import pytest

from milhasalerta.sources.telegram_channel import (
    TelegramChannelSource,
    _e_artigo,
    _limpar,
    _normalizar,
)

# Trechos reais do HTML de t.me/s/, incluindo os dois casos que quebraram a v1:
# a imagem do banner (Pontos pra Voar) e a palavra autolinkada (Passageiro de Primeira).
PAGINA = """
<div class="tgme_widget_message" data-post="canal/101">
<div class="tgme_widget_message_text js-message_text">Caribe na Mega Promo!<br/>
Voos da Latam para Aruba por 34 mil milhas o trecho<br/>
<a href="https://melhores.la/DiaVM1">melhores.la/DiaVM1</a></div></div>
<div class="tgme_widget_message" data-post="canal/102">
<div class="tgme_widget_message_text js-message_text">Smiles com 355% de bônus<br/>
<a href="https://pontospravoar.com/wp-content/uploads/2026/03/banner.png">img</a>
<a href="https://pontospravoar.com/?p=138128">Leia mais</a></div></div>
<div class="tgme_widget_message" data-post="canal/103">
<div class="tgme_widget_message_photo">sem texto nenhum</div></div>
<div class="tgme_widget_message" data-post="canal/104">
<div class="tgme_widget_message_text js-message_text">Hotéis em Santiago com desconto<br/>
<a href="http://Hoteis.com">Hoteis.com</a>
<a href="https://passageirodeprimeira.com/hoteis-santiago">artigo</a></div></div>
"""


@pytest.fixture
def posts(monkeypatch):
    s = TelegramChannelSource("Canal", "x", extrair=lambda p: p, ja_visto=lambda k: False)
    monkeypatch.setattr(
        "milhasalerta.sources.telegram_channel.requests.get",
        lambda *a, **k: type("R", (), {"text": PAGINA, "raise_for_status": lambda s: None})(),
    )
    return s._mensagens()


def test_pula_mensagem_sem_texto(posts):
    # A mensagem 103 e so foto. Parear permalink por indice desalinharia daqui
    # em diante, dando chave de dedup errada para todas as seguintes.
    assert len(posts) == 3
    assert "canal/103" not in [p.dedup_key for p in posts]


def test_primeira_linha_vira_titulo_e_resto_resumo(posts):
    assert posts[0].titulo == "Caribe na Mega Promo!"
    assert "34 mil milhas" in posts[0].resumo


def test_link_curto_e_preservado(posts):
    assert posts[0].url == "https://melhores.la/DiaVM1"


def test_ignora_imagem_do_post_e_pega_o_artigo(posts):
    # A v1 pegava o banner .png.
    assert posts[1].url == "https://pontospravoar.com?p=138128"


def test_ignora_palavra_autolinkada_sem_caminho(posts):
    # O Telegram transforma "Hoteis.com" no texto em http://Hoteis.com.
    assert posts[2].url == "https://passageirodeprimeira.com/hoteis-santiago"


def test_permalink_vem_do_data_post_da_propria_mensagem(posts):
    # Depois da mensagem so-foto, a 4a mensagem tem de manter a chave 104.
    assert posts[2].dedup_key == "https://t.me/canal/104"


def test_dedup_pela_permalink_nao_pelo_link(posts):
    # Promos distintos compartilham landing page; a permalink os mantém separados.
    assert [p.dedup_key for p in posts] == [
        "https://t.me/canal/101",
        "https://t.me/canal/102",
        "https://t.me/canal/104",
    ]


def test_query_de_identidade_sobrevive_mas_utm_nao():
    assert _normalizar("https://x.com/a?p=1&utm_source=telegram") == "https://x.com/a?p=1"
    assert _normalizar("https://x.com/a/?fbclid=z") == "https://x.com/a"


@pytest.mark.parametrize(
    "url,esperado",
    [
        ("https://site.com/artigo-longo", True),
        ("https://site.com/?p=123", True),
        ("http://Hoteis.com", False),
        ("https://site.com/", False),
        ("https://site.com/foto.png", False),
        ("https://site.com/foto.JPG", False),
    ],
)
def test_reconhece_o_que_e_artigo(url, esperado):
    assert _e_artigo(url) is esperado


def test_limpar_converte_br_em_quebra():
    assert _limpar("a<br/>b<br>c") == "a\nb\nc"
