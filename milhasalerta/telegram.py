import os

import requests

from .airports import describe
from .models import Deal


def _milhas_curtas(milhas: int) -> str:
    return f"{milhas // 1000}k" if milhas >= 1000 else str(milhas)


def formatar(deal: Deal, regras: list[str]) -> str:
    linhas = []
    if deal.kind == "voo":
        rota = describe(deal.destino) if deal.destino else "Destino não identificado"
        if deal.origem:
            rota = f"{describe(deal.origem)} → {rota}"
        linhas.append(f"✈️ <b>{rota}</b>")

        precos = []
        if deal.preco_brl is not None:
            precos.append(f"R$ {deal.preco_brl:,}".replace(",", "."))
        if deal.milhas is not None:
            milhas = _milhas_curtas(deal.milhas)
            precos.append(f"{milhas} {deal.programa}" if deal.programa else f"{milhas} milhas")
        if precos:
            linhas.append(" ou ".join(precos))
        if deal.cabine:
            linhas.append(f"Classe: {deal.cabine}")
    else:
        linhas.append(f"🎁 <b>{deal.programa or 'Promoção'}</b>")
        if deal.bonus_pct is not None:
            linhas.append(f"Bônus de {deal.bonus_pct}%")

    linhas.append(f"\n{deal.titulo}")
    linhas.append(f'<a href="{deal.url}">{deal.fonte}</a>')
    linhas.append(f"<i>{', '.join(regras)}</i>")
    return "\n".join(linhas)


def enviar(texto: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    resposta = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": os.environ["TELEGRAM_CHAT_ID"],
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    resposta.raise_for_status()
