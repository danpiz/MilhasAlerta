import pytest

from milhasalerta.models import Deal
from milhasalerta.rules import casa, regras_que_casam

EXECUTIVA = {
    "nome": "Executiva de SP para o exterior",
    "kind": "voo",
    "origens": ["GRU", "VCP", "CGH", "SAO"],
    "cabines": ["executiva", "primeira"],
    "max_milhas": 120000,
    "max_preco_brl": 6000,
}
BARATA = {
    "nome": "Passagem barata saindo de SP",
    "kind": "voo",
    "origens": ["GRU", "VCP", "CGH", "SAO"],
    "max_preco_brl": 1500,
}
FIREHOSE = {
    "nome": "Firehose",
    "kind": "voo",
    "origens": ["GRU", "VCP", "CGH", "SAO"],
}
PROMO = {
    "nome": "Bônus de transferência",
    "kind": "promo",
    "programas": ["Smiles", "LATAM Pass", "Azul Fidelidade", "Livelo"],
    "min_bonus_pct": 80,
}
TODAS = [EXECUTIVA, BARATA, FIREHOSE, PROMO]


def voo(**kwargs) -> Deal:
    base = dict(
        kind="voo", titulo="t", url="u", fonte="f", dedup_key="u", origem="GRU"
    )
    return Deal(**{**base, **kwargs})


def test_executiva_barata_casa_regra_restrita_e_firehose():
    deal = voo(cabine="executiva", milhas=60000, destino="MIA")
    assert regras_que_casam(TODAS, deal) == [EXECUTIVA["nome"], FIREHOSE["nome"]]


def test_economica_cara_casa_so_o_firehose():
    deal = voo(cabine="economica", milhas=300000, destino="MIA")
    assert regras_que_casam(TODAS, deal) == [FIREHOSE["nome"]]


def test_deal_so_em_reais_nao_e_descartado_por_limite_de_milhas():
    # O post não afirma milhas; max_milhas não pode rejeitá-lo.
    deal = voo(preco_brl=593, destino="LIM")
    assert casa(BARATA, deal)


def test_ou_entre_milhas_e_reais_aceita_pelo_lado_bom():
    # Estoura as milhas com folga, mas R$ 300 satisfaz o outro limite.
    deal = voo(cabine="executiva", milhas=900000, preco_brl=300, destino="EZE")
    assert casa(EXECUTIVA, deal)


def test_ambos_os_lados_ruins_rejeita():
    deal = voo(cabine="executiva", milhas=900000, preco_brl=90000, destino="NRT")
    assert not casa(EXECUTIVA, deal)


def test_cabine_desconhecida_nao_casa_regra_de_executiva():
    # Sem isso, uma econômica de R$ 150 vira "Executiva de SP para o exterior".
    deal = voo(cabine=None, preco_brl=150, destino="MIA")
    assert not casa(EXECUTIVA, deal)
    assert regras_que_casam(TODAS, deal) == [BARATA["nome"], FIREHOSE["nome"]]


def test_destino_desconhecido_nao_casa_regra_com_destinos():
    regra = {**FIREHOSE, "destinos": ["NRT", "HND"]}
    assert not casa(regra, voo(destino=None, preco_brl=500))


def test_programa_desconhecido_nao_casa_regra_de_promo():
    deal = Deal(
        kind="promo", titulo="t", url="u", fonte="f", dedup_key="u",
        programa=None, bonus_pct=100,
    )
    assert not casa(PROMO, deal)


def test_barra_de_preco_exige_prova():
    # Só tem milhas; a regra "Passagem barata" não pode disparar sem preço em reais.
    deal = voo(milhas=60000, destino="MIA")
    assert not casa(BARATA, deal)


def test_promo_sem_percentual_nao_satisfaz_minimo():
    deal = Deal(
        kind="promo", titulo="t", url="u", fonte="f", dedup_key="u",
        programa="Livelo", bonus_pct=None,
    )
    assert not casa(PROMO, deal)


def test_origem_desconhecida_passa_no_filtro_de_origem():
    # Portais raramente dizem a origem; dado ausente não pode rejeitar.
    deal = voo(origem=None, preco_brl=593, destino="LIM")
    assert casa(FIREHOSE, deal)


def test_origem_conhecida_e_diferente_rejeita():
    deal = voo(origem="REC", preco_brl=500, destino="LIM")
    assert not casa(FIREHOSE, deal)


def test_kind_diferente_nunca_casa():
    deal = voo(cabine="executiva", milhas=60000)
    assert not casa(PROMO, deal)


def test_promo_com_bonus_suficiente():
    deal = Deal(
        kind="promo", titulo="t", url="u", fonte="f", dedup_key="u",
        programa="Livelo", bonus_pct=100,
    )
    assert casa(PROMO, deal)


def test_promo_com_bonus_abaixo_do_minimo_rejeita():
    deal = Deal(
        kind="promo", titulo="t", url="u", fonte="f", dedup_key="u",
        programa="Livelo", bonus_pct=30,
    )
    assert not casa(PROMO, deal)


def test_regra_desabilitada_nunca_casa():
    regra = {**FIREHOSE, "enabled": False}
    assert not casa(regra, voo(preco_brl=100))


@pytest.mark.parametrize("programa", ["latam pass", "LATAM PASS", " Latam Pass "])
def test_programa_casa_sem_diferenciar_caixa_ou_espaco(programa):
    deal = Deal(
        kind="promo", titulo="t", url="u", fonte="f", dedup_key="u",
        programa=programa, bonus_pct=90,
    )
    assert casa(PROMO, deal)
