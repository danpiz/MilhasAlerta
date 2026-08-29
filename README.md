# MilhasAlerta

Monitor de oportunidades de passagens aéreas no Brasil — **com milhas e em reais** — que alerta no
Telegram. Lê os feeds RSS dos portais brasileiros, extrai os dados estruturados de cada post com
Claude Haiku e dispara alerta para o que casa com as suas regras.

## Como funciona

```
feeds RSS  ─▶  dedup (state/seen.json)  ─▶  Haiku extrai  ─▶  regras  ─▶  Telegram
```

O dedup vem antes da extração de propósito: cada post novo custa uma chamada de API, e post repetido
não pode custar de novo.

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

Rode `--seed` antes da primeira execução real. Os feeds trazem ~60 posts de backlog, e sem isso
todos viram alerta de uma vez (e todos custam uma chamada de API). O `--seed` não chama o modelo.

## Configuração

Tudo em [`config.yaml`](config.yaml): quais feeds ler e quais regras disparam alerta.

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

- RSS entrega deal **publicado**, não monitoramento de rota. Para isso, Seats.aero.
- Latência: os portais publicam minutos depois do deal aparecer, e o cron de 30 min soma a isso.
- `pontospravoar.com` está atrás de Cloudflare e ficou de fora.

## Créditos

- Esqueleto (loop de checagem, dedup, schema de regras, cliente Seats.aero) adaptado de
  [haiguan28/award-flight-alert](https://github.com/haiguan28/award-flight-alert) (MIT).
- Mapa de programas de fidelidade portado de
  [eduard0vieira/mileage-bot](https://github.com/eduard0vieira/mileage-bot).
- Padrão de GitHub Actions + RSS inspirado em
  [GabrielRF/PromoPassagens](https://github.com/GabrielRF/PromoPassagens).
