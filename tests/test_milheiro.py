from milhasalerta.milheiro import cotacao, custo_efetivo
from milhasalerta.models import Deal
from milhasalerta.rules import casa
from milhasalerta.telegram import formatar

TABELA = {"padrao": 18.00, "Smiles": 16.50, "LATAM Pass": 19.00}


def test_usa_a_cotacao_do_programa():
    assert custo_efetivo(24000, "LATAM Pass", TABELA) == 456  # 24 * 19


def test_programa_sem_entrada_cai_no_padrao():
    assert custo_efetivo(10000, "Flying Blue", TABELA) == 180  # 10 * 18


def test_programa_casa_sem_diferenciar_caixa():
    assert cotacao("smiles", TABELA) == 16.50
    assert cotacao("  SMILES  ", TABELA) == 16.50


def test_sem_milhas_nao_ha_conversao():
    assert custo_efetivo(None, "Smiles", TABELA) is None


def test_sem_tabela_configurada_nao_ha_conversao():
    assert custo_efetivo(24000, "Smiles", {}) is None


def test_sem_padrao_e_programa_desconhecido_nao_inventa():
    assert custo_efetivo(24000, "Qantas", {"Smiles": 16.5}) is None


def test_alerta_mostra_a_conversao_para_comparar_de_bate_pronto():
    deal = Deal(
        kind="voo", titulo="t", url="https://x.com/a", fonte="F", dedup_key="k",
        destino="LIM", programa="LATAM Pass", preco_brl=593, milhas=24000,
        custo_efetivo_brl=456,
    )
    texto = formatar(deal, ["R"])
    # Os dois lados na mesma linha: 456 < 593, logo compensa emitir com milhas.
    assert "R$ 593 ou 24k LATAM Pass (≈R$ 456)" in texto


def test_alerta_sem_conversao_nao_mostra_parenteses():
    deal = Deal(
        kind="voo", titulo="t", url="u", fonte="F", dedup_key="k",
        destino="LIM", milhas=24000,
    )
    assert "≈" not in formatar(deal, ["R"])


REGRA = {"nome": "Barato", "kind": "voo", "max_custo_brl": 500}


def test_max_custo_brl_casa_pelas_milhas_convertidas():
    # So tem milhas; sem a conversao esta regra nunca dispararia.
    deal = Deal(
        kind="voo", titulo="t", url="u", fonte="F", dedup_key="k",
        destino="LIM", milhas=24000, custo_efetivo_brl=456,
    )
    assert casa(REGRA, deal)


def test_max_custo_brl_casa_pelo_dinheiro():
    deal = Deal(
        kind="voo", titulo="t", url="u", fonte="F", dedup_key="k",
        destino="LIM", preco_brl=300,
    )
    assert casa(REGRA, deal)


def test_max_custo_brl_rejeita_quando_os_dois_lados_estouram():
    deal = Deal(
        kind="voo", titulo="t", url="u", fonte="F", dedup_key="k",
        destino="LIM", preco_brl=900, milhas=60000, custo_efetivo_brl=1140,
    )
    assert not casa(REGRA, deal)


def test_max_custo_brl_sem_conversao_nem_dinheiro_nao_casa():
    # Barra de qualidade exige prova.
    deal = Deal(
        kind="voo", titulo="t", url="u", fonte="F", dedup_key="k",
        destino="LIM", milhas=24000,
    )
    assert not casa(REGRA, deal)
