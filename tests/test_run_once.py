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
    # Sem isto o teste consome mensagens reais do bot: getUpdates avanca o
    # offset no servidor do Telegram e a mensagem some para valer.
    monkeypatch.setattr(main.telegram, "receber", lambda desde=None: [])
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


def test_run_once_monta_a_fonte_do_google(ambiente, monkeypatch):
    """A fonte de rota some em silencio se run_once nao passar tudo que ela exige.

    get_sources ignora o Google quando falta qualquer dependencia -- sem erro,
    sem log. O sintoma seria "nenhum alerta de rota", que e indistinguivel de
    "nao achei nada barato". Este teste e o que faz o esquecimento doer aqui.
    """
    from milhasalerta.sources.google_flights import GoogleFlightsSource

    montadas = []
    original = main.get_sources

    def espiar(config, **kw):
        sources = original(config, **kw)
        montadas.extend(type(s) for s in sources)
        return sources

    monkeypatch.setattr(main, "get_sources", espiar)
    monkeypatch.setattr(
        GoogleFlightsSource, "_consultar", lambda self, o, d, dia, volta=None: []
    )
    main.run_once()
    assert GoogleFlightsSource in montadas


@pytest.mark.parametrize("modo", ["dry_run", "seed"])
def test_dry_run_e_seed_nao_consomem_comandos(ambiente, monkeypatch, modo):
    """getUpdates avanca o offset no servidor: a mensagem some para valer.

    --dry-run ainda promete nao chamar rede, e --seed so marca backlog. Atender
    comandos em qualquer um dos dois consumiria mensagens de verdade, cotaria
    rotas no Google e responderia ao usuario.
    """
    def barrado(desde=None):
        raise AssertionError("leu comandos do Telegram")

    monkeypatch.setattr(main.telegram, "receber", barrado)
    main.run_once(**{modo: True})
