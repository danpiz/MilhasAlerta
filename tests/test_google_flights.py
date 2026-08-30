import pytest

from milhasalerta.regioes import expandir
from milhasalerta.sources.google_flights import GoogleFlightsSource, datas_amostradas


def fonte(rotas, precos, historico=None, **kw):
    """Fonte com a consulta ao Google trocada por uma tabela fixa."""
    vistos = kw.pop("vistos", set())
    s = GoogleFlightsSource(
        rotas=rotas,
        vistas=lambda prefixo: [k for k in vistos if k.startswith(prefixo)],
        observar=lambda o, d, dia, p: (historico or {}).get(d),
        **kw,
    )
    s._consultar = lambda o, d, dia, volta=None: precos.get(d, [])
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
        rotas=ROTA_TETO, vistas=lambda prefixo: [],
        observar=lambda o, d, dia, p: observados.append((d, p)), amostras=1,
    )
    s._consultar = lambda o, d, dia, volta=None: [9000]
    s.fetch()
    assert observados == [("LIS", 9000), ("CDG", 9000)]


def test_rota_desabilitada_nao_consulta():
    rota = [{**ROTA_TETO[0], "enabled": False}]
    consultas = []
    s = fonte(rota, {}, amostras=1)
    s._consultar = lambda o, d, dia, volta=None: consultas.append(d) or []
    s.fetch()
    assert consultas == []


def test_falha_numa_rota_nao_derruba_as_outras():
    def consultar(o, d, dia, volta=None):
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
    ja_alertado = {"gf:GRU-LIS-X-:2000"}
    s = fonte(ROTA_TETO, {"LIS": [2000]}, amostras=1, vistos=ja_alertado)
    assert s.fetch() == []

    # Mas uma queda adicional e noticia nova.
    s2 = fonte(ROTA_TETO, {"LIS": [1800]}, amostras=1, vistos=ja_alertado)
    assert [d.preco_brl for d in s2.fetch()] == [1800]


def test_ida_e_volta_consulta_as_duas_pernas():
    rota = [{"nome": "Europa", "origens": ["GRU"], "destinos": ["LIS"],
             "ida_e_volta": True, "dias_de_viagem": 12, "max_preco_brl": 9999}]
    chamadas = []
    s = fonte(rota, {}, amostras=1)
    s._consultar = lambda o, d, dia, volta=None: chamadas.append((dia, volta)) or [4000]
    deals = s.fetch()
    (ida, volta), = chamadas
    from datetime import date
    assert (date.fromisoformat(volta) - date.fromisoformat(ida)).days == 12
    assert deals[0].data == ida and deals[0].data_volta == volta


def test_so_ida_nao_manda_perna_de_volta():
    chamadas = []
    s = fonte(ROTA_TETO, {}, amostras=1)
    s._consultar = lambda o, d, dia, volta=None: chamadas.append(volta) or [2000]
    s.fetch()
    assert set(chamadas) == {None}


def test_a_partir_de_fixa_a_janela():
    from milhasalerta.sources.google_flights import datas_amostradas
    datas = datas_amostradas(3, inicio="2027-01-05")
    assert datas[0] == "2027-01-05"
    assert len(datas) == 3


def test_ida_e_volta_tem_chave_distinta_da_so_ida():
    """Senao o preco de ida e volta suprimiria o alerta de so-ida, ou vice-versa."""
    rota_iv = [{"nome": "R", "origens": ["GRU"], "destinos": ["LIS"],
                "ida_e_volta": True, "dias_de_viagem": 12, "max_preco_brl": 9999}]
    s1 = fonte(rota_iv, {}, amostras=1)
    s1._consultar = lambda o, d, dia, volta=None: [4000]
    s2 = fonte([{**rota_iv[0], "ida_e_volta": False}], {}, amostras=1)
    s2._consultar = lambda o, d, dia, volta=None: [4000]
    assert s1.fetch()[0].dedup_key != s2.fetch()[0].dedup_key


def test_conta_falhas_para_bloqueio_nao_passar_por_silencio(capsys):
    """Scraper que emudece parece 'nenhum deal hoje'. A contagem e o unico
    sinal de que o Google bloqueou."""
    def consultar(o, d, dia, volta=None):
        raise RuntimeError("bloqueado")

    s = fonte(ROTA_TETO, {}, amostras=1)
    s._consultar = consultar
    assert s.fetch() == []
    assert (s.falhas, s.consultas) == (2, 2)
    assert "2/2 consultas falharam" in capsys.readouterr().err


# --- teto acima do preco normal: a rota inteira vira alerta -------------------
# Reproduz o incidente de 30/08/2026: "/alerta Europa ... ate R$ 6.000" com o
# trecho custando 4.200-5.700 fez as 14x6 combinacoes passarem no filtro e
# render 87 mensagens de uma vez.

ROTA_LARGA = [
    {
        "nome": "Europa dezembro",
        "origens": ["GRU"],
        "destinos": ["LIS", "CDG", "FRA", "MAD", "BCN"],
        "max_preco_brl": 6000,
    }
]
MERCADO = {"LIS": [4200], "CDG": [5500], "FRA": [4900], "MAD": [4400], "BCN": [5100]}


def test_teto_generoso_nao_alerta_a_rota_inteira():
    s = fonte(ROTA_LARGA, MERCADO, amostras=6, limite_por_rota=3)
    assert len(s.fetch()) == 3


def test_corta_pelas_mais_baratas():
    s = fonte(ROTA_LARGA, MERCADO, amostras=1, limite_por_rota=2)
    assert [d.destino for d in s.fetch()] == ["LIS", "MAD"]


