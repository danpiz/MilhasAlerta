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

import sys
from datetime import date, timedelta
from typing import Callable, Optional

from ..models import Deal
from ..regioes import expandir

CURRENCY = "BRL"


def _somar_dias(dia: str, n: int) -> str:
    return (date.fromisoformat(dia) + timedelta(days=n)).isoformat()


def datas_amostradas(
    quantidade: int,
    passo_dias: int = 30,
    offset_dias: int = 30,
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
) -> list[str]:
    """Datas de ida a consultar.

    Sem `fim`, uma por mês: panorama do ano sem varrer o calendário inteiro.

    Com `fim`, as mesmas `quantidade` datas se espalham DENTRO da janela. A
    diferença não é cosmética: "a partir de 20/dez" sem fim caminhava até maio,
    misturando alta e baixa temporada na mesma rota — e aí um teto só não serve
    para as duas pontas (medido: Alemanha a R$ 5.961 em dez e R$ 4.457 em fev).
    """
    base = date.fromisoformat(inicio) if inicio else date.today() + timedelta(days=offset_dias)
    if not fim:
        return [(base + timedelta(days=i * passo_dias)).isoformat() for i in range(quantidade)]

    vao = (date.fromisoformat(fim) - base).days
    if vao <= 0 or quantidade <= 1:
        return [base.isoformat()]
    passo = vao / (quantidade - 1)
    return [(base + timedelta(days=round(i * passo))).isoformat() for i in range(quantidade)]


def _url_google(origem: str, destino: str, dia: str, volta: Optional[str]) -> str:
    base = f"https://www.google.com/travel/flights?q=Flights%20to%20{destino}%20from%20{origem}%20on%20{dia}"
    return f"{base}%20through%20{volta}" if volta else f"{base}%20oneway"


def consultar(
    origem: str, destino: str, dia: str, volta: Optional[str] = None, cabine: str = "economy"
) -> list[int]:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights

    pernas = [FlightQuery(date=dia, from_airport=origem, to_airport=destino)]
    if volta:
        pernas.append(FlightQuery(date=volta, from_airport=destino, to_airport=origem))
    q = create_query(
        flights=pernas,
        seat=cabine,
        trip="round-trip" if volta else "one-way",
        passengers=Passengers(adults=1),
        currency=CURRENCY,
    )
    return [int(v.price) for v in get_flights(q) if str(v.price).isdigit() and int(v.price) > 0]


def cotar(rota: dict, max_destinos: int = 6, max_datas: int = 3) -> dict[str, int]:
    """Menor preco atual por destino, numa amostra pequena da rota.

    Serve para calibrar o teto de um alerta na hora em que ele e criado. Sem
    isso o teto e um chute: "abaixo de R$ 4.000" nao diz nada se o trecho custa
    10.000 (o alerta nunca dispara) nem se custa 3.000 (dispara com o preco
    normal, e foi o que encheu o Telegram com 87 mensagens em 30/08/2026).

    E amostra, nao varredura: a rota inteira da Europa sao 84 consultas e uns
    90s. Destino que falhar fica de fora em vez de derrubar a cotacao."""
    destinos = expandir(rota.get("destinos"))[:max_destinos]
    dias = rota.get("dias_de_viagem") if rota.get("ida_e_volta") else None
    origem = (rota.get("origens") or ["GRU"])[0]
    precos: dict[str, int] = {}
    for destino in destinos:
        achados = []
        datas = datas_amostradas(
            max_datas, inicio=rota.get("a_partir_de"), fim=rota.get("ate")
        )
        for dia in datas:
            volta = _somar_dias(dia, dias) if dias else None
            try:
                achados += consultar(origem, destino, dia, volta, "economy")
            except Exception:
                continue
        if achados:
            precos[destino] = min(achados)
    return precos


