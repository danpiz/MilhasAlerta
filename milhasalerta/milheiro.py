"""Converte milhas em reais para os dois preços virarem comparáveis.

Um alerta que diz "R$ 593 ou 24k LATAM Pass" obriga você a fazer a conta de
cabeça para saber qual lado compensa. Com a cotação do milheiro o alerta passa
a dizer "≈R$ 396", e a resposta fica óbvia.

A cotação é palpite informado, não preço de mercado: varia por programa e muda
a cada promoção de compra de pontos. Por isso vive no config.yaml, e o alerta
sempre marca o valor com "≈".
"""

from typing import Optional

PADRAO = "padrao"


def cotacao(programa: Optional[str], tabela: dict) -> Optional[float]:
    """R$ por 1.000 milhas do programa, ou a cotação padrão."""
    if not tabela:
        return None
    if programa:
        alvo = programa.strip().lower()
        for nome, valor in tabela.items():
            if nome.lower() == alvo:
                return float(valor)
    padrao = tabela.get(PADRAO)
    return float(padrao) if padrao is not None else None


def custo_efetivo(milhas: Optional[int], programa: Optional[str], tabela: dict) -> Optional[int]:
    """Quanto as milhas custariam em reais. None quando não dá para saber."""
    if not milhas:
        return None
    taxa = cotacao(programa, tabela)
    if taxa is None:
        return None
    return round(milhas / 1000 * taxa)