def test_limite_vale_por_rota_e_nao_no_total():
    duas = ROTA_LARGA + [
        {"nome": "Vizinhos", "origens": ["GRU"], "destinos": ["SCL"], "max_preco_brl": 900}
    ]
    s = fonte(duas, {**MERCADO, "SCL": [745]}, amostras=1, limite_por_rota=2)
    # A rota barata nao pode ser engolida pelo corte da rota cara.
    assert [d.destino for d in s.fetch()] == ["LIS", "MAD", "SCL"]


def test_rota_bem_calibrada_nao_e_afetada():
    s = fonte(ROTA_TETO, {"LIS": [2000], "CDG": [4000]}, amostras=1, limite_por_rota=3)
    assert [d.destino for d in s.fetch()] == ["LIS"]


# --- realerta so quando fica mais barato --------------------------------------
# Reproduz o segundo defeito de 30/08/2026: o preco entra na chave, entao uma
# ALTA virava chave nova e realertava. Medido: GRU-AMS 29/10 a R$ 4330 e, dez
# horas depois, o mesmo trecho a R$ 4450.

ROTA_UM = [{"nome": "Um", "origens": ["GRU"], "destinos": ["AMS"], "max_preco_brl": 5000}]


def alertado(preco: int) -> set:
    return {f"gf:GRU-AMS-{datas_amostradas(1)[0]}-:{preco}"}


def test_nao_realerta_quando_o_preco_sobe():
    s = fonte(ROTA_UM, {"AMS": [4450]}, amostras=1, vistos=alertado(4330))
    assert s.fetch() == []


def test_nao_realerta_o_mesmo_preco():
    s = fonte(ROTA_UM, {"AMS": [4330]}, amostras=1, vistos=alertado(4330))
    assert s.fetch() == []


def test_realerta_quando_fica_mais_barato():
    s = fonte(ROTA_UM, {"AMS": [4100]}, amostras=1, vistos=alertado(4330))
    assert [d.preco_brl for d in s.fetch()] == [4100]


def test_compara_com_o_menor_ja_alertado_nao_com_o_ultimo():
    """Alertei 4330 e depois 4100; 4200 e alta em relacao ao menor."""
    s = fonte(ROTA_UM, {"AMS": [4200]}, amostras=1, vistos=alertado(4330) | alertado(4100))
    assert s.fetch() == []


def test_trecho_nunca_alertado_passa():
    s = fonte(ROTA_UM, {"AMS": [4900]}, amostras=1, vistos=alertado(4330) - alertado(4330))
    assert [d.preco_brl for d in s.fetch()] == [4900]


def test_nao_confunde_trechos_com_prefixo_parecido():
    """AMS-2026-01-01 nao pode herdar o piso de AMS-2026-01-01x."""
    dia = datas_amostradas(1)[0]
    s = fonte(ROTA_UM, {"AMS": [4900]}, amostras=1,
              vistos={f"gf:GRU-AMS-{dia}-2026-12-31:4000"})
    assert [d.preco_brl for d in s.fetch()] == [4900]


# --- cotacao de uma rota na criacao do alerta ---------------------------------

import milhasalerta.sources.google_flights as gf

ROTA_COTAR = {
    "origens": ["GRU"],
    "destinos": ["LIS", "OPO", "MAD", "BCN", "CDG", "FCO", "LHR", "AMS"],
    "ida_e_volta": True,
    "dias_de_viagem": 12,
}


def falso_consultar(monkeypatch, tabela, registro=None):
    def _c(origem, destino, dia, volta=None, cabine="economy"):
        if registro is not None:
            registro.append((destino, dia, volta))
        valor = tabela.get(destino)
        if valor is None:
            raise RuntimeError("destino fora do ar")
        return valor
    monkeypatch.setattr(gf, "consultar", _c)


def test_cotacao_limita_destinos_e_datas(monkeypatch):
    chamadas = []
    falso_consultar(monkeypatch, {d: [5000] for d in ROTA_COTAR["destinos"]}, chamadas)
    precos = gf.cotar(ROTA_COTAR, max_destinos=6, max_datas=3)
    assert len(precos) == 6
    assert len(chamadas) == 18  # 6 destinos x 3 datas, nao as 84 da varredura


def test_cotacao_devolve_o_menor_entre_as_datas(monkeypatch):
    falso_consultar(monkeypatch, {"LIS": [5200, 4800]})
    assert gf.cotar({**ROTA_COTAR, "destinos": ["LIS"]}, max_datas=2) == {"LIS": 4800}


def test_destino_que_falha_sai_sem_derrubar_os_outros(monkeypatch):
    falso_consultar(monkeypatch, {"LIS": [4200]})  # OPO e MAD levantam
    precos = gf.cotar({**ROTA_COTAR, "destinos": ["LIS", "OPO", "MAD"]}, max_datas=1)
    assert precos == {"LIS": 4200}


def test_cotacao_de_ida_e_volta_consulta_a_volta(monkeypatch):
    chamadas = []
    falso_consultar(monkeypatch, {"LIS": [4200]}, chamadas)
    gf.cotar({**ROTA_COTAR, "destinos": ["LIS"]}, max_datas=1)
    _, ida, volta = chamadas[0]
    assert volta == gf._somar_dias(ida, 12)


def test_cotacao_de_so_ida_nao_tem_volta(monkeypatch):
    chamadas = []
    falso_consultar(monkeypatch, {"LIS": [2100]}, chamadas)
    gf.cotar({**ROTA_COTAR, "destinos": ["LIS"], "ida_e_volta": False}, max_datas=1)
    assert chamadas[0][2] is None
