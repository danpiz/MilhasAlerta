import os
from typing import Callable, Optional, Protocol

from ..models import Deal
from .rss import Post, RssSource
from .seats_aero import SeatsAeroSource


class DealSource(Protocol):
    nome: str

    def fetch(self) -> list[Deal]: ...


def get_sources(
    config: dict,
    extrair: Callable[[Post], Optional[Deal]],
    ja_visto: Callable[[str], bool],
) -> list[DealSource]:
    sources: list[DealSource] = [
        RssSource(nome=feed["nome"], url=feed["url"], extrair=extrair, ja_visto=ja_visto)
        for feed in config["feeds"]
    ]
    seats_key = os.environ.get("SEATS_API_KEY")
    if seats_key:
        sources.append(SeatsAeroSource(api_key=seats_key, alertas=config["alertas"]))
    return sources
