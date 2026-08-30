from datetime import datetime, timedelta, timezone

from milhasalerta.historico import (
    MINIMO_OBSERVACOES,
    chave,
    normal,
    podar,
    queda_pct,
    registrar,
)

AGORA = datetime.now(timezone.utc)


def serie_com(precos, k="GRU-LIS-2026-10-13"):
    s = {}
    for p in precos:
        registrar(s, k, p)
    return s, k


def test_sem_amostra_suficiente_nao_ha_normal():
    s, k = serie_com([2000] * (MINIMO_OBSERVACOES - 1))
    assert normal(s, k) is None


def test_normal_aparece_ao_atingir_o_minimo():
    s, k = serie_com([2000] * MINIMO_OBSERVACOES)
    assert normal(s, k) == 2000


def test_usa_mediana_e_nao_media():
    # Uma tarifa absurda distorceria a media e criaria um normal inexistente.
    s, k = serie_com([2000, 2000, 2000, 2000, 40000])
    assert normal(s, k) == 2000


def test_queda_medida_contra_o_normal():
    s, k = serie_com([2000] * 5)
    assert queda_pct(s, k, 1200) == 40


def test_preco_acima_do_normal_nao_e_queda():
    s, k = serie_com([2000] * 5)
    assert queda_pct(s, k, 2500) is None


def test_sem_historico_nao_inventa_queda():
    # Barra de qualidade exige prova: antes de aprender, nao dispara.
    s, k = serie_com([2000])
    assert queda_pct(s, k, 100) is None


def test_poda_observacao_alem_da_retencao():
    k = chave("GRU", "LIS", "2026-10-13")
    s = {k: [
        [(AGORA - timedelta(days=90)).isoformat(), 2000],
        [(AGORA - timedelta(days=3)).isoformat(), 2100],
    ]}
    assert len(podar(s)[k]) == 1


def test_poda_descarta_serie_que_ficou_vazia():
    k = chave("GRU", "LIS", "2026-10-13")
    s = {k: [[(AGORA - timedelta(days=90)).isoformat(), 2000]]}
    assert podar(s) == {}


def test_chave_separa_rotas_e_datas():
    assert chave("GRU", "LIS", "2026-10-13") != chave("GRU", "LIS", "2026-11-13")
    assert chave("GRU", "LIS", "2026-10-13") != chave("GRU", "CDG", "2026-10-13")


# --- a chave agrupa por mes ---------------------------------------------------
# Medido em 30/08/2026: dos 221 trechos da serie, nenhum tinha as 5 observacoes
# que normal() exige. Rota sem janela amostra "hoje + 30 dias", entao a data
# anda todo dia e a chave do dia era abandonada antes de acumular.

def test_chave_agrupa_o_mes_inteiro():
    assert chave("GRU", "LIS", "2026-12-05") == chave("GRU", "LIS", "2026-12-28")


def test_chave_separa_meses_diferentes():
    assert chave("GRU", "LIS", "2026-12-28") != chave("GRU", "LIS", "2027-01-05")


def test_chave_separa_trechos():
    assert chave("GRU", "LIS", "2026-12-05") != chave("GRU", "CDG", "2026-12-05")


def test_data_rolante_acumula_ate_virar_normal():
    """O caso real: a data anda um dia por dia e antes nada acumulava."""
    from datetime import date, timedelta
    s = {}
    base = date(2026, 12, 1)
    for i in range(MINIMO_OBSERVACOES):
        k = chave("GRU", "LIS", (base + timedelta(days=i)).isoformat())
        registrar(s, k, 5000)
    assert len(s) == 1
    assert normal(s, k) == 5000