class GoogleFlightsSource:
    nome = "Google Flights"

    def __init__(
        self,
        rotas: list[dict],
        vistas: Callable[[str], list[str]],
        observar: Callable[[str, str, str, int], Optional[int]],
        amostras: int = 6,
        cabine: str = "economy",
        limite_por_rota: int = 3,
    ):
        self.rotas = rotas or []
        # Recebe um prefixo de chave e devolve as chaves ja alertadas.
        self._vistas = vistas
        # Recebe (origem, destino, data, preco) e devolve a queda % contra o
        # historico, se houver. Mantem a serie fora da fonte.
        self._observar = observar
        self.amostras = amostras
        self.cabine = cabine
        self.limite_por_rota = limite_por_rota
        self.consultas = self.falhas = 0

    def _consultar(
        self, origem: str, destino: str, dia: str, volta: Optional[str] = None
    ) -> list[int]:
        return consultar(origem, destino, dia, volta, self.cabine)

    def fetch(self) -> list[Deal]:
        deals: list[Deal] = []
        self.consultas = self.falhas = 0
        for rota in self.rotas:
            if not rota.get("enabled", True):
                continue
            destinos = expandir(rota.get("destinos"))
            # Ida e volta e o que a maioria quer; o preco de so-ida engana quem
            # le rapido. dias_de_viagem define a volta a partir da ida.
            dias = rota.get("dias_de_viagem") if rota.get("ida_e_volta") else None
            da_rota: list[Deal] = []
            for origem in rota.get("origens", []):
                for destino in destinos:
                    for dia in datas_amostradas(
                        self.amostras, inicio=rota.get("a_partir_de"), fim=rota.get("ate")
                    ):
                        volta = _somar_dias(dia, dias) if dias else None
                        deal = self._melhor(rota, origem, destino, dia, volta)
                        if deal:
                            da_rota.append(deal)
            # So as mais baratas da rota. O teto e um filtro, nao um criterio de
            # relevancia: se ele estiver acima do preco normal do trecho -- "Europa
            # ate R$ 6.000", quando Europa custa 4.200-5.700 -- TODAS as 14x6
            # combinacoes passam e viram alerta. Aconteceu: 87 mensagens de uma vez.
            # Ordenar por preco privilegia sempre os mesmos destinos baratos; e o
            # preco a pagar por um corte que nao depende de historico.
            da_rota.sort(key=lambda d: d.preco_brl)
            deals.extend(da_rota[: self.limite_por_rota])
        if self.falhas:
            # Scraper que emudece parece "nenhum deal hoje". Sem esta linha o
            # bloqueio do Google passaria semanas despercebido.
            print(
                f"[{self.nome}] {self.falhas}/{self.consultas} consultas falharam",
                file=sys.stderr,
            )
        return deals

    def _melhor(
        self, rota: dict, origem: str, destino: str, dia: str, volta: Optional[str] = None
    ) -> Optional[Deal]:
        self.consultas += 1
        try:
            precos = self._consultar(origem, destino, dia, volta)
        except Exception:
            # Uma rota fora do ar nao pode abortar as outras 83, mas a falha
            # precisa aparecer em algum lugar -- ver o resumo em fetch().
            self.falhas += 1
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

        # So alerta se for mais barato do que ja alertei para este trecho.
        # O preco entra na chave, entao a checagem "ja vi esta chave" tratava
        # QUALQUER preco diferente como novidade -- inclusive uma alta. Medido:
        # GRU-AMS 29/10 alertado a R$ 4330 e realertado a R$ 4450 dez horas
        # depois. Preco igual tambem nao repete: nao e menor.
        trecho = f"gf:{origem}-{destino}-{dia}-{volta or ''}"
        alertados = [
            int(sufixo)
            for chave in self._vistas(f"{trecho}:")
            if (sufixo := chave.rsplit(":", 1)[-1]).isdigit()
        ]
        if alertados and preco >= min(alertados):
            return None
        chave = f"{trecho}:{preco}"

        trecho = f"{dia} a {volta}" if volta else dia
        titulo = f"{origem}→{destino} em {trecho} por R$ {preco}"
        if queda:
            titulo = f"{titulo} ({queda}% abaixo do normal)"
        return Deal(
            kind="voo",
            titulo=titulo,
            url=_url_google(origem, destino, dia, volta),
            fonte=self.nome,
            dedup_key=chave,
            origem=origem,
            destino=destino,
            cabine="economica" if self.cabine == "economy" else self.cabine,
            preco_brl=preco,
            data=dia,
            data_volta=volta,
            queda_pct=queda,
        )
