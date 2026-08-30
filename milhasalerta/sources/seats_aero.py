"""Provider do Seats.aero Partner API — dormente até SEATS_API_KEY existir.

NÃO EXERCITADO CONTRA A API REAL: exige conta Pro (US$ 9,99/mês). O formato de
requisição e resposta segue a documentação e o cliente de eduard0vieira/mileage-bot.
Validar contra o retorno real antes de confiar nos alertas que sair daqui.
"""

from datetime import date, datetime, timedelta, timezone

import requests

from ..models import Deal

BASE_URL = "https://seats.aero/partnerapi"

# Portado de eduard0vieira/mileage-bot (app/services/seats_client.py).
PROGRAMAS = {
    "smiles": "Smiles",
    "latam": "LATAM Pass",
    "azul": "Azul Fidelidade",
    "aeroplan": "Air Canada Aeroplan",
    "united": "United MileagePlus",
    "lifemiles": "Avianca LifeMiles",
    "aa": "American AAdvantage",
    "delta": "Delta SkyMiles",
    "flyingblue": "Flying Blue",
    "virginatlantic": "Virgin Atlantic Flying Club",
    "qantas": "Qantas Frequent Flyer",
    "alaska": "Alaska Mileage Plan",
    "emirates": "Emirates Skywards",
    "etihad": "Etihad Guest",
    "turkish": "Turkish Miles&Smiles",
    "eurobonus": "SAS EuroBonus",
    "velocity": "Virgin Australia Velocity",
    "connectmiles": "Copa ConnectMiles",
}

CAMPO_CUSTO = {
    "economica": "YMileageCost",
    "executiva": "JMileageCost",
    "primeira": "FMileageCost",
}


class SeatsAeroSource:
    nome = "seats.aero"

    def __init__(
        self,
        api_key: str,
        alertas: list[dict],
        janela_dias: int = 60,
        max_staleness_horas: float = 5,
    ):
        self.api_key = api_key
        self.alertas = alertas
        self.janela_dias = janela_dias
        self.max_staleness_horas = max_staleness_horas

    def _buscar(self, origem: str, destino: str, cabine: str) -> list[dict]:
        inicio = date.today()
        resposta = requests.get(
            f"{BASE_URL}/search",
            headers={"Partner-Authorization": self.api_key},
            params={
                "origin_airport": origem,
                "destination_airport": destino,
                "start_date": inicio.isoformat(),
                "end_date": (inicio + timedelta(days=self.janela_dias)).isoformat(),
                "cabin": cabine,
            },
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json().get("data", [])

    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        for alerta in self.alertas:
            # O cached search precisa de par origem+destino; o firehose (regra sem
            # destinos) não é enumerável e fica só com o RSS.
            destinos = alerta.get("destinos")
            if not alerta.get("enabled", True) or alerta.get("kind") != "voo" or not destinos:
                continue
            for origem in alerta.get("origens", []):
                for destino in destinos:
                    for cabine in alerta.get("cabines", ["executiva"]):
                        deals.extend(self._para_deals(origem, destino, cabine))
        return deals

    def _fresco(self, voo: dict) -> bool:
        """O Seats.aero cacheia, e disponibilidade award evapora em horas.

        Sem este filtro o provider alerta assento que ja nao existe. A propria
        comunidade recomenda so confiar no que foi revisto nas ultimas horas,
        e a diferenca aparece na pratica: um mesmo voo cotado 89k no cache
        estava 81,5k no site do programa.

        Registro sem marca de tempo passa: nao rejeitamos por dado ausente.
        """
        marca = voo.get("LastSeen") or voo.get("UpdatedAt") or voo.get("CreatedAt")
        if not marca or self.max_staleness_horas is None:
            return True
        try:
            visto = datetime.fromisoformat(str(marca).replace("Z", "+00:00"))
        except ValueError:
            return True
        if visto.tzinfo is None:
            visto = visto.replace(tzinfo=timezone.utc)
        idade = (datetime.now(timezone.utc) - visto).total_seconds() / 3600
        return idade <= self.max_staleness_horas

    def _para_deals(self, origem: str, destino: str, cabine: str) -> list[Deal]:
        campo = CAMPO_CUSTO.get(cabine)
        if not campo:
            return []
        deals = []
        for voo in self._buscar(origem, destino, cabine):
            if not self._fresco(voo):
                continue
            milhas = int(voo.get(campo) or 0)
            if not milhas:
                continue
            fonte_programa = (voo.get("Source") or "").lower()
            rota = voo.get("Route") or {}
            identidade = voo.get("ID") or f"{origem}{destino}{voo.get('Date')}{milhas}"
            deals.append(
                Deal(
                    kind="voo",
                    titulo=f"{origem}→{destino} {cabine} por {milhas // 1000}k milhas",
                    url=f"https://seats.aero/search?originAirport={origem}&destinationAirport={destino}",
                    fonte=self.nome,
                    dedup_key=f"seats:{identidade}",
                    programa=PROGRAMAS.get(fonte_programa, fonte_programa.title() or None),
                    origem=rota.get("OriginAirport") or origem,
                    destino=rota.get("DestinationAirport") or destino,
                    cabine=cabine,
                    milhas=milhas,
                )
            )
        return deals
