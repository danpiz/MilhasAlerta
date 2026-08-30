from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

Kind = Literal["voo", "promo"]
Cabine = Literal["economica", "executiva", "primeira"]


def recente(publicado: Optional[datetime], max_idade_horas: Optional[float]) -> bool:
    """Sem limite configurado, ou sem data no post, nada é descartado — filtro
    de frescor não pode rejeitar por falta de dado, senão fonte sem timestamp
    ficaria muda."""
    if max_idade_horas is None or publicado is None:
        return True
    if publicado.tzinfo is None:
        publicado = publicado.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - publicado <= timedelta(hours=max_idade_horas)


@dataclass
class Deal:
    kind: Kind
    titulo: str
    url: str
    fonte: str
    dedup_key: str
    programa: Optional[str] = None
    # kind="voo"
    origem: Optional[str] = None
    destino: Optional[str] = None
    cabine: Optional[Cabine] = None
    milhas: Optional[int] = None
    preco_brl: Optional[int] = None
    # Milhas convertidas em reais pela cotacao do milheiro. Preenchido depois da
    # extracao, em main, para regras e alerta lerem sem conhecer o config.
    custo_efetivo_brl: Optional[int] = None
    # Preco de passagem so existe amarrado a uma data: sem isso o alerta nao e
    # acionavel. data_volta preenchida significa que o preco e de ida e volta.
    data: Optional[str] = None
    data_volta: Optional[str] = None
    # Post de portal quase nunca traz data, mas as vezes diz "ida e volta".
    # Sem isso o alerta mostra um preco que pode ser metade da viagem.
    ida_e_volta: Optional[bool] = None
    # Quanto abaixo do preco tipico da rota, quando ha historico suficiente.
    queda_pct: Optional[int] = None
    # kind="promo"
    bonus_pct: Optional[int] = None
