import pytest

from milhasalerta.regioes import expandir
from milhasalerta.sources.google_flights import GoogleFlightsSource, datas_amostradas


def fonte(rotas, precos, historico=None, **kw):
    """Fonte com a consulta ao Google trocada por uma tabela fixa."""
    vistos = kw.pop("vistos", set())
    s = GoogleFlightsSource(
        rotas=rotas,
        ja_visto=lambda k: k in vistos,
        observar=lambda o, d, dia, p: (historico or {}).get(d),
        **kw,
    )
    s._consultar = lambda o, d, dia: precos.get(d, [])
    return s


ROTA_TETO = [{"nome": "Europa", "origens": ["GRU"], "destinos": ["LIS", "CDG"], "max_preco_brl": 2500}]


def test_expande_regiao_em_aeroportos():
    europa = expandir(["europa"])
    assert "LIS" in europa and "CDG" in europa and len(europa) > 10


def test_mistura_regiao_com_codigo_solto():
    r = expandir(["america_do_sul", "NRT"])
    assert "EZE" in r and "NRT" in r


def test_nao_repete_aeroporto_em_regioes_sobrepostas():
    assert len(expandir(["europa", "europa", "LIS"])) == len(expandir(["europa"]))


def test_amostra_uma_data_por_mes():
    datas = datas_amostradas(6)
    assert len(datas) == 6
    assert len(set(datas)) == 6


def test_alerta_quando_abaixo_do_teto():
    s = fonte(ROTA_TETO, {"LIS": [2000, 2400], "CDG": [4000]}, amostras=1)
    deals = s.fetch()
    assert [d.destino for d in deals] == ["LIS"]
    assert deals[0].preco_brl == 2000  # o menor da lista


def test_nao_alerta_preco_comum():
    s = fonte(ROTA_TETO, {"LIS": [9000], "CDG": [9000]}, amostras=1)
    assert s.fetch() == []


def test_alerta_por_queda_mesmo_acima_do_teto():
    rota = [{"nome": "Tokyo", "origens": ["GRU"], "destinos": ["NRT"], "min_queda_pct": 25}]
    s = fonte(rota, {"NRT": [8000]}, historico={"NRT": 40}, amostras=1)
    deals = s.fetch()
    assert len(deals) == 1
    assert deals[0].queda_pct == 40
    assert "40% abaixo do normal" in deals[0].titulo


def test_queda_insuficiente_nao_alerta():
    rota = [{"nome": "Tokyo", "origens": ["GRU"], "destinos": ["NRT"], "min_queda_pct": 25}]
    s = fonte(rota, {"NRT": [8000]}, historico={"NRT": 10}, amostras=1)
    assert s.fetch() == []


def test_observa_o_preco_mesmo_sem_alertar():
    """Sem observar preco comum o historico nunca aprende o que e normal."""
    observados = []
    s = GoogleFlightsSource(
        rotas=ROTA_TETO, ja_visto=lambda k: False,
        observar=lambda o, d, dia, p: observados.append((d, p)), amostras=1,
    )
    s._consultar = lambda o, d, dia: [9000]
    s.fetch()
    assert observados == [("LIS", 9000), ("CDG", 9000)]


def test_rota_desabilitada_nao_consulta():
    rota = [{**ROTA_TETO[0], "enabled": False}]
    consultas = []
    s = fonte(rota, {}, amostras=1)
    s._consultar = lambda o, d, dia: consultas.append(d) or []
    s.fetch()
    assert consultas == []


def test_falha_numa_rota_nao_derruba_as_outras():
    def consultar(o, d, dia):
        if d == "LIS":
            raise RuntimeError("google bloqueou")
        return [2000]

    s = fonte(ROTA_TETO, {}, amostras=1)
    s._consultar = consultar
    assert [d.destino for d in s.fetch()] == ["CDG"]


def test_mesmo_preco_nao_realerta(monkeypatch):
    monkeypatch.setattr(
        "milhasalerta.sources.google_flights.datas_amostradas", lambda n, **k: ["X"]
    )
    ja_alertado = {"gf:GRU-LIS-X:2000"}
    s = fonte(ROTA_TETO, {"LIS": [2000]}, amostras=1, vistos=ja_alertado)
    assert s.fetch() == []

    # Mas uma queda adicional e noticia nova.
    s2 = fonte(ROTA_TETO, {"LIS": [1800]}, amostras=1, vistos=ja_alertado)
    assert [d.preco_brl for d in s2.fetch()] == [1800]
