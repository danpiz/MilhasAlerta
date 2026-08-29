from milhasalerta.models import Deal
from milhasalerta.telegram import formatar


def voo(**kwargs) -> Deal:
    base = dict(kind="voo", titulo="t", url="https://x.com/a", fonte="Fonte", dedup_key="k")
    return Deal(**{**base, **kwargs})


def test_alerta_cabe_em_tres_linhas():
    texto = formatar(voo(destino="EZE", preco_brl=307, milhas=12000, programa="LATAM Pass"), ["R"])
    assert len(texto.split("\n")) == 3


def test_voo_com_os_dois_precos_mostra_os_dois():
    texto = formatar(
        voo(origem="GRU", destino="LIM", milhas=24000, preco_brl=593, programa="LATAM Pass"),
        ["Firehose"],
    )
    assert "R$ 593 ou 24k LATAM Pass" in texto
    assert "São Paulo 🇧🇷 → Lima 🇵🇪" in texto


def test_sem_origem_mostra_so_o_destino():
    texto = formatar(voo(destino="EZE", preco_brl=307), ["R"])
    assert "Buenos Aires 🇦🇷" in texto
    assert "→ Buenos Aires" not in texto


def test_origem_conhecida_aparece_para_denunciar_que_nao_sai_de_sp():
    # A regra de origem aceita origem ausente, entao quando o post declara GIG
    # o alerta precisa mostrar, senao parece deal de Sao Paulo.
    texto = formatar(voo(origem="GIG", destino="EZE", preco_brl=307), ["Firehose"])
    assert "Rio de Janeiro 🇧🇷 → Buenos Aires 🇦🇷" in texto


def test_cabine_premium_aparece_e_economica_nao():
    assert "executiva" in formatar(voo(destino="MIA", cabine="executiva", milhas=60000), ["R"])
    assert "economica" not in formatar(voo(destino="MIA", cabine="economica", milhas=60000), ["R"])


def test_voo_so_com_milhas_nao_inventa_reais():
    texto = formatar(voo(destino="NRT", milhas=60000, programa="Smiles"), ["R"])
    assert "R$" not in texto
    assert "60k Smiles" in texto


def test_promo_mostra_bonus():
    deal = Deal(
        kind="promo", titulo="Até 100% de bônus", url="https://x.com/a",
        fonte="Melhores Destinos", dedup_key="k", programa="Livelo", bonus_pct=100,
    )
    texto = formatar(deal, ["Bônus"])
    assert "Livelo" in texto and "100% de bônus" in texto


def test_promo_sem_percentual_cai_no_titulo():
    deal = Deal(
        kind="promo", titulo="Shopping Smiles em dobro", url="https://x.com/a",
        fonte="F", dedup_key="k", programa="Smiles",
    )
    assert "Shopping Smiles em dobro" in formatar(deal, ["R"])


def test_link_e_a_ultima_linha_e_leva_ao_artigo():
    texto = formatar(voo(destino="MIA", milhas=60000), ["R"])
    assert texto.split("\n")[-1] == '<a href="https://x.com/a">Fonte →</a>'


def test_nao_repete_as_regras_no_alerta():
    # Ruido: o usuario quer identificar a oportunidade, nao auditar o filtro.
    texto = formatar(voo(destino="MIA", milhas=60000), ["Executiva de SP", "Firehose"])
    assert "Firehose" not in texto


def test_destino_desconhecido_nao_quebra():
    assert "Destino não identificado" in formatar(voo(preco_brl=500), ["R"])
