import pytest

from milhasalerta.models import Deal
from milhasalerta.sources.base import get_sources
from milhasalerta.sources.rss import RssSource, _texto_limpo

CONFIG = {
    "feeds": [{"nome": "Feed A", "url": "https://exemplo.com/feed"}],
    "alertas": [{"nome": "R", "kind": "voo", "origens": ["GRU"], "enabled": True}],
}


def test_sem_chave_do_seats_so_o_rss(monkeypatch):
    monkeypatch.delenv("SEATS_API_KEY", raising=False)
    sources = get_sources(CONFIG, extrair=lambda p: None, ja_visto=lambda u: False)
    assert [s.nome for s in sources] == ["Feed A"]


def test_com_chave_do_seats_o_provider_entra(monkeypatch):
    monkeypatch.setenv("SEATS_API_KEY", "chave-falsa")
    sources = get_sources(CONFIG, extrair=lambda p: None, ja_visto=lambda u: False)
    assert [s.nome for s in sources] == ["Feed A", "seats.aero"]


def test_rss_nao_extrai_post_ja_visto():
    """Cada post novo custa uma chamada ao Haiku; visto não pode ser re-extraído."""
    extraidos = []

    def extrair(post):
        extraidos.append(post.url)
        return Deal(
            kind="voo", titulo=post.titulo, url=post.url, fonte=post.fonte,
            dedup_key=post.url, preco_brl=100,
        )

    source = RssSource(
        nome="F", url="https://exemplo.com/feed",
        extrair=extrair, ja_visto=lambda url: url == "https://exemplo.com/velho",
    )
    source._posts = lambda: [
        type("P", (), {"titulo": "novo", "resumo": "", "url": "https://exemplo.com/novo", "fonte": "F"})(),
        type("P", (), {"titulo": "velho", "resumo": "", "url": "https://exemplo.com/velho", "fonte": "F"})(),
    ]

    deals = source.fetch()
    assert extraidos == ["https://exemplo.com/novo"]
    assert len(deals) == 1


def test_extracao_que_devolve_none_nao_vira_deal():
    source = RssSource(
        nome="F", url="u", extrair=lambda p: None, ja_visto=lambda u: False
    )
    source._posts = lambda: [
        type("P", (), {"titulo": "t", "resumo": "", "url": "https://exemplo.com/a", "fonte": "F"})()
    ]
    assert source.fetch() == []


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("<p>Voe para <b>Lima</b></p>", "Voe para Lima"),
        ("R$ 593 &#8211; taxas", "R$ 593 – taxas"),
        ("linha1\n\n   linha2", "linha1 linha2"),
    ],
)
def test_limpeza_de_html(bruto, esperado):
    assert _texto_limpo(bruto) == esperado
