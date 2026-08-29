from main import _marcador
from milhasalerta.sources.telegram_channel import Post


def test_seed_marca_a_chave_de_dedup_nao_o_link():
    """No Telegram a chave e a permalink e a url e o artigo. Marcar a url no
    --seed nao semeia nada: o backlog inteiro volta como novo na proxima."""
    post = Post(
        titulo="Caribe na Mega Promo!",
        resumo="34 mil milhas",
        url="https://melhores.la/DiaVM1",
        fonte="Melhores Destinos",
        dedup_key="https://t.me/melhoresdestinos/19181",
    )
    assert _marcador(post).dedup_key == "https://t.me/melhoresdestinos/19181"
