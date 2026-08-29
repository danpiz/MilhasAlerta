from datetime import datetime, timedelta, timezone

from milhasalerta.models import recente
from milhasalerta.sources.telegram_channel import TelegramChannelSource

AGORA = datetime.now(timezone.utc)


def test_post_de_hoje_passa():
    assert recente(AGORA - timedelta(hours=3), 24)


def test_post_de_ontem_e_descartado():
    assert not recente(AGORA - timedelta(hours=30), 24)


def test_sem_limite_configurado_nada_e_descartado():
    assert recente(AGORA - timedelta(days=400), None)


def test_post_sem_data_passa():
    # Filtro de frescor não pode rejeitar por dado ausente: fonte sem
    # timestamp ficaria muda.
    assert recente(None, 24)


def test_data_ingenua_e_tratada_como_utc():
    ingenua = (AGORA - timedelta(hours=1)).replace(tzinfo=None)
    assert recente(ingenua, 24)


def test_fetch_nao_extrai_mensagem_velha(monkeypatch):
    """Velha não pode nem chegar no Haiku — cada extração custa uma chamada."""
    extraidos = []
    fonte = TelegramChannelSource(
        "C", "x",
        extrair=lambda p: extraidos.append(p.dedup_key),
        ja_visto=lambda k: False,
        max_idade_horas=24,
    )
    nova = f'{(AGORA - timedelta(hours=2)):%Y-%m-%dT%H:%M:%S}+00:00'
    velha = f'{(AGORA - timedelta(hours=48)):%Y-%m-%dT%H:%M:%S}+00:00'
    pagina = f"""
<div class="tgme_widget_message" data-post="canal/1">
<time datetime="{nova}"></time>
<div class="tgme_widget_message_text">Deal de hoje<br/>
<a href="https://site.com/hoje">link</a></div></div>
<div class="tgme_widget_message" data-post="canal/2">
<time datetime="{velha}"></time>
<div class="tgme_widget_message_text">Deal de anteontem<br/>
<a href="https://site.com/velho">link</a></div></div>
"""
    monkeypatch.setattr(
        "milhasalerta.sources.telegram_channel.requests.get",
        lambda *a, **k: type("R", (), {"text": pagina, "raise_for_status": lambda s: None})(),
    )
    fonte.fetch()
    assert extraidos == ["https://t.me/canal/1"]
