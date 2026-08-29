from milhasalerta.models import Deal
from milhasalerta.telegram import formatar


def test_voo_com_os_dois_precos_mostra_os_dois():
    deal = Deal(
        kind="voo", titulo="Voe para Lima a partir de R$ 593 ou 24 mil milhas",
        url="https://exemplo.com/lima", fonte="Passageiro de Primeira", dedup_key="k",
        programa="LATAM Pass", origem="GRU", destino="LIM",
        cabine="economica", milhas=24000, preco_brl=593,
    )
    texto = formatar(deal, ["Firehose"])
    assert "R$ 593" in texto
    assert "24k LATAM Pass" in texto
    assert " ou " in texto
    assert "São Paulo" in texto and "Lima" in texto
    assert "🇧🇷" in texto and "🇵🇪" in texto
    assert "Firehose" in texto


def test_voo_so_com_milhas_nao_inventa_reais():
    deal = Deal(
        kind="voo", titulo="t", url="u", fonte="f", dedup_key="k",
        destino="NRT", milhas=60000, programa="Smiles",
    )
    texto = formatar(deal, ["Executiva"])
    assert "R$" not in texto
    assert "60k Smiles" in texto


def test_promo_mostra_bonus():
    deal = Deal(
        kind="promo", titulo="Até 100% de bônus Livelo → Azul", url="u",
        fonte="Melhores Destinos", dedup_key="k", programa="Livelo", bonus_pct=100,
    )
    texto = formatar(deal, ["Bônus de transferência"])
    assert "100%" in texto
    assert "Livelo" in texto


def test_destino_desconhecido_nao_quebra():
    deal = Deal(
        kind="voo", titulo="t", url="u", fonte="f", dedup_key="k", preco_brl=500,
    )
    assert "Destino não identificado" in formatar(deal, ["Firehose"])


def test_lista_todas_as_regras_que_casaram():
    deal = Deal(
        kind="voo", titulo="t", url="u", fonte="f", dedup_key="k",
        destino="MIA", milhas=60000,
    )
    texto = formatar(deal, ["Executiva de SP", "Firehose"])
    assert "Executiva de SP, Firehose" in texto
