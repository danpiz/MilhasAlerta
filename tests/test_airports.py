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


def test_aeroporto_fora_do_mapa_usa_o_pacote():
    # Não está em NOMES; vem do airportsdata com a bandeira certa.
    assert describe("BKK") == "Bangkok 🇹🇭"


def test_codigo_desconhecido_volta_como_veio():
    assert describe("ZZZ") == "ZZZ"
