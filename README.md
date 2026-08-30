# MilhasAlerta

Monitor de oportunidades de passagens aéreas no Brasil — **com milhas e em reais** — que alerta no
Telegram. Lê os canais públicos dos portais brasileiros, extrai os dados estruturados de cada
mensagem com Claude Haiku e dispara alerta para o que casa com as suas regras.

## Como funciona

```
canais Telegram + RSS  ─▶  dedup  ─▶  Haiku extrai  ─┐
                                                     ├─▶  regras  ─▶  Telegram
Google Flights (rotas vigiadas)  ─▶  histórico  ─────┘
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

## Criando alertas pelo Telegram

Editar YAML e dar push para vigiar uma rota é atrito demais, então dá para falar com o bot:

```
/alerta voos pra Portugal em janeiro de 2027 ida e volta economica
/alertas          → lista os ativos, numerados
/remover 1        → apaga
```

O texto livre vira uma rota vigiada com a mesma estrutura do `config.yaml`, então o motor não
precisa saber de onde ela veio. O que você não disser tem padrão: origem GRU, 12 dias de viagem,
ida e volta, econômica.

Sem teto de preço no pedido, o gatilho vira queda contra o histórico da rota — e isso **leva alguns
dias para começar a valer**, porque antes disso ele ainda não sabe quanto a rota costuma custar.
Para alerta imediato, dê um teto: `/alerta Portugal em janeiro ate 4000 reais`.

> **A confirmação demora.** Sem um processo sempre ligado, o bot só lê suas mensagens quando o cron
> roda — e o agendamento do GitHub entrega bem menos do que o cron pede. Medido neste repo:
> ~1 execução a cada 4h, não a cada 30 min como configurado. Mande e esqueça; a confirmação chega.

## Rotas vigiadas

As fontes acima **reagem** ao que os portais publicaram. O Google Flights é a única que **consulta**
uma rota — responde "avise se Europa cair abaixo de R$ 2.500", que os canais não conseguem.

```yaml
rotas:
  - nome: Europa a partir de SP
    origens: [GRU]
    destinos: europa        # ou lista: [LIS, CDG]
    max_preco_brl: 2500     # teto que você define
    min_queda_pct: 30       # ou queda contra o preço típico da rota
```

`destinos` aceita código IATA, atalho de região, ou os dois misturados. Atalhos disponíveis em
[`regioes.py`](milhasalerta/regioes.py): `europa`, `america_do_norte`, `america_do_sul`, `asia`,
`africa`, `oceania`.

Os dois gatilhos são complementares: `max_preco_brl` pega o que você já sabe que quer;
`min_queda_pct` pega o que você não saberia pedir. A queda só passa a disparar depois de algumas
observações — a série vive em `state/seen.json` e usa mediana, porque uma tarifa absurda distorceria
a média e criaria um "normal" que nunca existiu.

**O custo são as datas, não os destinos.** Cada destino × data é uma consulta. Europa são 14
aeroportos; com 6 datas amostradas dá 84 consultas (~90s). Por isso as datas são amostradas — uma
por mês — e a fonte roda a cada `google_cadencia_horas` (padrão 6), não a cada 30 min como o resto.
Ela se estrangula sozinha pelo estado, sem workflow separado: dois workflows commitando o mesmo
`seen.json` brigariam pelo push.

> **É scraping.** Contra os termos do Google, que não oferece API a nenhum preço (a QPX Express
> fechou em 2018), e quebra quando eles mudarem o formato. É a única dependência frágil do projeto;
> tudo mais é feed público ou API documentada. Se o Google bloquear, a fonte falha sozinha e o
> monitor segue pelos canais.
>
> `currency="BRL"` é obrigatório e está fixo no código. O parâmetro é vazio por padrão e o Google
> decide pelo IP — o runner do Actions fica nos EUA e devolvia dólar. Medido: GRU→MIA veio `335` sem
> forçar e `R$ 1.736` com BRL.

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
✈️ São Paulo 🇧🇷 → Lima 🇵🇪
R$ 593 ou 24k LATAM Pass (≈R$ 456)
Passageiro de Primeira →
```

O `(≈R$ 456)` é a conversão das milhas pela cotação do milheiro. Sem ela os dois preços são números
incomparáveis e você faz a conta de cabeça; com ela, 456 < 593 diz na hora que compensa emitir com
milhas. A tabela `milheiro:` fica no [`config.yaml`](config.yaml) — é estimativa, não preço de
mercado, por isso o `≈`, e vale reajustar quando aparecer promoção de compra de pontos.

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

Entre os limites de preço a relação é **OU** — basta um lado estar bom. É o que faz funcionar um post
como *"Lima a partir de R$ 593 ou 24 mil milhas LATAM Pass"*. Entre campos diferentes é **E**.

`max_custo_brl` é o limite mais prático: compara contra o dinheiro **e** contra as milhas
convertidas, então funciona seja como for que o post anunciou o preço.

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

`seats_max_staleness_horas` (padrão 5) descarta registro que o Seats.aero não revê há horas.
Disponibilidade award evapora rápido e o cache deles não — sem o filtro, o provider alerta assento
que já não existe.

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
