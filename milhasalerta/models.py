from dataclasses import dataclass
from typing import Literal, Optional

Kind = Literal["voo", "promo"]
Cabine = Literal["economica", "executiva", "primeira"]


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
    # kind="promo"
    bonus_pct: Optional[int] = None
