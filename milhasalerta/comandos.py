"""Criar e gerenciar alertas conversando com o bot no Telegram.

Editar YAML e dar push para vigiar uma rota é atrito demais. Aqui o texto
livre vira uma rota vigiada — a mesma estrutura do config.yaml, então nada no
motor precisa saber de onde ela veio.

LATÊNCIA: sem processo sempre ligado, o bot só lê quando o cron roda, e o
agendamento do GitHub entrega bem menos que pede (medido: ~1 execução a cada
4h). A confirmação demora. Por isso ela diz explicitamente quando chegou, em
vez de fingir que foi instantânea.
"""

import os
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel

from .regioes import REGIOES

MODELO = "claude-haiku-4-5"
LIMITE_ALERTAS = 20

INSTRUCOES = f"""Converta o pedido de viagem em uma rota vigiada.

Hoje é {{hoje}}. Regiões conhecidas: {", ".join(REGIOES)}.

- destinos: códigos IATA, ou o nome de uma região da lista acima. Para um país
  sem região própria, liste os aeroportos principais (Portugal -> LIS, OPO).
- origens: IATA. Se não disser de onde sai, use GRU.
- a_partir_de: primeiro dia da janela desejada, em AAAA-MM-DD. "janeiro de
  2027" vira 2027-01-05. Se não houver menção a data, deixe null.
- ida_e_volta: true a menos que peçam só ida.
- dias_de_viagem: duração pedida; 12 se não disserem.
- max_preco_brl: só se citarem um teto em reais.
- cabine: economica, executiva ou primeira; economica se não disserem.
- nome: rótulo curto e humano, como "Portugal em janeiro de 2027"."""


class RotaPedida(BaseModel):
    nome: str
    origens: list[str]
    destinos: list[str]
    ida_e_volta: bool = True
    dias_de_viagem: int = 12
    a_partir_de: Optional[str] = None
    max_preco_brl: Optional[int] = None
    cabine: Literal["economica", "executiva", "primeira"] = "economica"


def interpretar(texto: str, client=None) -> dict:
    """Texto livre -> rota vigiada, no mesmo formato do config.yaml."""
    import anthropic

    if client is None:
        workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        headers = {"anthropic-workspace-id": workspace} if workspace else None
        client = anthropic.Anthropic(default_headers=headers)

    resposta = client.messages.parse(
        model=MODELO,
        max_tokens=1024,
        system=INSTRUCOES.format(hoje=date.today().isoformat()),
        messages=[{"role": "user", "content": texto}],
        output_format=RotaPedida,
    )
    rota = resposta.parsed_output.model_dump()
    # Sem teto declarado, o gatilho passa a ser queda contra o historico --
    # senao a rota seria vigiada e nunca alertaria nada.
    if rota.get("max_preco_brl") is None:
        rota["min_queda_pct"] = 25
    rota["enabled"] = True
    return rota


def _descrever(rota: dict) -> str:
    partes = [", ".join(rota["destinos"])]
    if rota.get("a_partir_de"):
        partes.append(f"a partir de {rota['a_partir_de']}")
    partes.append("ida e volta" if rota.get("ida_e_volta") else "só ida")
    if rota.get("cabine") and rota["cabine"] != "economica":
        partes.append(rota["cabine"])
    if rota.get("max_preco_brl"):
        partes.append(f"até {_reais(rota['max_preco_brl'])}")
    else:
        partes.append(f"queda de {rota.get('min_queda_pct', 25)}%")
    return " · ".join(partes)


def _reais(valor: int) -> str:
    return f"R$ {valor:,}".replace(",", ".")


def _sugerir(menor: int) -> int:
    """Teto util fica ABAIXO do preco corrente -- e o que separa promocao de
    preco normal. 10% abaixo do mais barato de hoje, arredondado."""
    return int(round(menor * 0.9 / 50) * 50)


