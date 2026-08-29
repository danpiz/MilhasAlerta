import os
from typing import Callable, Optional, Protocol

from ..models import Deal
from .rss import Post, RssSource
from .seats_aero import SeatsAeroSource
from .telegram_channel import TelegramChannelSource


class DealSource(Protocol):
    nome: str

    def fetch(self) -> list[Deal]: ...


def get_sources(
    config: dict,
    extrair: Callable[[Post], Optional[Deal]],
    ja_visto: Callable[[str], bool],
) -> list[DealSource]:
    sources: list[DealSource] = [
        TelegramChannelSource(
            nome=c["nome"], canal=c["canal"], extrair=extrair, ja_visto=ja_visto
        )
        for c in config.get("canais", [])
    ]
    sources += [
        RssSource(nome=feed["nome"], url=feed["url"], extrair=extrair, ja_visto=ja_visto)
        for feed in config.get("feeds", [])
    ]
    seats_key = os.environ.get("SEATS_API_KEY")
    if seats_key:
        sources.append(SeatsAeroSource(api_key=seats_key, alertas=config["alertas"]))
    return sources
