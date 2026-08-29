"""Testa a lógica em volta do modelo, não o modelo.

A qualidade da extração em si só dá para julgar com ANTHROPIC_API_KEY —
ver tests/test_extract_live.py.
"""

from types import SimpleNamespace

from milhasalerta.extract import DealExtraido, Extractor
from milhasalerta.sources.rss import Post

POST = Post(
    titulo="Voe para Lima a partir de R$ 593 ou 24 mil milhas LATAM Pass + taxas",
    resumo="bilhetes de ida e volta entre São Paulo (GRU) e Lima (LIM)",
    url="https://exemplo.com/lima",
    fonte="Passageiro de Primeira",
    dedup_key="https://exemplo.com/lima",
)


class ClienteDuble:
    def __init__(self, extraido: DealExtraido):
        self._extraido = extraido
        self.messages = SimpleNamespace(parse=self._parse)
        self.chamadas = []

    def _parse(self, **kwargs):
        self.chamadas.append(kwargs)
        return SimpleNamespace(parsed_output=self._extraido)


def extrair(extraido: DealExtraido, post: Post = POST):
    cliente = ClienteDuble(extraido)
    return Extractor(client=cliente)(post), cliente


def test_voo_vira_deal_com_os_dois_precos():
    deal, _ = extrair(
        DealExtraido(
            kind="voo", programa="LATAM Pass", origem="GRU", destino="LIM",
            cabine="economica", milhas=24000, preco_brl=593,
        )
    )
    assert deal.kind == "voo"
    assert (deal.origem, deal.destino) == ("GRU", "LIM")
    assert (deal.milhas, deal.preco_brl) == (24000, 593)
    assert deal.dedup_key == POST.dedup_key
    assert deal.titulo == POST.titulo


def test_irrelevante_vira_none():
    deal, _ = extrair(DealExtraido(kind="irrelevante"))
    assert deal is None


def test_voo_sem_nenhum_preco_e_descartado():
    deal, _ = extrair(DealExtraido(kind="voo", destino="LIM"))
    assert deal is None


def test_promo_preserva_bonus():
    deal, _ = extrair(DealExtraido(kind="promo", programa="Livelo", bonus_pct=100))
    assert (deal.kind, deal.bonus_pct, deal.programa) == ("promo", 100, "Livelo")


def test_usa_haiku_e_manda_titulo_e_resumo():
    _, cliente = extrair(DealExtraido(kind="voo", preco_brl=593))
    (chamada,) = cliente.chamadas
    assert chamada["model"] == "claude-haiku-4-5"
    conteudo = chamada["messages"][0]["content"]
    assert POST.titulo in conteudo and POST.resumo in conteudo
