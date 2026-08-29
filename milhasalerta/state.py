import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RETENCAO = timedelta(days=30)


class State:
    """Dedup de deals já alertados, persistido em JSON de texto simples."""

    def __init__(self, path: Path):
        self.path = path
        self._seen: dict[str, str] = {}
        if path.exists():
            self._seen = json.loads(path.read_text(encoding="utf-8")).get("seen", {})

    def is_new(self, dedup_key: str) -> bool:
        return dedup_key not in self._seen

    def mark(self, dedup_key: str) -> None:
        self._seen[dedup_key] = datetime.now(timezone.utc).isoformat()

    def save(self) -> None:
        limite = datetime.now(timezone.utc) - RETENCAO
        vivos = {
            key: visto
            for key, visto in self._seen.items()
            if datetime.fromisoformat(visto) > limite
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"seen": vivos}, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
