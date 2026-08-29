import json
from datetime import datetime, timedelta, timezone

from milhasalerta.state import State


def test_novo_ate_ser_marcado(tmp_path):
    state = State(tmp_path / "seen.json")
    assert state.is_new("https://exemplo.com/a")
    state.mark("https://exemplo.com/a")
    assert not state.is_new("https://exemplo.com/a")


def test_persiste_entre_execucoes(tmp_path):
    caminho = tmp_path / "seen.json"
    primeira = State(caminho)
    primeira.mark("https://exemplo.com/a")
    primeira.save()

    segunda = State(caminho)
    assert not segunda.is_new("https://exemplo.com/a")
    assert segunda.is_new("https://exemplo.com/b")


def test_poda_entradas_alem_da_retencao(tmp_path):
    caminho = tmp_path / "seen.json"
    antigo = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    recente = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    caminho.write_text(json.dumps({"seen": {"velho": antigo, "novo": recente}}))

    state = State(caminho)
    state.save()

    salvos = json.loads(caminho.read_text())["seen"]
    assert "velho" not in salvos
    assert "novo" in salvos


def test_cria_diretorio_do_estado(tmp_path):
    state = State(tmp_path / "sub" / "dir" / "seen.json")
    state.mark("x")
    state.save()
    assert (tmp_path / "sub" / "dir" / "seen.json").exists()
