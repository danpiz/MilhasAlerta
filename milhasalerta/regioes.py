"""Atalhos de região para o config.

O Google Flights tem busca por região na interface, mas ela é renderizada por
JavaScript e a fast_flights só faz ponto-a-ponto. Então "europa" só existe como
uma lista curada de aeroportos — e cada aeroporto vira uma consulta, o que
torna o tamanho dessas listas a variável de custo.

Curadas para deal saindo do Brasil, não exaustivas. Para vigiar um aeroporto
fora daqui, basta listar o código IATA direto no config.
"""

REGIOES = {
    "europa": [
        "LIS", "OPO", "MAD", "BCN", "CDG", "FCO", "LHR", "AMS",
        "FRA", "MXP", "MUC", "ZRH", "DUB", "BRU",
    ],
    "america_do_norte": [
        "MIA", "MCO", "JFK", "EWR", "LAX", "ORD", "IAD", "BOS",
        "DFW", "ATL", "YYZ", "MEX", "CUN",
    ],
    "america_do_sul": [
        "EZE", "SCL", "LIM", "BOG", "MVD", "ASU", "PTY", "AEP",
    ],
    "asia": ["NRT", "HND", "ICN", "SIN", "BKK", "HKG", "DXB", "DOH", "TLV"],
    "africa": ["JNB", "CPT", "CMN", "ADD", "NBO"],
    "oceania": ["SYD", "MEL", "AKL"],
}


def expandir(destinos) -> list[str]:
    """Aceita lista com códigos IATA, nomes de região, ou os dois misturados."""
    if isinstance(destinos, str):
        destinos = [destinos]
    saida: list[str] = []
    for item in destinos or []:
        chave = str(item).strip().lower()
        for iata in REGIOES.get(chave, [str(item).strip().upper()]):
            if iata not in saida:
                saida.append(iata)
    return saida
