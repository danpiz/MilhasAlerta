import pytest

from milhasalerta.airports import describe


@pytest.mark.parametrize(
    "iata,esperado",
    [
        ("GRU", "São Paulo 🇧🇷"),
        ("gru", "São Paulo 🇧🇷"),
        ("LIM", "Lima 🇵🇪"),
        ("EZE", "Buenos Aires 🇦🇷"),  # o pacote diria "Ezeiza"
        ("CDG", "Paris 🇫🇷"),
        ("LIS", "Lisboa 🇵🇹"),
    ],
)
def test_nome_em_portugues_com_bandeira(iata, esperado):
    assert describe(iata) == esperado


@pytest.mark.parametrize(
    "iata,esperado",
    [
        ("VIE", "Viena 🇦🇹"),      # o pacote diria "Vienna"
        ("CPH", "Copenhague 🇩🇰"),  # "Copenhagen"
        ("ICN", "Seul 🇰🇷"),        # "Seoul"
        ("PEK", "Pequim 🇨🇳"),      # "Beijing"
    ],
)
def test_traduz_nome_em_ingles(iata, esperado):
    assert describe(iata) == esperado


@pytest.mark.parametrize(
    "iata,esperado",
    [
        ("YUL", "Montreal 🇨🇦"),    # o pacote diria "Dorval", o suburbio
        ("YVR", "Vancouver 🇨🇦"),   # "Richmond"
        ("AUA", "Aruba 🇦🇼"),       # "Oranjestad"
    ],
)
def test_corrige_cidade_errada_do_pacote(iata, esperado):
    assert describe(iata) == esperado


def test_aeroporto_fora_do_mapa_usa_o_pacote():
    # Não está em NOMES; vem do airportsdata com a bandeira certa.
    assert describe("BKK") == "Bangkok 🇹🇭"


def test_codigo_desconhecido_volta_como_veio():
    assert describe("ZZZ") == "ZZZ"


# --- codigos de metropole -----------------------------------------------------
# Nao sao aeroportos, entao nao existem no airportsdata e describe() devolvia o
# codigo cru: o alerta saiu com "✈️ NYC", sem nome nem bandeira. SAO importa
# duas vezes -- e a origem padrao do projeto.

@pytest.mark.parametrize("codigo,esperado", [
    ("NYC", "Nova York 🇺🇸"), ("SAO", "São Paulo 🇧🇷"),
    ("LON", "Londres 🇬🇧"), ("MIL", "Milão 🇮🇹"), ("RIO", "Rio de Janeiro 🇧🇷"),
])
def test_metropole_vira_cidade_com_bandeira(codigo, esperado):
    assert describe(codigo) == esperado


def test_aeroporto_de_verdade_tem_prioridade_sobre_metropole():
    assert describe("JFK") == "Nova York 🇺🇸"


def test_codigo_desconhecido_ainda_volta_como_veio():
    assert describe("ZZZ") == "ZZZ"
