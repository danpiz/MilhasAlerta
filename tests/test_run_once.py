"""Exercita run_once inteiro com fontes dubles.

Existe porque um NameError em run_once chegou a producao: todos os modulos
tinham teste, mas ninguem executava a funcao que os costura. Falha de
integracao nao aparece em teste de unidade.
"""

import json

import pytest

import main
from milhasalerta.models import Deal


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
alertas:
  - nome: Barato de SP
    kind: voo
    origens: [GRU]
    max_preco_brl: 3000
rotas:
  - nome: Europa
    origens: [GRU]
    destinos: [LIS]
    max_preco_brl: 5000
milheiro:
  padrao: 18.0
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "CONFIG", config)
    monkeypatch.setattr(main, "ESTADO", tmp_path / "seen.json")
    monkeypatch.setattr(main, "Extractor", lambda: (lambda post: None))

    enviados = []
    monkeypatch.setattr(main.telegram, "enviar", lambda texto: enviados.append(texto))
    return tmp_path, enviados


def com_fonte(monkeypatch, deals):
    class Fonte:
        nome = "duble"

        def fetch(self):
            return list(deals)

    monkeypatch.setattr(main, "get_sources", lambda *a, **k: [Fonte()])


def voo(**kw):
    base = dict(kind="voo", titulo="t", url="u", fonte="duble", dedup_key="k1", origem="GRU")
    return Deal(**{**base, **kw})


def test_deal_que_casa_regra_vira_alerta(ambiente, monkeypatch):
    _, enviados = ambiente
    com_fonte(monkeypatch, [voo(destino="LIS", preco_brl=2000)])
    assert main.run_once() == 0
    assert len(enviados) == 1
    assert "Lisboa" in enviados[0]


def test_rota_sozinha_dispara_alerta(ambiente, monkeypatch):
    """Rotas entram no motor de regras junto com alertas, e sem kind explicito
    casa() rejeitava todas -- nenhum alerta de rota jamais sairia.

    R$ 4.000 estoura o teto de "Barato de SP" (3.000), entao so a rota
    "Europa" (5.000) pode ter deixado passar."""
    _, enviados = ambiente
    com_fonte(monkeypatch, [voo(destino="LIS", preco_brl=4000, dedup_key="k2")])
    main.run_once()
    assert len(enviados) == 1
    assert "Lisboa" in enviados[0]


def test_deal_fora_das_regras_nao_alerta(ambiente, monkeypatch):
    _, enviados = ambiente
    com_fonte(monkeypatch, [voo(destino="LIS", preco_brl=90000)])
    main.run_once()
    assert enviados == []


def test_segunda_execucao_nao_repete(ambiente, monkeypatch):
    _, enviados = ambiente
    com_fonte(monkeypatch, [voo(destino="LIS", preco_brl=2000)])
    main.run_once()
    main.run_once()
    assert len(enviados) == 1


def test_milheiro_e_aplicado_antes_das_regras(ambiente, monkeypatch, tmp_path):
    """max_custo_brl compara contra as milhas convertidas, entao a conversao
    precisa acontecer ANTES de casar as regras."""
    _, enviados = ambiente
    (tmp_path / "config.yaml").write_text(
        """
alertas:
  - nome: Milhas baratas
    kind: voo
    origens: [GRU]
    max_custo_brl: 2000
milheiro:
  padrao: 18.0
""",
        encoding="utf-8",
    )
    com_fonte(monkeypatch, [voo(destino="LIS", milhas=100000, programa="Smiles")])
    main.run_once()
    assert "≈R$ 1.800" in enviados[0]


def test_fonte_quebrada_nao_derruba_a_execucao(ambiente, monkeypatch):
    _, enviados = ambiente

    class Quebrada:
        nome = "quebrada"

        def fetch(self):
            raise RuntimeError("fora do ar")

    class Boa:
        nome = "boa"

        def fetch(self):
            return [voo(destino="LIS", preco_brl=2000)]

    monkeypatch.setattr(main, "get_sources", lambda *a, **k: [Quebrada(), Boa()])
    assert main.run_once() == 0
    assert len(enviados) == 1


def test_seed_marca_sem_alertar(ambiente, monkeypatch):
    tmp, enviados = ambiente
    com_fonte(monkeypatch, [voo(destino="LIS", preco_brl=2000)])
    main.run_once(seed=True)
    assert enviados == []
    assert json.loads((tmp / "seen.json").read_text())["seen"]


def test_dry_run_nao_envia(ambiente, monkeypatch):
    _, enviados = ambiente
    com_fonte(monkeypatch, [voo(destino="LIS", preco_brl=2000)])
    assert main.run_once(dry_run=True) == 0
    assert enviados == []
