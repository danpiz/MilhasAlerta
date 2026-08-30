from pathlib import Path

import pytest
from dotenv import load_dotenv

# Os testes live leem ANTHROPIC_API_KEY no import; carregar antes da coleta.
load_dotenv(Path(__file__).parent.parent / ".env")


@pytest.fixture(autouse=True)
def sem_telegram_de_verdade(monkeypatch, request):
    """Nenhum teste fala com o bot real.

    getUpdates avanca o offset no servidor do Telegram: um teste distraido
    consome mensagens de verdade e elas somem para sempre. E enviar dispararia
    alerta no celular do usuario a cada rodada da suite.

    Marque com @pytest.mark.sem_guarda_telegram o teste que precisa da
    funcao de verdade e ja dublou a rede por conta propria.
    """
    if request.node.get_closest_marker("sem_guarda_telegram"):
        return
    from milhasalerta import telegram

    def barrado(*a, **k):
        raise AssertionError(
            "teste tentou falar com o Telegram real; use monkeypatch ou a marca sem_guarda_telegram"
        )

    monkeypatch.setattr(telegram, "receber", barrado)
    monkeypatch.setattr(telegram, "enviar", barrado)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "sem_guarda_telegram: chama as funcoes reais do telegram (rede ja dublada no teste)",
    )
