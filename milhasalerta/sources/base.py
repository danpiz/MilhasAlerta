import os
from typing import Callable, Optional, Protocol

from ..models import Deal
from .rss import Post, RssSource
from .seats_aero import SeatsAeroSource
from .google_flights import GoogleFlightsSource
from .telegram_channel import TelegramChannelSource


class DealSource(Protocol):
    nome: str

    def fetch(self) -> list[Deal]: ...


def get_sources(
    config: dict,
    extrair: Callable[[Post], Optional[Deal]],
    ja_visto: Callable[[str], bool],
    observar_preco: Optional[Callable[[str, str, str, int], Optional[int]]] = None,
    google_liberado: bool = True,
    chaves_vistas: Optional[Callable[[str], list[str]]] = None,
) -> list[DealSource]:
    idade = config.get("max_idade_horas")
    sources: list[DealSource] = [
        TelegramChannelSource(
            nome=c["nome"], canal=c["canal"], extrair=extrair,
            ja_visto=ja_visto, max_idade_horas=idade,
        )
        for c in config.get("canais", [])
    ]
    sources += [
        RssSource(
            nome=feed["nome"], url=feed["url"], extrair=extrair,
            ja_visto=ja_visto, max_idade_horas=idade,
        )
        for feed in config.get("feeds", [])
    ]
    rotas = config.get("rotas")
    if rotas and observar_preco is not None and chaves_vistas is not None and google_liberado:
        sources.append(
            GoogleFlightsSource(
                rotas=rotas,
                vistas=chaves_vistas,
                observar=observar_preco,
                amostras=config.get("google_amostras_de_data", 6),
                limite_por_rota=config.get("google_max_alertas_por_rota", 3),
            )
        )
    seats_key = os.environ.get("SEATS_API_KEY")
    if seats_key:
        sources.append(
            SeatsAeroSource(
                api_key=seats_key,
                alertas=config["alertas"],
                max_staleness_horas=config.get("seats_max_staleness_horas", 5),
            )
        )
    return sources
