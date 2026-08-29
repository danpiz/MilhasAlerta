"""Casamento entre Deals e as regras do config.yaml.

Regra geral: **todo filtro exige prova.** Se o deal não afirma o valor, não casa.
Sem isso uma regra de `cabines: [executiva]` dispararia em passagem econômica de
R$ 150 — dado ausente vira curinga e a regra específica vira outro firehose.

A única exceção é `origens`, que tolera origem ausente: os portais brasileiros
omitem a origem por convenção ("Voe para Lima a partir de R$ 593" quase sempre é
de São Paulo), e exigir prova ali deixaria o monitor mudo.

Entre `max_milhas` e `max_preco_brl` a relação é OU: basta um lado estar bom, que é
o que faz funcionar "R$ 593 ou 24 mil milhas". Entre campos diferentes é E.

Como o dedup é por deal, e não por regra, o alerta sai uma vez só listando todas as
regras que casaram.
"""

from .models import Deal


def _lista_ok(valor, permitidos, ausente_passa: bool = False) -> bool:
    if not permitidos:
        return True
    if valor is None:
        return ausente_passa
    alvo = str(valor).strip().lower()
    return any(alvo == str(p).strip().lower() for p in permitidos)


def _preco_ok(regra: dict, deal: Deal) -> bool:
    """Barra de qualidade: exige prova, e é OU entre milhas e reais."""
    limites = []
    if regra.get("max_milhas") is not None:
        limites.append((deal.milhas, regra["max_milhas"]))
    if regra.get("max_preco_brl") is not None:
        limites.append((deal.preco_brl, regra["max_preco_brl"]))
    if not limites:
        return True
    # Sem nenhum valor afirmado não há prova de que o deal é bom.
    return any(valor is not None and valor <= limite for valor, limite in limites)


def casa(regra: dict, deal: Deal) -> bool:
    if not regra.get("enabled", True):
        return False
    if regra.get("kind") != deal.kind:
        return False

    if deal.kind == "voo":
        return (
            _lista_ok(deal.origem, regra.get("origens"), ausente_passa=True)
            and _lista_ok(deal.destino, regra.get("destinos"))
            and _lista_ok(deal.cabine, regra.get("cabines"))
            and _preco_ok(regra, deal)
        )

    minimo = regra.get("min_bonus_pct")
    bonus_ok = minimo is None or (deal.bonus_pct is not None and deal.bonus_pct >= minimo)
    return _lista_ok(deal.programa, regra.get("programas")) and bonus_ok


def regras_que_casam(alertas: list[dict], deal: Deal) -> list[str]:
    return [regra["nome"] for regra in alertas if casa(regra, deal)]
