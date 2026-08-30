"""Preço em dinheiro de rotas vigiadas, via Google Flights.

É a única fonte do projeto que consulta uma rota em vez de reagir ao que os
portais publicaram — responde "avise se Europa cair abaixo de R$ 2.500", que os
canais não conseguem.

DUAS COISAS QUE PARECEM DETALHE E NÃO SÃO:

1. currency="BRL" é obrigatório. O parâmetro é vazio por padrão e o Google
   decide pelo IP; o runner do Actions fica nos EUA e devolve dólar. Medido:
   GRU-MIA veio 335 sem forçar e R$ 1.736 com BRL.

2. Cada destino × data é uma consulta. Europa inteira num mês seriam 434
   consultas por rodada. A amostragem existe para isso não virar bloqueio.

É scraping: contra os termos do Google, e quebra quando eles mudarem o formato.
Falha aqui não derruba as outras fontes.
"""

from datetime import date, timedelta
from typing import Callable, Optional

from ..models import Deal
from ..regioes import expandir

CURRENCY = "BRL"


def datas_amostradas(quantidade: int, passo_dias: int = 30, offset_dias: int = 30) -> list[str]:
    """Uma data por mês. Panorama do ano sem varrer o calendário inteiro."""
    hoje = date.today()
    return [
        (hoje + timedelta(days=offset_dias + i * passo_dias)).isoformat()
        for i in range(quantidade)
    ]


class GoogleFlightsSource:
    nome = "Google Flights"

    def __init__(
        self,
        rotas: list[dict],
        ja_visto: Callable[[str], bool],
        observar: Callable[[str, str, str, int], Optional[int]],
        amostras: int = 6,
        cabine: str = "economy",
    ):
        self.rotas = rotas or []
        self._ja_visto = ja_visto
        # Recebe (origem, destino, data, preco) e devolve a queda % contra o
        # historico, se houver. Mantem a serie fora da fonte.
        self._observar = observar
        self.amostras = amostras
        self.cabine = cabine

    def _consultar(self, origem: str, destino: str, dia: str) -> list[int]:
        from fast_flights import FlightQuery, Passengers, create_query, get_flights

        q = create_query(
            flights=[FlightQuery(date=dia, from_airport=origem, to_airport=destino)],
            seat=self.cabine,
            trip="one-way",
            passengers=Passengers(adults=1),
            currency=CURRENCY,
        )
        return [
            int(v.price) for v in get_flights(q) if str(v.price).isdigit() and int(v.price) > 0
        ]

    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        for rota in self.rotas:
            if not rota.get("enabled", True):
                continue
            destinos = expandir(rota.get("destinos"))
            for origem in rota.get("origens", []):
                for destino in destinos:
                    for dia in datas_amostradas(self.amostras):
                        deal = self._melhor(rota, origem, destino, dia)
                        if deal:
                            deals.append(deal)
        return deals

    def _melhor(self, rota: dict, origem: str, destino: str, dia: str) -> Optional[Deal]:
        try:
            precos = self._consultar(origem, destino, dia)
        except Exception:
            # Uma rota fora do ar nao pode abortar as outras 83.
            return None
        if not precos:
            return None

        preco = min(precos)
        # Observa sempre, mesmo sem alertar: e observando preco comum que o
        # historico aprende o que e "normal" naquela rota.
        queda = self._observar(origem, destino, dia, preco)

        # Filtra aqui, nao so nas regras: sem isso cada varredura empurraria 84
        # precos comuns para o estado, que so guarda o que vale a pena rever.
        teto = rota.get("max_preco_brl")
        minimo_queda = rota.get("min_queda_pct")
        bom_por_preco = teto is not None and preco <= teto
        bom_por_queda = minimo_queda is not None and queda is not None and queda >= minimo_queda
        if not (bom_por_preco or bom_por_queda):
            return None

        # O preco entra na chave: o mesmo valor nao realerta, mas uma queda
        # adicional e noticia nova.
        chave = f"gf:{origem}-{destino}-{dia}:{preco}"
        if self._ja_visto(chave):
            return None

        titulo = f"{origem}→{destino} em {dia} por R$ {preco}"
        if queda:
            titulo = f"{titulo} ({queda}% abaixo do normal)"
        return Deal(
            kind="voo",
            titulo=titulo,
            url=(
                "https://www.google.com/travel/flights?q="
                f"Flights%20to%20{destino}%20from%20{origem}%20on%20{dia}%20oneway"
            ),
            fonte=self.nome,
            dedup_key=chave,
            origem=origem,
            destino=destino,
            cabine="economica" if self.cabine == "economy" else self.cabine,
            preco_brl=preco,
            queda_pct=queda,
        )
