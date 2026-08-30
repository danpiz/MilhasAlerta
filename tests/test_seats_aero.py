"""O provider em si nunca foi exercitado contra a API real (exige conta Pro).
Estes testes cobrem a logica local que roda sobre a resposta dela."""

from datetime import datetime, timedelta, timezone

from milhasalerta.sources.seats_aero import SeatsAeroSource

AGORA = datetime.now(timezone.utc)


def fonte(horas=5):
    return SeatsAeroSource(api_key="x", alertas=[], max_staleness_horas=horas)


def marca(delta_horas):
    return (AGORA - timedelta(hours=delta_horas)).isoformat().replace("+00:00", "Z")


def test_registro_recente_passa():
    assert fonte()._fresco({"LastSeen": marca(2)})


def test_registro_velho_e_descartado():
    # Disponibilidade award evapora em horas; o cache do Seats.aero nao.
    assert not fonte()._fresco({"LastSeen": marca(30)})


def test_cai_para_updated_at_e_created_at():
    assert fonte()._fresco({"UpdatedAt": marca(1)})
    assert not fonte()._fresco({"CreatedAt": marca(48)})


def test_sem_marca_de_tempo_passa():
    # Nao rejeitamos por dado ausente.
    assert fonte()._fresco({"JMileageCost": 60000})


def test_marca_ilegivel_passa():
    assert fonte()._fresco({"LastSeen": "ontem de tarde"})


def test_marca_ingenua_e_tratada_como_utc():
    ingenua = (AGORA - timedelta(hours=1)).replace(tzinfo=None).isoformat()
    assert fonte()._fresco({"LastSeen": ingenua})


def test_limite_nulo_desliga_o_filtro():
    assert fonte(horas=None)._fresco({"LastSeen": marca(500)})


def test_firehose_nao_e_consultado():
    """Cached search precisa de par origem+destino; regra sem destinos nao e
    enumeravel e nao pode virar varredura cega da API."""
    s = SeatsAeroSource(
        api_key="x",
        alertas=[{"nome": "Firehose", "kind": "voo", "origens": ["GRU"], "enabled": True}],
    )
    assert s.fetch() == []
