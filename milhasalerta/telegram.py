import os

import requests

from .airports import describe
from .models import Deal


def _milhas_curtas(milhas: int) -> str:
    return f"{milhas // 1000}k" if milhas >= 1000 else str(milhas)


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
            precos.append(f"{milhas} {deal.programa}" if deal.programa else f"{milhas} milhas")
        detalhe = " ou ".join(precos)
    else:
        cabecalho = f"🎁 <b>{deal.programa or 'Promoção'}</b>"
        detalhe = f"{deal.bonus_pct}% de bônus" if deal.bonus_pct is not None else deal.titulo

    linhas = [cabecalho]
    if detalhe:
        linhas.append(detalhe)
    linhas.append(f'<a href="{deal.url}">{deal.fonte} →</a>')
    return "\n".join(linhas)


def enviar(texto: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    resposta = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": os.environ["TELEGRAM_CHAT_ID"],
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    resposta.raise_for_status()
