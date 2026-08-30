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
        type("P", (), {"titulo": "novo", "resumo": "", "url": "https://exemplo.com/novo", "fonte": "F", "dedup_key": "https://exemplo.com/novo", "publicado": None})(),
        type("P", (), {"titulo": "velho", "resumo": "", "url": "https://exemplo.com/velho", "fonte": "F", "dedup_key": "https://exemplo.com/velho", "publicado": None})(),
    ]

    deals = source.fetch()
    assert extraidos == ["https://exemplo.com/novo"]
    assert len(deals) == 1


def test_extracao_que_devolve_none_nao_vira_deal():
    source = RssSource(
        nome="F", url="u", extrair=lambda p: None, ja_visto=lambda u: False
    )
    source._posts = lambda: [
        type("P", (), {"titulo": "t", "resumo": "", "url": "https://exemplo.com/a", "fonte": "F", "dedup_key": "https://exemplo.com/a", "publicado": None})()
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


# --- post rejeitado tem de ser marcado ----------------------------------------
# Medido em 30/08/2026: 22 posts frescos estavam sem marcacao. Sem marcar o
# descarte, cada um volta a custar uma chamada ao Haiku em TODA rodada ate sair
# da janela de 24h -- ~5 vezes hoje, ~96 se o gatilho externo for a cada 15 min.

def _post(url):
    return type("P", (), {"titulo": "t", "resumo": "", "url": url, "fonte": "F",
                          "dedup_key": url, "publicado": None})()


def fonte_rss(extrair, marcados, urls):
    s = RssSource(nome="F", url="u", extrair=extrair, ja_visto=lambda u: False,
                  marcar=marcados.append)
    s._posts = lambda: [_post(u) for u in urls]
    return s


def test_post_rejeitado_e_marcado():
    marcados = []
    fonte_rss(lambda p: None, marcados, ["https://ex.com/a", "https://ex.com/b"]).fetch()
    assert marcados == ["https://ex.com/a", "https://ex.com/b"]


def test_post_aproveitado_nao_e_marcado_pela_fonte():
    """Quem vira deal e marcado pelo run_once depois de casar as regras."""
    marcados = []
    def extrair(p):
        return Deal(kind="voo", titulo="t", url=p.url, fonte="F",
                    dedup_key=p.dedup_key, preco_brl=100)
    deals = fonte_rss(extrair, marcados, ["https://ex.com/a"]).fetch()
    assert marcados == [] and len(deals) == 1


def test_marca_so_o_rejeitado_quando_ha_mistura():
    marcados = []
    def extrair(p):
        if p.url.endswith("bom"):
            return Deal(kind="voo", titulo="t", url=p.url, fonte="F",
                        dedup_key=p.dedup_key, preco_brl=100)
        return None
    fonte_rss(extrair, marcados, ["https://ex.com/bom", "https://ex.com/ruim"]).fetch()
    assert marcados == ["https://ex.com/ruim"]


def test_sem_callback_de_marcar_nao_quebra():
    s = RssSource(nome="F", url="u", extrair=lambda p: None, ja_visto=lambda u: False)
    s._posts = lambda: [_post("https://ex.com/a")]
    assert s.fetch() == []
