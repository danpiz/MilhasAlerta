import os
from typing import Optional

import requests

from .airports import describe
from .models import Deal


MESES = "jan fev mar abr mai jun jul ago set out nov dez".split()


def _milhas_curtas(milhas: int) -> str:
    return f"{milhas // 1000}k" if milhas >= 1000 else str(milhas)


def _dia_curto(iso: str) -> str:
    ano, mes, dia = iso.split("-")
    return f"{int(dia)} {MESES[int(mes) - 1]}"


def _datas(ida: str, volta: Optional[str]) -> str:
    """Sempre diz se e so ida: o mesmo trecho ida e volta custa quase o dobro,
    e um alerta que omite isso passa por barato o que nao e."""
    if volta:
        return f"{_dia_curto(ida)} a {_dia_curto(volta)}"
    return f"{_dia_curto(ida)}, só ida"


def formatar(deal: Deal, regras: list[str]) -> str:
    """Tres linhas no maximo. O card de preview do Telegram fica desligado no
    envio, senao ele expande o link num bloco com foto que engole o alerta."""
    if deal.kind == "voo":
        destino = describe(deal.destino) if deal.destino else "Destino não identificado"
        # A origem so aparece quando o post a declara -- e ai importa, porque a
        # regra de origem aceita origem ausente e o deal pode nao sair de SP.
        rota = f"{describe(deal.origem)} → {destino}" if deal.origem else destino
        if deal.cabine in ("executiva", "primeira"):
            rota = f"{rota} · {deal.cabine}"
        cabecalho = f"✈️ <b>{rota}</b>"

        precos = []
        if deal.preco_brl is not None:
            precos.append(f"R$ {deal.preco_brl:,}".replace(",", "."))
        if deal.milhas is not None:
            milhas = _milhas_curtas(deal.milhas)
            lado = f"{milhas} {deal.programa}" if deal.programa else f"{milhas} milhas"
            # A conversao e o que torna os dois lados comparaveis de bate-pronto.
            # "~" porque a cotacao do milheiro e estimativa, nao preco de mercado.
            if deal.custo_efetivo_brl is not None:
                convertido = f"{deal.custo_efetivo_brl:,}".replace(",", ".")
                lado = f"{lado} (≈R$ {convertido})"
            precos.append(lado)
        detalhe = " ou ".join(precos)
        # Preco sem data nao e acionavel, e so-ida sem dizer engana quem le
        # rapido -- o mesmo trecho ida e volta custa quase o dobro.
        if deal.data:
            detalhe = f"{detalhe} · {_datas(deal.data, deal.data_volta)}"
        elif deal.ida_e_volta is not None:
            # Post de portal raramente traz data (medido: 5% de 60 posts), mas
            # quando diz o tipo de viagem isso muda como se le o preco.
            detalhe = f"{detalhe} · {'ida e volta' if deal.ida_e_volta else 'só ida'}"
        # Na linha do preco, nao no cabecalho: la sairia <b> dentro de <b>.
        if deal.queda_pct:
            detalhe = f"{detalhe} · {deal.queda_pct}% abaixo do normal"
    else:
        cabecalho = f"🎁 <b>{deal.programa or 'Promoção'}</b>"
        detalhe = f"{deal.bonus_pct}% de bônus" if deal.bonus_pct is not None else deal.titulo

    linhas = [cabecalho]
    if detalhe:
        linhas.append(detalhe)
    linhas.append(f'<a href="{deal.url}">{deal.fonte} →</a>')
    return "\n".join(linhas)


class TelegramError(RuntimeError):
    """Erro sem a URL da API — ela carrega o bot token embutido."""


def receber(desde: Optional[int] = None) -> list[dict]:
    """Mensagens novas para o bot.

    Sem processo sempre ligado, o bot só lê quando o cron roda — e o
    agendamento do GitHub entrega bem menos que o cron pede. Por isso `desde`
    (o offset) tem de ser persistido: se a mesma mensagem for lida duas vezes,
    o alerta é criado em duplicata.
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    params = {"timeout": 0}
    if desde is not None:
        params["offset"] = desde
    try:
        resposta = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates", params=params, timeout=30
        )
        resposta.raise_for_status()
    except requests.RequestException as erro:
        status = getattr(erro.response, "status_code", None)
        raise TelegramError(f"falha ao ler mensagens ({status or type(erro).__name__})") from None
    return resposta.json().get("result", [])


def enviar(texto: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resposta = requests.post(
            url,
            json={
                "chat_id": os.environ["TELEGRAM_CHAT_ID"],
                "text": texto,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        resposta.raise_for_status()
    except requests.RequestException as erro:
        # A API do Telegram poe o token no caminho da URL, e requests inclui a
        # URL em toda mensagem de erro. Num repo publico o log do Actions e
        # publico: deixar o traceback subir cru depende de o GitHub mascarar o
        # segredo. Melhor nunca produzir a string.
        status = getattr(erro.response, "status_code", None)
        detalhe = f"HTTP {status}" if status else type(erro).__name__
        raise TelegramError(f"falha ao enviar alerta ({detalhe})") from None
