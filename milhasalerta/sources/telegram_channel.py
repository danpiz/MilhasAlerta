"""Canais públicos do Telegram via a prévia web em t.me/s/<canal>.

HTML público, sem token nem autenticação. Rende mais sinal que o RSS dos mesmos
portais: o canal do Melhores Destinos é só deal, enquanto o feed deles é
majoritariamente notícia de aeroporto e aviação.

A dedup_key é o link do artigo, não a permalink da mensagem — assim o mesmo deal
publicado em dois canais alerta uma vez só.
"""

import html
import re
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from ..models import Deal

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

BLOCO = re.compile(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
# data-post vive no wrapper da propria mensagem. Parear por indice com um regex
# separado desalinharia na primeira mensagem sem texto (so foto).
MENSAGEM = re.compile(r'data-post="([^"]+)"(.*?)(?=data-post="|\Z)', re.S)
HREF = re.compile(r'href="(https?://[^"]+)"')
URL_NUA = re.compile(r'https?://[^\s<>"]+')
LIMITE_RESUMO = 600
IMAGENS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
RASTREIO = {"fbclid", "gclid", "ref", "src"}


@dataclass
class Post:
    titulo: str
    resumo: str
    url: str
    fonte: str
    dedup_key: str


def _limpar(bruto: str) -> str:
    com_quebras = re.sub(r"<br\s*/?>", "\n", bruto)
    sem_tags = re.sub(r"<[^>]+>", "", com_quebras)
    return html.unescape(sem_tags).strip()


def _normalizar(url: str) -> str:
    """Tira só rastreamento. A query pode ser a identidade (?p=138128 no WordPress)."""
    partes = urlsplit(url)
    query = urlencode(
        [
            (chave, valor)
            for chave, valor in parse_qsl(partes.query)
            if not chave.startswith("utm_") and chave not in RASTREIO
        ]
    )
    return urlunsplit((partes.scheme, partes.netloc, partes.path.rstrip("/"), query, ""))


def _e_artigo(url: str) -> bool:
    """Descarta o que o Telegram linka mas não é o artigo: imagem do post e
    palavra autolinkada do texto ('Hoteis.com' vira http://Hoteis.com)."""
    partes = urlsplit(url)
    if partes.path.lower().endswith(IMAGENS):
        return False
    return bool(partes.query) or len(partes.path.strip("/")) > 1


class TelegramChannelSource:
    def __init__(
        self,
        nome: str,
        canal: str,
        extrair: Callable[[Post], Optional[Deal]],
        ja_visto: Callable[[str], bool],
    ):
        self.nome = nome
        self.canal = canal
        self._extrair = extrair
        self._ja_visto = ja_visto

    def _mensagens(self) -> list[Post]:
        resposta = requests.get(
            f"https://t.me/s/{self.canal}", headers={"User-Agent": UA}, timeout=30
        )
        resposta.raise_for_status()

        posts = []
        for post_id, corpo in MENSAGEM.findall(resposta.text):
            bloco = BLOCO.search(corpo)
            if not bloco:
                continue  # mensagem sem texto (so foto)
            texto = _limpar(bloco.group(1))
            if not texto:
                continue
            # Dedup pela permalink, nunca pelo link do artigo: promos diferentes
            # do mesmo canal compartilham landing page (12 urls para 20
            # mensagens), e deduplicar pelo link descartaria promo legitimo.
            permalink = f"https://t.me/{post_id}"
            # Ja a url e o link de clique do alerta, entao prefere o artigo.
            links = HREF.findall(bloco.group(1)) or URL_NUA.findall(texto)
            externos = [
                u for u in links
                if "t.me" not in urlsplit(u).netloc and _e_artigo(u)
            ]
            url = _normalizar(externos[0]) if externos else permalink

            linhas = [l for l in texto.split("\n") if l.strip()]
            posts.append(
                Post(
                    titulo=linhas[0][:300],
                    resumo=" ".join(linhas[1:])[:LIMITE_RESUMO],
                    url=url,
                    fonte=self.nome,
                    dedup_key=permalink,
                )
            )
        return posts

    def fetch(self) -> list[Deal]:
        # Filtrar antes de extrair: cada mensagem nova custa uma chamada ao Haiku.
        novas = [p for p in self._mensagens() if not self._ja_visto(p.dedup_key)]
        deals = [self._extrair(p) for p in novas]
        return [d for d in deals if d is not None]
