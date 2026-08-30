import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from milhasalerta import telegram
from milhasalerta.extract import Extractor
from milhasalerta.milheiro import custo_efetivo
from milhasalerta.models import Deal
from milhasalerta.rules import regras_que_casam
from milhasalerta.sources.base import get_sources
from milhasalerta.state import State

RAIZ = Path(__file__).parent
CONFIG = RAIZ / "config.yaml"
ESTADO = RAIZ / "state" / "seen.json"

# No Actions as credenciais vêm do ambiente; localmente, do .env.
load_dotenv(RAIZ / ".env")


def _marcador(post) -> Deal:
    """Deal mínimo só para carregar a dedup_key no modo --seed, sem gastar API.

    A chave TEM de sair de post.dedup_key, não de post.url: no Telegram elas são
    diferentes (permalink vs link do artigo), e marcar a errada faz o --seed não
    semear nada — o backlog inteiro reaparece como novo na execução seguinte.
    """
    return Deal(
        kind="voo",
        titulo=post.titulo,
        url=post.url,
        fonte=post.fonte,
        dedup_key=post.dedup_key,
    )


def _listar(config, sources) -> int:
    ativas = [r for r in config["alertas"] if r.get("enabled", True)]
    print(f"Regras ativas ({len(ativas)}):")
    for regra in ativas:
        print(f"  - [{regra['kind']}] {regra['nome']}")
    print(f"\nFontes ({len(sources)}):")
    for source in sources:
        print(f"  - {source.nome}")
    return 0


def run_once(dry_run: bool = False, seed: bool = False) -> int:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    state = State(ESTADO)

    # Nem dry-run nem seed chamam o modelo.
    extrair = _marcador if (seed or dry_run) else Extractor()
    sources = get_sources(config, extrair=extrair, ja_visto=lambda url: not state.is_new(url))

    if dry_run:
        return _listar(config, sources)

    if seed:
        print("Marcando o backlog atual como visto, sem alertar nem chamar o modelo.")
    elif not ESTADO.exists():
        print(
            "Aviso: estado vazio — todo o backlog dos feeds vira alerta agora.\n"
            "       Use --seed antes se quiser começar só com o que for publicado daqui pra frente.",
            file=sys.stderr,
        )

    enviados = marcados = 0
    for source in sources:
        try:
            deals = source.fetch()
        except Exception as erro:
            # Uma fonte fora do ar não pode derrubar as outras.
            print(f"[erro] {source.nome}: {erro}", file=sys.stderr)
            continue

        for deal in deals:
            if not state.is_new(deal.dedup_key):
                continue
            deal.custo_efetivo_brl = custo_efetivo(
                deal.milhas, deal.programa, config.get("milheiro", {})
            )
            state.mark(deal.dedup_key)
            marcados += 1
            if seed:
                continue
            regras = regras_que_casam(config["alertas"], deal)
            if not regras:
                continue
            telegram.enviar(telegram.formatar(deal, regras))
            enviados += 1
            print(f"[alerta] {deal.titulo}")

    state.save()
    if seed:
        print(f"{marcados} post(s) marcado(s). A próxima execução só alerta o que for novo.")
    else:
        print(f"{enviados} alerta(s) enviado(s) de {marcados} post(s) novo(s).")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor de deals de milhas e passagens.")
    parser.add_argument("--dry-run", action="store_true", help="Lista regras e fontes e sai.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Marca o backlog atual como visto, sem alertar. Use na primeira execução.",
    )
    args = parser.parse_args()
    raise SystemExit(run_once(dry_run=args.dry_run, seed=args.seed))
