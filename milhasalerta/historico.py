"""Série de preços por rota, para detectar queda relativa.

O teto fixo ("Europa abaixo de R$ 2.500") só pega o que você já sabe querer. A
queda relativa pega o que você não esperava — é o "63% abaixo da média" que o
Google mostra. Para isso é preciso saber o que era normal naquela rota, e isso
só se aprende observando.

Usa mediana, não média: uma única tarifa absurda distorce a média e cria um
"normal" que nunca existiu.
"""

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Optional

RETENCAO = timedelta(days=60)
MINIMO_OBSERVACOES = 5


def chave(origem: str, destino: str, data: str) -> str:
    return f"{origem}-{destino}-{data}"


def registrar(serie: dict, k: str, preco: int, agora: Optional[datetime] = None) -> None:
    agora = agora or datetime.now(timezone.utc)
    serie.setdefault(k, []).append([agora.isoformat(), preco])


def normal(serie: dict, k: str) -> Optional[int]:
    """Preço tipico da rota, ou None enquanto não houver amostra suficiente."""
    pontos = serie.get(k) or []
    if len(pontos) < MINIMO_OBSERVACOES:
        return None
    return round(median(preco for _, preco in pontos))


def queda_pct(serie: dict, k: str, preco: int) -> Optional[int]:
    """Quanto o preço está abaixo do normal, em pontos percentuais."""
    base = normal(serie, k)
    if not base or preco >= base:
        return None
    return round((base - preco) / base * 100)


def podar(serie: dict, agora: Optional[datetime] = None) -> dict:
    limite = (agora or datetime.now(timezone.utc)) - RETENCAO
    podada = {}
    for k, pontos in serie.items():
        vivos = [p for p in pontos if datetime.fromisoformat(p[0]) > limite]
        if vivos:
            podada[k] = vivos
    return podada
