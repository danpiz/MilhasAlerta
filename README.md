# MilhasAlerta

Monitor de oportunidades de passagens aéreas no Brasil — **com milhas e em reais** — que alerta no
Telegram. Lê os canais públicos dos portais brasileiros, extrai os dados estruturados de cada
mensagem com Claude Haiku e dispara alerta para o que casa com as suas regras.

## Como funciona

```
canais Telegram + RSS  ─▶  dedup (state/seen.json)  ─▶  Haiku extrai  ─▶  regras  ─▶  Telegram
```

O dedup vem antes da extração de propósito: cada post novo custa uma chamada de API, e post repetido
não pode custar de novo.

## Fontes

A fonte principal são os **canais públicos do Telegram**, lidos pela prévia web em `t.me/s/<canal>`
— HTML público, sem token, sem autenticação e sem limite de requisição.

Isso rende mais sinal que o RSS dos mesmos portais. Comparando o que cada um entregava no mesmo dia:

| RSS do Melhores Destinos | Canal do Melhores Destinos |
|---|---|
| "Aeroporto de Campinas instala sistema de passaportes" | "Costa Rica 🇨🇷: 31 mil milhas o trecho" |
| "Bienal do Livro de SP divulga programação" | "Caribe: Latam para Aruba por 34 mil milhas" |

O feed deles é redação; o canal é deal. Os canais também recuperam o **Pontos pra Voar**, cujo RSS
fica atrás do Cloudflare.

Os canais foram escolhidos por medição, não por indicação de blog — vários canais recomendados por
aí estão parados há anos:

| Canal | Situação |
|---|---|
| `melhoresdestinos`, `passageirodeprimeira`, `canalpontospravoar` | ativos, alta densidade de deal ✅ |
| `milhas_sem_segredo` | ativo, foco em acúmulo e transferência ✅ |
| `promopassagens` | **agregador** — reposta os outros, só geraria duplicata ❌ |
| `beconews` | parado há ~11 dias ❌ |
| `decolandocmilhas`, `alertapassagens`, `milhaseviagens` | parados há mais de 2 anos ❌ |

Para checar de novo: `curl -s "https://t.me/s/<canal>" | grep -c tgme_widget_message_text`.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # preencha ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

Para o token do Telegram, fale com o [@BotFather](https://t.me/BotFather). O `TELEGRAM_CHAT_ID` é o
seu chat pessoal ou um canal (`@nomedocanal`).

```bash
.venv/bin/python main.py --dry-run   # lista regras e fontes, sem rede nem API
.venv/bin/python main.py --seed      # PRIMEIRA EXECUÇÃO: marca o backlog sem alertar
.venv/bin/python main.py             # roda de verdade
.venv/bin/python -m pytest tests/    # testes (os live pulam sem ANTHROPIC_API_KEY)
```

Rode `--seed` antes da primeira execução real. As fontes trazem dezenas de posts de backlog, e sem
isso todos viram alerta de uma vez (e todos custam uma chamada de API). O `--seed` não chama o modelo.

## Formato do alerta

Três linhas, sem card de preview — o preview do Telegram expande o link num bloco com foto que
engole o alerta e torna difícil bater o olho e achar a oportunidade.

```
✈️ Rio de Janeiro 🇧🇷 → Buenos Aires 🇦🇷
R$ 307 ou 12k LATAM Pass
Passageiro de Primeira →
```

A origem só aparece quando o post declara — e aí importa: a regra de origem aceita origem ausente,
então sem mostrar, um deal saindo do Rio pareceria de São Paulo. A cabine aparece só quando é
executiva ou primeira.

## Frescor

`max_idade_horas` no [`config.yaml`](config.yaml) descarta post antigo **antes** da extração, então
promoção vencida não vira alerta nem gasta chamada de API. O padrão é 24h. Sem isso o canal, que
sempre expõe as últimas 20 mensagens, faria o backlog inteiro parecer novidade.

## Configuração

Tudo em [`config.yaml`](config.yaml): quais canais e feeds ler, e quais regras disparam alerta.

Adicionar um canal é uma linha em `canais:` — só o handle, sem token. O `dedup_key` de uma mensagem
é a permalink dela (`t.me/canal/1234`), não o link do artigo: promos diferentes do mesmo canal
compartilham landing page, e deduplicar pelo link descartaria mensagem legítima como repetida.

**Todo filtro exige prova**: se o post não afirma o valor, a regra não casa. Sem isso, dado ausente
vira curinga e `cabines: [executiva]` dispara numa econômica de R$ 150.

A única exceção é **`origens`**, que aceita origem ausente — os portais brasileiros omitem a origem
por convenção (*"Voe para Lima a partir de R$ 593"* quase sempre sai de São Paulo), e exigir prova
ali deixaria o monitor mudo.

Entre `max_milhas` e `max_preco_brl` a relação é **OU** — basta um lado estar bom. É o que faz
funcionar um post como *"Lima a partir de R$ 593 ou 24 mil milhas LATAM Pass"*. Entre campos
diferentes é **E**.

Uma regra sem nenhum filtro casa com tudo: é assim que o "firehose" e uma rota específica saem do
mesmo motor, sem código separado.

## Rodando no GitHub Actions

O [workflow](.github/workflows/monitor.yml) roda a cada 30 min e commita o estado de volta no repo.
Configure os secrets `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.

Rode `--seed` e commite o `state/seen.json` **antes** de ligar o agendamento, senão a primeira
execução na nuvem despeja o backlog inteiro no seu Telegram.

O commit de estado a cada rodada tem um efeito colateral útil: o GitHub desativa workflows agendados
após 60 dias sem atividade no repo, e esses commits mantêm o repo vivo sozinho.

## Seats.aero (opcional)

O provider em [`milhasalerta/sources/seats_aero.py`](milhasalerta/sources/seats_aero.py) fica
desligado até existir `SEATS_API_KEY` — exige conta Pro (US$ 9,99/mês). Ele habilita o que o RSS não
faz: monitorar uma rota proativamente ("avise se GRU→Tóquio cair abaixo de 80k") em vez de só
reagir ao que os portais publicam.

> **Não foi exercitado contra a API real.** Valide o retorno antes de confiar nos alertas dele.

## Limites conhecidos

- As fontes entregam deal **publicado**, não monitoramento de rota. Para "avise se GRU→Tóquio cair
  abaixo de 80k", só com o Seats.aero ligado.
- Latência: os portais publicam minutos depois do deal aparecer, e o cron de 30 min soma a isso.
  Trocar RSS por canal não muda isso — o gargalo é o cron, não a fonte.
- `t.me/s/` é uma superfície HTML não documentada. É estável há anos e muito menos frágil que
  raspar companhia aérea, mas quebra se o Telegram mudar a marcação.
- Deal publicado em dois canais diferentes alerta duas vezes: o dedup é por mensagem, não por
  conteúdo. Excluir o agregador `promopassagens` mantém isso raro.

## Créditos

- Esqueleto (loop de checagem, dedup, schema de regras, cliente Seats.aero) adaptado de
  [haiguan28/award-flight-alert](https://github.com/haiguan28/award-flight-alert) (MIT).
- Mapa de programas de fidelidade portado de
  [eduard0vieira/mileage-bot](https://github.com/eduard0vieira/mileage-bot).
- Padrão de GitHub Actions + RSS inspirado em
  [GabrielRF/PromoPassagens](https://github.com/GabrielRF/PromoPassagens).
