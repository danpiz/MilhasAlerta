import html
import re
from dataclasses import dataclass
from typing import Callable, Optional

import feedparser
import requests

from ..models import Deal

# Os portais rejeitam user-agents de biblioteca com 403.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
LIMITE_RESUMO = 600


@dataclass
class Post:
    titulo: str
    resumo: str
    url: str
    fonte: str


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
    ):
        self.nome = nome
        self.url = url
        self._extrair = extrair
        self._ja_visto = ja_visto

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
            )
            for entrada in feed.entries
            if entrada.get("link")
        ]

    def fetch(self) -> list[Deal]:
        # Filtrar antes de extrair: cada post novo custa uma chamada ao Haiku.
        novos = [post for post in self._posts() if not self._ja_visto(post.url)]
        deals = [self._extrair(post) for post in novos]
        return [deal for deal in deals if deal is not None]
