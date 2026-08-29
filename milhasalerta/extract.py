import os
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel

from .models import Deal
from .sources.rss import Post

MODELO = "claude-haiku-4-5"

INSTRUCOES = """Você classifica posts de portais brasileiros de milhas e passagens aéreas.

Responda com um destes kind:
- "voo": o post anuncia uma passagem específica com preço. Preencha destino (IATA) e o que houver
  de milhas e preco_brl. Muitos posts trazem OS DOIS ("R$ 593 ou 24 mil milhas") — preencha ambos.
  Só preencha origem se o post disser de onde sai; não invente São Paulo.
- "promo": bônus de transferência, compra de pontos com desconto, ou promoção de programa sem rota.
  Preencha programa e bonus_pct quando houver percentual.
- "irrelevante": notícia, review de cartão, novidade de aeroporto, conteúdo institucional.

Valores em milhas vêm como "24 mil"=24000 ou "3.391"=3391. preco_brl é inteiro em reais, sem centavos.
Use o menor valor quando o post disser "a partir de". Deixe null o que o post não afirmar."""


class DealExtraido(BaseModel):
    kind: Literal["voo", "promo", "irrelevante"]
    programa: Optional[str] = None
    origem: Optional[str] = None
    destino: Optional[str] = None
    cabine: Optional[Literal["economica", "executiva", "primeira"]] = None
    milhas: Optional[int] = None
    preco_brl: Optional[int] = None
    bonus_pct: Optional[int] = None


def _client() -> anthropic.Anthropic:
    # Chave identity-linked exige o workspace em toda requisição; chave comum, não.
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    headers = {"anthropic-workspace-id": workspace} if workspace else None
    return anthropic.Anthropic(default_headers=headers)


class Extractor:
    def __init__(self, client: Optional[anthropic.Anthropic] = None):
        self.client = client or _client()

    def __call__(self, post: Post) -> Optional[Deal]:
        resposta = self.client.messages.parse(
            model=MODELO,
            max_tokens=1024,
            system=INSTRUCOES,
            messages=[
                {
                    "role": "user",
                    "content": f"Título: {post.titulo}\n\nResumo: {post.resumo}",
                }
            ],
            output_format=DealExtraido,
        )
        extraido = resposta.parsed_output
        if extraido.kind == "irrelevante":
            return None
        # Um "voo" sem nenhum preço não é acionável.
        if extraido.kind == "voo" and extraido.milhas is None and extraido.preco_brl is None:
            return None
        return Deal(
            kind=extraido.kind,
            titulo=post.titulo,
            url=post.url,
            fonte=post.fonte,
            dedup_key=post.url,
            programa=extraido.programa,
            origem=extraido.origem,
            destino=extraido.destino,
            cabine=extraido.cabine,
            milhas=extraido.milhas,
            preco_brl=extraido.preco_brl,
            bonus_pct=extraido.bonus_pct,
        )
