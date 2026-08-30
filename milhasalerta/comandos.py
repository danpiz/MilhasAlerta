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
        partes.append(f"até R$ {rota['max_preco_brl']}")
    else:
        partes.append(f"queda de {rota.get('min_queda_pct', 25)}%")
    return " · ".join(partes)


def processar(texto: str, alertas: list[dict], client=None) -> tuple[list[dict], Optional[str]]:
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
        gatilho = (
            "Aviso quando aparecer algo abaixo desse valor."
            if rota.get("max_preco_brl")
            else "Sem teto de preço, aviso quando cair bem abaixo do normal da rota — "
            "isso leva alguns dias, até eu aprender quanto ela costuma custar."
        )
        return alertas + [rota], (
            f"✅ Monitorando <b>{rota['nome']}</b>\n{_descrever(rota)}\n\n{gatilho}"
        )

    return alertas, (
        "Comandos:\n"
        "<code>/alerta &lt;viagem&gt;</code> — vigiar uma rota\n"
        "<code>/alertas</code> — listar\n"
        "<code>/remover &lt;n&gt;</code> — apagar"
    )
