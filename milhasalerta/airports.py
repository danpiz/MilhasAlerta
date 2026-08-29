import functools

import airportsdata

# O airportsdata traz city sem acento ("Sao Paulo") e às vezes com a cidade do
# aeroporto em vez da metrópole ("Ezeiza" para EZE). Como isso é o texto que
# aparece no alerta, os aeroportos que de fato aparecem em deal brasileiro têm
# nome próprio aqui; o resto cai no pacote.
NOMES = {
    # Brasil
    "GRU": "São Paulo", "CGH": "São Paulo", "VCP": "Campinas", "SAO": "São Paulo",
    "GIG": "Rio de Janeiro", "SDU": "Rio de Janeiro", "RIO": "Rio de Janeiro",
    "BSB": "Brasília", "CNF": "Belo Horizonte", "SSA": "Salvador",
    "REC": "Recife", "FOR": "Fortaleza", "POA": "Porto Alegre",
    "CWB": "Curitiba", "FLN": "Florianópolis", "MCZ": "Maceió",
    "NAT": "Natal", "BEL": "Belém", "MAO": "Manaus", "IGU": "Foz do Iguaçu",
    # América do Sul
    "EZE": "Buenos Aires", "AEP": "Buenos Aires", "SCL": "Santiago",
    "LIM": "Lima", "BOG": "Bogotá", "MVD": "Montevidéu", "PTY": "Cidade do Panamá",
    # América do Norte
    "JFK": "Nova York", "EWR": "Nova York", "LGA": "Nova York",
    "MIA": "Miami", "MCO": "Orlando", "LAX": "Los Angeles",
    "ORD": "Chicago", "IAD": "Washington", "YYZ": "Toronto", "MEX": "Cidade do México",
    # Europa
    "LIS": "Lisboa", "OPO": "Porto", "MAD": "Madri", "BCN": "Barcelona",
    "CDG": "Paris", "ORY": "Paris", "LHR": "Londres", "LGW": "Londres",
    "FCO": "Roma", "MXP": "Milão", "FRA": "Frankfurt", "MUC": "Munique",
    "AMS": "Amsterdã", "ZRH": "Zurique", "IST": "Istambul", "DUB": "Dublin",
    # Europa — nomes em portugues
    "VIE": "Viena", "GVA": "Genebra", "BRU": "Bruxelas", "CPH": "Copenhague",
    "ARN": "Estocolmo", "HEL": "Helsinque", "PRG": "Praga", "BUD": "Budapeste",
    "WAW": "Varsóvia", "ATH": "Atenas", "EDI": "Edimburgo", "VCE": "Veneza",
    "NAP": "Nápoles", "FLR": "Florença", "SVQ": "Sevilha", "AGP": "Málaga",
    "VLC": "Valência", "MAN": "Manchester", "NCE": "Nice", "LYS": "Lyon",
    # Americas — o pacote devolve o suburbio do aeroporto, nao a cidade
    "YUL": "Montreal",       # diria "Dorval"
    "YVR": "Vancouver",      # diria "Richmond"
    "SJD": "Los Cabos", "LPB": "La Paz", "CUN": "Cancún",
    "AUA": "Aruba", "CUR": "Curaçao", "BGI": "Barbados",
    "ASU": "Assunção", "SDQ": "Santo Domingo", "PUJ": "Punta Cana",
    "HAV": "Havana", "SJO": "San José",
    # Asia, Africa e Oceania
    "ICN": "Seul", "SIN": "Singapura", "PEK": "Pequim", "PVG": "Xangai",
    "DEL": "Nova Délhi", "BOM": "Mumbai", "ADD": "Adis Abeba", "AMM": "Amã",
    "DXB": "Dubai", "DOH": "Doha", "NRT": "Tóquio", "HND": "Tóquio",
    "JNB": "Joanesburgo", "CPT": "Cidade do Cabo", "SYD": "Sydney",
}


@functools.lru_cache(maxsize=1)
def _by_iata() -> dict:
    return airportsdata.load("IATA")


def _flag(country_code: str) -> str:
    # Regional indicator symbols sit 0x1F1E6 above 'A'.
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country_code.upper())


def describe(iata: str) -> str:
    """'GRU' -> 'São Paulo 🇧🇷'. Código desconhecido volta como veio."""
    codigo = iata.upper()
    airport = _by_iata().get(codigo)
    if not airport:
        return codigo
    return f"{NOMES.get(codigo, airport['city'])} {_flag(airport['country'])}".strip()