def _cotacao(rota: dict, precos: dict[str, int]) -> str:
    """Preco corrente da rota, e se o teto escolhido faz sentido contra ele.

    Um teto sem referencia e um chute: "abaixo de R$ 4.000" nao diz nada a quem
    nao sabe se o trecho custa 3.000 ou 10.000. Dizer isso na hora da criacao e
    o que permite corrigir antes de o alerta ficar mudo ou virar enxurrada."""
    # Rota sem teto depende do historico, que ainda nao existe. Dizer isso
    # importa mais que a cotacao: sem o aviso, o silencio parece defeito.
    sem_teto = (
        f"\nSem teto de preço, aviso quando cair {rota.get('min_queda_pct', 25)}% abaixo do "
        "normal da rota — isso leva alguns dias, até eu aprender quanto ela costuma custar."
    )
    if not precos:
        if rota.get("max_preco_brl") is None:
            return sem_teto
        return "\nNão consegui cotar a rota agora — o teto fica sem referência por enquanto."

    ordenados = sorted(precos.items(), key=lambda kv: kv[1])
    menor = ordenados[0][1]
    maior = ordenados[-1][1]
    destino = "destino" if len(precos) == 1 else "destinos"
    linhas = [f"\nPreço hoje (amostra de {len(precos)} {destino}):"]
    linhas += [f"  {d}  {_reais(p)}" for d, p in ordenados[:3]]
    if len(ordenados) > 3:
        linhas.append(f"  mais caro na amostra: {_reais(maior)}")

    teto = rota.get("max_preco_brl")
    if teto is None:
        linhas.append(sem_teto)
    elif teto < menor:
        linhas.append(
            f"\n⚠️ Seu teto ({_reais(teto)}) está abaixo de tudo que achei agora. "
            f"Ele vai ficar mudo até a rota cair {round((1 - teto / menor) * 100)}%."
        )
    elif teto > maior:
        linhas.append(
            f"\n⚠️ Seu teto ({_reais(teto)}) está acima do preço normal — ele alertaria "
            f"a rota inteira, não promoção. Algo perto de {_reais(_sugerir(menor))} avisaria só o que é barato."
        )
    else:
        linhas.append(f"\nSeu teto ({_reais(teto)}) está dentro da faixa atual.")
    if teto is not None:
        linhas.append("Para mudar: /remover e criar de novo com outro valor.")
    return "\n".join(linhas)


def processar(
    texto: str, alertas: list[dict], client=None, cotar=None
) -> tuple[list[dict], Optional[str]]:
    """Aplica um comando. Devolve (alertas atualizados, resposta ao usuário)."""
    texto = (texto or "").strip()
    if not texto.startswith("/"):
        return alertas, None

    comando, _, resto = texto.partition(" ")
    comando = comando.split("@")[0].lower()
    resto = resto.strip()

    if comando == "/alertas":
        if not alertas:
            return alertas, "Nenhum alerta ativo. Crie com /alerta <o que você quer>."
        linhas = [f"{i}. <b>{a['nome']}</b>\n   {_descrever(a)}" for i, a in enumerate(alertas, 1)]
        return alertas, "Alertas ativos:\n\n" + "\n".join(linhas)

    if comando == "/remover":
        if not resto.isdigit():
            return alertas, "Use /remover <número>, como aparece em /alertas."
        i = int(resto)
        if not 1 <= i <= len(alertas):
            return alertas, f"Não existe alerta {i}. Veja /alertas."
        removido = alertas[i - 1]["nome"]
        return alertas[: i - 1] + alertas[i:], f"Removido: {removido}"

    if comando == "/alerta":
        if not resto:
            return alertas, (
                "Descreva a viagem. Exemplo:\n"
                "<code>/alerta voos pra Portugal em janeiro de 2027 "
                "ida e volta economica</code>"
            )
        if len(alertas) >= LIMITE_ALERTAS:
            return alertas, f"Limite de {LIMITE_ALERTAS} alertas. Remova um com /remover."
        try:
            rota = interpretar(resto, client=client)
        except Exception:
            return alertas, "Não entendi o pedido. Tente descrever com destino e período."
        # Cotar na criacao e o que torna o teto ajustavel: falha aqui nao pode
        # perder o alerta que o usuario acabou de pedir.
        try:
            precos = cotar(rota) if cotar else {}
        except Exception:
            precos = {}
        return alertas + [rota], (
            f"✅ Monitorando <b>{rota['nome']}</b>\n{_descrever(rota)}\n"
            f"{_cotacao(rota, precos)}"
        )

    return alertas, (
        "Comandos:\n"
        "<code>/alerta &lt;viagem&gt;</code> — vigiar uma rota\n"
        "<code>/alertas</code> — listar\n"
        "<code>/remover &lt;n&gt;</code> — apagar"
    )
