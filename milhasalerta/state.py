import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .historico import podar

RETENCAO = timedelta(days=30)


class State:
    """Dedup de deals já alertados, persistido em JSON de texto simples."""

    def __init__(self, path: Path):
        self.path = path
        self._seen: dict[str, str] = {}
        self.serie: dict[str, list] = {}
        self._marcos: dict[str, str] = {}
        # Rotas criadas pelo /alerta no Telegram, e o offset do getUpdates --
        # sem persistir o offset, a mesma mensagem viraria alerta duplicado.
        self.alertas_usuario: list[dict] = []
        self.ultimo_update: int | None = None
        if path.exists():
            bruto = json.loads(path.read_text(encoding="utf-8"))
            self._seen = bruto.get("seen", {})
            self.serie = bruto.get("serie", {})
            self._marcos = bruto.get("marcos", {})
            self.alertas_usuario = bruto.get("alertas_usuario", [])
            self.ultimo_update = bruto.get("ultimo_update")

    def is_new(self, dedup_key: str) -> bool:
        return dedup_key not in self._seen

    def chaves_vistas(self, prefixo: str) -> list[str]:
        """Chaves ja alertadas que comecam com o prefixo.

        O Google Flights poe o preco na chave, entao so "ja vi esta chave" nao
        basta: precisa saber por QUAL preco ja alertou aquele trecho, senao uma
        alta de preco vira chave nova e realerta mais caro. A leitura da chave
        fica na fonte; aqui so o prefixo."""
        return [k for k in self._seen if k.startswith(prefixo)]

    def mark(self, dedup_key: str) -> None:
        self._seen[dedup_key] = datetime.now(timezone.utc).isoformat()

    def passou(self, nome: str, horas: float) -> bool:
        """Estrangula uma fonte cara sem precisar de workflow separado --
        dois workflows commitando o mesmo estado brigariam pelo push."""
        marco = self._marcos.get(nome)
        if not marco:
            return True
        idade = datetime.now(timezone.utc) - datetime.fromisoformat(marco)
        return idade >= timedelta(hours=horas)

    def marcar_execucao(self, nome: str) -> None:
        self._marcos[nome] = datetime.now(timezone.utc).isoformat()

    def save(self) -> None:
        limite = datetime.now(timezone.utc) - RETENCAO
        vivos = {
            key: visto
            for key, visto in self._seen.items()
            if datetime.fromisoformat(visto) > limite
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "seen": vivos,
                    "serie": podar(self.serie),
                    "marcos": self._marcos,
                    "alertas_usuario": self.alertas_usuario,
                    "ultimo_update": self.ultimo_update,
                },
                indent=2, sort_keys=True, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
