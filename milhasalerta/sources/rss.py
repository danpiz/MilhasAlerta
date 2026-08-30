import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import feedparser
import requests

from ..models import Deal, recente

# Os portais rejeitam user-agents de biblioteca com 403.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
LIMITE_RESUMO = 600


@dataclass
class Post:
    titulo: str
    resumo: str
    url: str
    fonte: str
    dedup_key: str
    publicado: Optional[datetime] = None


def _publicado(entrada) -> Optional[datetime]:
    marca = entrada.get("published_parsed") or entrada.get("updated_parsed")
    return datetime(*marca[:6], tzinfo=timezone.utc) if marca else None


def _texto_limpo(bruto: str) -> str:
    sem_tags = re.sub(r"<[^>]+>", " ", bruto or "")
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()[:LIMITE_RESUMO]


class RssSource:
    def __init__(
        self,
        nome: str,
        url: str,
        extrair: Callable[[Post], Optional[Deal]],
        ja_visto: Callable[[str], bool],
        marcar: Optional[Callable[[str], None]] = None,
        max_idade_horas: Optional[float] = None,
    ):
        self.nome = nome
        self.url = url
        self._extrair = extrair
        self._ja_visto = ja_visto
        self._marcar = marcar
        self.max_idade_horas = max_idade_horas

    def _posts(self) -> list[Post]:
        resposta = requests.get(self.url, headers={"User-Agent": UA}, timeout=30)
        resposta.raise_for_status()
        feed = feedparser.parse(resposta.content)
        return [
            Post(
                titulo=_texto_limpo(entrada.get("title", "")),
                resumo=_texto_limpo(entrada.get("summary", "")),
                url=entrada.get("link", ""),
                fonte=self.nome,
                dedup_key=entrada.get("link", ""),
                publicado=_publicado(entrada),
            )
            for entrada in feed.entries
            if entrada.get("link")
        ]

    def fetch(self) -> list[Deal]:
        # Filtrar antes de extrair: cada post novo custa uma chamada ao Haiku.
        novos = [
            post for post in self._posts()
            if recente(post.publicado, self.max_idade_horas)
            and not self._ja_visto(post.dedup_key)
        ]
        deals = [self._extrair(post) for post in novos]
        # Post que o extrator rejeita tem de ser marcado tambem, senao volta a
        # custar uma chamada ao Haiku em TODA rodada ate sair da janela de 24h.
        # A 15 min isso e ~96 chamadas por post rejeitado, em vez de ~5.
        # `None` aqui so significa "nao e deal": erro de API sobe como excecao.
        if self._marcar:
            for post, deal in zip(novos, deals):
                if deal is None:
                    self._marcar(post.dedup_key)
        return [deal for deal in deals if deal is not None]
