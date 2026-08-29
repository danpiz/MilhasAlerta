"""Exercita o Haiku de verdade contra títulos reais dos portais.

Pulado sem ANTHROPIC_API_KEY. Gasta alguns centavos de token por execução.
Rodar com: pytest tests/test_extract_live.py -v
"""

import os

import pytest

from milhasalerta.extract import Extractor
from milhasalerta.sources.rss import Post

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="precisa de ANTHROPIC_API_KEY",
)


def post(titulo: str, resumo: str = "") -> Post:
    return Post(
        titulo=titulo, resumo=resumo, url="https://exemplo.com/x",
        fonte="teste", dedup_key="https://exemplo.com/x",
    )


@pytest.fixture(scope="module")
def extrair():
    return Extractor()


def test_lima_traz_os_dois_precos(extrair):
    deal = extrair(
        post(
            "Voe para Lima a partir de R$ 593 ou 24 mil milhas LATAM Pass + taxas",
            "bilhetes de ida e volta entre São Paulo (GRU) e Lima (LIM)",
        )
    )
    assert deal.kind == "voo"
    assert deal.destino == "LIM"
    assert deal.milhas == 24000
    assert deal.preco_brl == 593
    assert "latam" in (deal.programa or "").lower()


def test_mega_promo_com_milhas_nao_redondas(extrair):
    deal = extrair(
        post("Mega Promo LATAM! Trechos para diversos destinos a partir de R$ 150 ou 3.391 milhas + taxas")
    )
    assert deal.kind == "voo"
    assert deal.milhas == 3391
    assert deal.preco_brl == 150


def test_bonus_de_transferencia_vira_promo(extrair):
    deal = extrair(
        post("Prorrogado! Até 100% de bônus na transferência de pontos Livelo para o Azul Fidelidade")
    )
    assert deal.kind == "promo"
    assert deal.bonus_pct == 100


def test_noticia_de_aeroporto_e_irrelevante(extrair):
    deal = extrair(
        post("Aeroporto de Campinas instala novo sistema automático de controle de passaportes")
    )
    assert deal is None
