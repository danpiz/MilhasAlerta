from types import SimpleNamespace

import pytest

from milhasalerta.comandos import LIMITE_ALERTAS, RotaPedida, processar

PORTUGAL = {
    "nome": "Portugal em janeiro de 2027",
    "origens": ["GRU"],
    "destinos": ["LIS", "OPO"],
    "ida_e_volta": True,
    "dias_de_viagem": 12,
    "a_partir_de": "2027-01-05",
    "max_preco_brl": None,
    "cabine": "economica",
    "min_queda_pct": 25,
    "enabled": True,
}


def cliente(rota: RotaPedida):
    return SimpleNamespace(
        messages=SimpleNamespace(
            parse=lambda **kw: SimpleNamespace(parsed_output=rota)
        )
    )


def rota_pedida(**kw):
    base = dict(
        nome="Portugal em janeiro de 2027", origens=["GRU"], destinos=["LIS", "OPO"],
        a_partir_de="2027-01-05",
    )
    return RotaPedida(**{**base, **kw})


def test_texto_sem_barra_e_ignorado():
    alertas, resposta = processar("bom dia", [])
    assert (alertas, resposta) == ([], None)


def test_cria_alerta_a_partir_de_texto_livre():
    alertas, resposta = processar(
        "/alerta voos pra Portugal em janeiro de 2027 ida e volta economica",
        [], client=cliente(rota_pedida()),
    )
    assert len(alertas) == 1
    assert alertas[0]["destinos"] == ["LIS", "OPO"]
    assert alertas[0]["a_partir_de"] == "2027-01-05"
    assert "Monitorando" in resposta


def test_sem_teto_o_gatilho_vira_queda_relativa():
    """Rota sem teto e sem queda seria vigiada e nunca alertaria nada."""
    alertas, resposta = processar("/alerta Portugal", [], client=cliente(rota_pedida()))
    assert alertas[0]["min_queda_pct"] == 25
    assert "leva alguns dias" in resposta


def test_com_teto_nao_inventa_queda():
    alertas, _ = processar(
        "/alerta Portugal ate 4000 reais", [],
        client=cliente(rota_pedida(max_preco_brl=4000)),
    )
    assert alertas[0]["max_preco_brl"] == 4000
    assert "min_queda_pct" not in alertas[0]


def test_alerta_sem_texto_explica_como_usar():
    alertas, resposta = processar("/alerta", [])
    assert alertas == []
    assert "Exemplo" in resposta


def test_falha_de_interpretacao_nao_derruba():
    def explode(**kw):
        raise RuntimeError("modelo fora do ar")

    c = SimpleNamespace(messages=SimpleNamespace(parse=explode))
    alertas, resposta = processar("/alerta algo", [], client=c)
    assert alertas == []
    assert "Não entendi" in resposta


def test_listar_vazio():
    _, resposta = processar("/alertas", [])
    assert "Nenhum alerta ativo" in resposta


def test_listar_numera_para_o_remover():
    _, resposta = processar("/alertas", [PORTUGAL])
    assert "1." in resposta and "Portugal em janeiro de 2027" in resposta


def test_remover_pelo_numero():
    alertas, resposta = processar("/remover 1", [PORTUGAL])
    assert alertas == []
    assert "Removido" in resposta


@pytest.mark.parametrize("entrada", ["/remover", "/remover abc"])
def test_remover_sem_numero_valido(entrada):
    alertas, resposta = processar(entrada, [PORTUGAL])
    assert alertas == [PORTUGAL]
    assert "número" in resposta


def test_remover_indice_inexistente():
    alertas, resposta = processar("/remover 9", [PORTUGAL])
    assert alertas == [PORTUGAL]
    assert "Não existe" in resposta


def test_limite_de_alertas():
    cheios = [PORTUGAL] * LIMITE_ALERTAS
    alertas, resposta = processar("/alerta mais um", cheios, client=cliente(rota_pedida()))
    assert len(alertas) == LIMITE_ALERTAS
    assert "Limite" in resposta


def test_comando_desconhecido_mostra_ajuda():
    _, resposta = processar("/qualquercoisa", [])
    assert "/alerta" in resposta and "/remover" in resposta


def test_aceita_comando_com_mencao_ao_bot():
    _, resposta = processar("/alertas@AlertaMilhaxBot", [])
    assert "Nenhum alerta ativo" in resposta
