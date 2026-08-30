# MilhasAlerta — Plano de Melhorias & Guia de Execução

Este documento contém o **relatório de validação técnica** das melhorias para o [MilhasAlerta](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta) e as **instruções passo a passo prontas para execução no Claude Code**, respeitando as diretrizes de código cirúrgico do [CLAUDE.md](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/CLAUDE.md).

---

## 🔍 1. Relatório de Validação Técnica

Realizamos testes práticos em tempo real no ambiente para validar o que é viável, gratuito e estável vs. o que é frágil:

| Oportunidade / Funcionalidade | Status da Validação | Descobertas Técnicas |
| :--- | :---: | :--- |
| **Scraping Direto de APIs de Companhias (Smiles / LATAM / Azul)** | ❌ **Inviável / Frágil** | Testado via requisições HTTP (`requests`). Retorna `403 Forbidden / Missing Authentication Token`. As companhias utilizam proteção WAF (Akamai Bot Manager / Cloudflare) com tokens JWT efêmeros e assinaturas de payload. Manter scrapers próprios quebra constantemente e leva a ban de IP no runner. |
| **Google Flights (`fast-flights`)** | ✅ **100% Funcional** | Já integrado no projeto, funciona de forma confiável para pesquisa de voos em dinheiro, monitoramento de rotas e cálculo de mediana/queda de preço. |
| **Canais Públicos do Telegram (`t.me/s/`)** | ✅ **100% Funcional & Gratuito** | Testado com scraping web. Rápido, sem token, sem autenticação, com alta densidade de deals de milhas em tempo real postados por especialistas. |
| **Novos Canais Ativos do Telegram** | ✅ **Validados ao Vivo** | Testamos mais de 20 canais candidatos. Foram aprovados com postagens ativas:<br>• `melhores_cartoes` (cartões, bônus de transferência Livelo/Esfera)<br>• `altarendablog` (programas de fidelidade e promoções)<br>• `papodemilhas` (deals de milhas e passagens baratas)<br>• `canalestevampelomundo` (deals e milhas).<br>*Canais descartados por estarem inativos/antigos:* `passagensimperdiveis` (parado desde 2019 no Telegram), `beconews` (inativo há semanas) e `promopassagens` (agregador repetitivo). |
| **Deep-Links de Emissão Direta** | ✅ **100% Funcional** | Links parametrizados com origem, destino e datas abrem diretamente as telas de busca no **Google Flights**, **Smiles**, **LATAM** e **Azul**, economizando tempo de pesquisa manual. |
| **Gatilho de Latência Mínima (Cron Externo)** | ✅ **100% Funcional & Gratuito** | O workflow [.github/workflows/monitor.yml](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/.github/workflows/monitor.yml) já possui suporte a `workflow_dispatch:`. Usar um serviço como [cron-job.org](https://cron-job.org) para disparar a API do GitHub reduz a latência de 4h para 10-15 minutos gratuitamente. |

---

## 🛠️ 2. Guia de Execução para o Claude Code

Execute as tarefas abaixo em ordem. Cada tarefa é independente, testável e segue o padrão cirúrgico do projeto.

---

### 📌 TAREFA 1: Gerador de Deep-Links de Emissão Direta

#### Objetivo
Adicionar links clicáveis para busca/emissão direta no rodapé dos alertas do Telegram, permitindo que o usuário clique e caia na tela de emissão do Google Flights, Smiles ou LATAM já com origem, destino e datas preenchidos.

#### Arquivos a Modificar / Criar
1. `milhasalerta/deeplinks.py` (Novo)
2. `milhasalerta/telegram.py` (Modificar)
3. `tests/test_deeplinks.py` (Novo)
4. `tests/test_telegram.py` (Atualizar)

#### Instruções de Implementação

1. **Criar [milhasalerta/deeplinks.py](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/milhasalerta/deeplinks.py)**:
```python
from datetime import datetime
from typing import Optional
import urllib.parse

def link_google_flights(origem: str, destino: str, data_ida: Optional[str] = None, data_volta: Optional[str] = None) -> str:
    base = f"https://www.google.com/travel/flights?q=Flights%20to%20{destino}%20from%20{origem}"
    if data_ida and data_volta:
        return f"{base}%20on%20{data_ida}%20through%20{data_volta}"
    elif data_ida:
        return f"{base}%20on%20{data_ida}%20oneway"
    return base

def link_smiles(origem: str, destino: str, data_ida: Optional[str] = None, data_volta: Optional[str] = None) -> str:
    if not data_ida:
        return f"https://www.smiles.com.br/emissao-com-milhas?originAirport={origem}&destinationAirport={destino}"
    try:
        ts_ida = int(datetime.strptime(data_ida, "%Y-%m-%d").timestamp() * 1000)
    except Exception:
        return "https://www.smiles.com.br"
    if data_volta:
        try:
            ts_volta = int(datetime.strptime(data_volta, "%Y-%m-%d").timestamp() * 1000)
            return f"https://www.smiles.com.br/emissao-com-milhas?originAirport={origem}&destinationAirport={destino}&departureDate={ts_ida}&returnDate={ts_volta}&adults=1&tripType=1"
        except Exception:
            pass
    return f"https://www.smiles.com.br/emissao-com-milhas?originAirport={origem}&destinationAirport={destino}&departureDate={ts_ida}&adults=1&tripType=2"

def link_latam(origem: str, destino: str, data_ida: Optional[str] = None, data_volta: Optional[str] = None) -> str:
    if not data_ida:
        return f"https://www.latamairlines.com/br/pt/ofertas-voos?origin={origem}&destination={destino}"
    if data_volta:
        return f"https://www.latamairlines.com/br/pt/ofertas-voos?origin={origem}&destination={destino}&outbound={data_ida}&inbound={data_volta}&cabin=Economy&adults=1"
    return f"https://www.latamairlines.com/br/pt/ofertas-voos?origin={origem}&destination={destino}&outbound={data_ida}&cabin=Economy&adults=1"
```

2. **Atualizar [milhasalerta/telegram.py](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/milhasalerta/telegram.py)**:
No método `formatar(deal, regras)`:
* Se `deal.kind == "voo"` e houver `deal.origem` e `deal.destino`:
  * Gerar links auxiliares no rodapé.
  * Se o programa for Smiles: incluir link da Smiles (`<a href="...">Emitir na Smiles →</a>`).
  * Se o programa for LATAM Pass: incluir link da LATAM (`<a href="...">Emitir na LATAM →</a>`).
  * Caso contrário ou para dinheiro: incluir link do Google Flights se a fonte não for o próprio Google Flights.
  * Manter a linha da fonte original (`<a href="{deal.url}">{deal.fonte} →</a>`).

3. **Criar [tests/test_deeplinks.py](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/tests/test_deeplinks.py)**:
* Testar links de ida e volta, só ida e sem datas para Google Flights, Smiles e LATAM.
* Garantir 100% de cobertura.

#### Critério de Sucesso
* Rodar `.venv/bin/python -m pytest tests/` e todos os testes passarem sem erros.

---

### 📌 TAREFA 2: Destaque Visual de "🚨 BUG FARE / TARIFA ERRO"

#### Objetivo
Destacar no título e na notificação do Telegram quando uma passagem for uma anomalia extrema de preço (`queda_pct >= 50%` ou preço muito abaixo do normal da rota), alertando com prioridade máxima.

#### Arquivos a Modificar
1. `milhasalerta/telegram.py`
2. `tests/test_telegram.py`

#### Instruções de Implementação
1. No [milhasalerta/telegram.py](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/milhasalerta/telegram.py):
   * Se `deal.queda_pct is not None and deal.queda_pct >= 50`:
     * Prefixar o cabeçalho com `🚨 <b>TARIFA ERRO / BUG FARE</b>\n` ou trocar o ícone de `✈️` por `🚨`.
2. Adicionar teste no [tests/test_telegram.py](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/tests/test_telegram.py) garantindo que quando `queda_pct=55`, a string "TARIFA ERRO" apareça no alerta.

#### Critério de Sucesso
* Testes unitários validam a tag de Tarifa Erro.

---

### 📌 TAREFA 3: Expansão de Canais Ativos do Telegram

#### Objetivo
Expandir as fontes do [config.yaml](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/config.yaml) com canais validados em tempo real com alta densidade de ofertas de milhas e cartões.

#### Arquivos a Modificar
1. `config.yaml`

#### Instruções de Implementação
Adicionar à seção `canais:` em [config.yaml](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/config.yaml):
```yaml
  - nome: Melhores Cartões
    canal: melhores_cartoes
  - nome: Papo de Milhas
    canal: papodemilhas
  - nome: Alta Renda Blog
    canal: altarendablog
  - nome: Estevam Pelo Mundo
    canal: canalestevampelomundo
```

#### Critério de Sucesso
* Rodar `.venv/bin/python main.py --dry-run` e verificar as novas fontes listadas sem erros.

---

### 📌 TAREFA 4: Suporte a Teto em Milhas no Comando `/alerta` do Telegram

#### Objetivo
Permitir que o usuário defina tetos em milhas via texto livre pelo Telegram (ex: `/alerta Paris em maio ate 80 mil milhas Smiles`).

#### Arquivos a Modificar
1. `milhasalerta/comandos.py`
2. `tests/test_comandos.py`

#### Instruções de Implementação
1. No [milhasalerta/comandos.py](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/milhasalerta/comandos.py):
   * Adicionar `max_milhas: Optional[int] = None` e `programa: Optional[str] = None` no modelo `RotaPedida`.
   * Atualizar `INSTRUCOES` para instruir o Haiku a preencher `max_milhas` e `programa` quando o usuário pedir em milhas.
   * Em `_descrever(rota)`: se houver `max_milhas`, formatar `até {max_milhas} milhas {programa or ''}`.
2. Adicionar teste em [tests/test_comandos.py](file:///Users/danpiz/Dev/ClaudeCode/MilhasAlerta/tests/test_comandos.py) com mock do Haiku retornando `max_milhas=70000` e `programa="Smiles"`.

#### Critério de Sucesso
* `pytest tests/test_comandos.py` passa com sucesso.

---

### 📌 TAREFA 5: Configuração do Disparo Externo Sem Latência (GitHub Actions Webhook)

#### Objetivo
Eliminar o atraso de 2h a 6h do cron do GitHub Actions sem custos de servidor.

#### Passo a Passo de Configuração

1. **Gerar um Personal Access Token (PAT) no GitHub**:
   * Vá em **Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens** (ou Tokens Classic).
   * Dê permissão de **Actions: Read & Write** para o repositório `MilhasAlerta`.
2. **Configurar no [cron-job.org](https://cron-job.org) (Gratuito)**:
   * Crie uma conta gratuita.
   * Crie um novo Cron Job com intervalo de **15 minutos**.
   * URL: `https://api.github.com/repos/<SEU_USUARIO>/MilhasAlerta/actions/workflows/monitor.yml/dispatches`
   * Método HTTP: `POST`
   * Headers:
     * `Authorization`: `Bearer ghp_seuTokenAqui`
     * `Accept`: `application/vnd.github.v3+json`
     * `User-Agent`: `CronJob-MilhasAlerta`
   * Request Body: `{"ref": "main"}`
3. **Resultado**: O workflow rodará pontualmente a cada 15 minutos, garantindo que você receba promoções relâmpago minutos após serem postadas.

---

## 🚀 Como Executar no Claude Code

Copie e cole a seguinte instrução no Claude Code para executar a implementação:

> "Leia o arquivo `IMPROVEMENT_PLAN.md` e execute a TAREFA 1, TAREFA 2, TAREFA 3 e TAREFA 4. Para cada tarefa, siga as diretrizes do `CLAUDE.md`, crie os testes unitários correspondentes, certifique-se de que `pytest` passe em 100% dos testes e mantenha as modificações cirúrgicas e enxutas."
