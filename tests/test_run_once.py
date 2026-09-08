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


def test_post_rejeitado_fica_marcado_no_estado(ambiente, monkeypatch):
    """Sem isto, o post que o extrator descarta e re-extraido em toda rodada.

    Custa uma chamada ao Haiku por rodada, por post, ate ele sair da janela de
    24h -- ~5 hoje, ~96 se o gatilho externo passar a 15 min. O run_once tem de
    entregar `marcar` ao get_sources, e o que a fonte marcar tem de sobreviver
    ao save() daquela mesma rodada.
    """
    tmp, _ = ambiente

    def espiar(config, **kw):
        assert "marcar" in kw, "run_once nao passou marcar ao get_sources"
        kw["marcar"]("post-descartado")   # e o que a fonte faz ao rejeitar
        return []

    monkeypatch.setattr(main, "get_sources", espiar)
    main.run_once()

    estado = json.loads((tmp / "seen.json").read_text(encoding="utf-8"))
    assert "post-descartado" in estado["seen"]


def test_resposta_de_comando_volta_para_o_chat_de_origem(ambiente, monkeypatch):
    """Comando dado num grupo tem de ser respondido no grupo.

    enviar() sem chat_id vai para TELEGRAM_CHAT_ID -- o destino dos alertas.
    Sem passar a origem, quem digitasse /alertas no grupo receberia a resposta
    no privado de outra pessoa.
    """
    enviados = []
    monkeypatch.setattr(main.telegram, "enviar",
                        lambda texto, chat_id=None: enviados.append(chat_id))
    monkeypatch.setattr(main.telegram, "receber", lambda desde=None: [
        {"update_id": 1, "message": {"text": "/alertas", "chat": {"id": -1009999}}}
    ])
    monkeypatch.setattr(main, "get_sources", lambda *a, **k: [])
    main.run_once()
    assert enviados == [-1009999]


def _alerta(nome, ate):
    return {"nome": nome, "origens": ["GRU"], "destinos": ["LIS"], "ate": ate,
            "a_partir_de": "2026-01-01", "max_preco_brl": 4000, "enabled": True}


def test_alerta_vencido_e_removido_e_avisado(ambiente, monkeypatch):
    tmp, enviados = ambiente
    estado = tmp / "seen.json"
    estado.write_text(json.dumps({
        "seen": {}, "serie": {}, "marcos": {},
        "alertas_usuario": [_alerta("Velho", "2020-01-31"), _alerta("Vivo", "2099-12-31")],
        "ultimo_update": None,
    }), encoding="utf-8")
    monkeypatch.setattr(main, "get_sources", lambda *a, **k: [])
    main.run_once()

    salvo = json.loads(estado.read_text(encoding="utf-8"))
    assert [a["nome"] for a in salvo["alertas_usuario"]] == ["Vivo"]
    assert len(enviados) == 1 and "Velho" in enviados[0] and "2020-01-31" in enviados[0]


def test_alerta_sem_ate_sobrevive(ambiente, monkeypatch):
    tmp, enviados = ambiente
    sem_fim = _alerta("Aberto", None)
    (tmp / "seen.json").write_text(json.dumps({
        "seen": {}, "serie": {}, "marcos": {},
        "alertas_usuario": [sem_fim], "ultimo_update": None,
    }), encoding="utf-8")
    monkeypatch.setattr(main, "get_sources", lambda *a, **k: [])
    main.run_once()
    salvo = json.loads((tmp / "seen.json").read_text(encoding="utf-8"))
    assert [a["nome"] for a in salvo["alertas_usuario"]] == ["Aberto"]
    assert enviados == []


def test_alerta_criado_agora_nao_e_varrido_na_mesma_rodada(ambiente, monkeypatch):
    """A limpeza roda depois dos comandos; ordem invertida apagaria o novo."""
    from milhasalerta import comandos
    monkeypatch.setattr(main.telegram, "receber", lambda desde=None: [
        {"update_id": 1, "message": {"text": "/alerta Lisboa", "chat": {"id": 1}}}
    ])
    monkeypatch.setattr(comandos, "interpretar",
                        lambda texto, client=None, queda_padrao=10: _alerta("Novo", "2099-01-01"))
    monkeypatch.setattr(main, "get_sources", lambda *a, **k: [])
    main.run_once()
    salvo = json.loads((ambiente[0] / "seen.json").read_text(encoding="utf-8"))
    assert [a["nome"] for a in salvo["alertas_usuario"]] == ["Novo"]
