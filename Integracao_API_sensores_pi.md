# Integracao da API de `sensores_pi` na raiz

## Passo 1 - Diagnostico da pasta `sensores_pi/app/api`

Status: concluido em 2026-05-18.

### Premissa

Este documento trata somente da integracao da pasta `sensores_pi/app/api` ao projeto raiz.

A raiz deve continuar organizada assim:

- `backend/`: API principal em FastAPI.
- `frontend/`: aplicacao React/Vite.
- `src/`: firmware MicroPython.
- `docker-compose.yml`: containerizacao do projeto.

Portanto, as rotas de `sensores_pi/app/api` nao devem ser copiadas como rotas Next.js. Elas devem ser reinterpretadas e portadas para o backend FastAPI existente.

## Rotas encontradas em `sensores_pi/app/api`

### `sensors`

Origem:

- `sensores_pi/app/api/sensors/route.ts`
- `sensores_pi/app/api/sensors/stream/route.ts`

Funcoes atuais:

- `POST /api/sensors`: recebe payloads por tipo de sensor (`humidity`, `vibration`, `accelerometer`) e salva no MongoDB.
- `GET /api/sensors`: lista as ultimas leituras salvas.
- `GET /api/sensors/stream`: cria stream Server-Sent Events para leituras em tempo real.

Ponto de adaptacao:

- O backend da raiz ja usa `POST /leituras` com schema unificado `sensores`.
- A integracao deve criar compatibilidade com payloads do tipo `sensorType/value/metadata`, convertendo para o formato `LeituraCreate` da raiz.

### `analytics`

Origem:

- `sensores_pi/app/api/analytics/route.ts`

Funcoes atuais:

- Consulta leituras no MongoDB.
- Separa leituras por `sensorType`.
- Calcula pontuacao de risco com base em umidade, vibracao e acelerometro.
- Retorna resumo, sensores atuais, historico para grafico e historico completo.

Ponto de adaptacao:

- A raiz ja calcula `nivel_alerta` em `backend/app/risk.py`.
- A rota pode virar `GET /analytics` ou `GET /leituras/analytics`, usando os documentos atuais da colecao `leituras`.
- O calculo deve usar `sensores.umidade_solo`, `sensores.inclinacao`, aceleracao e giroscopio, em vez de `sensorType`.

### `history`

Origem:

- `sensores_pi/app/api/history/route.ts`

Funcoes atuais:

- Gera dados historicos simulados por periodo e tipo de sensor.
- Tem comentarios indicando que a versao de producao deveria consultar MongoDB.

Ponto de adaptacao:

- A raiz ja possui `GET /leituras` com filtros por `inicio`, `fim`, `limit`, `offset` e `id_simulacao`.
- A integracao deve evitar dados simulados.
- Caso necessario, criar uma rota de conveniencia como `GET /history`, mas internamente ela deve consultar a colecao real.

### `alerts`

Origem:

- `sensores_pi/app/api/alerts/route.ts`

Funcoes atuais:

- Retorna alertas simulados.
- Permite criar alerta.
- Tem comentarios para persistencia futura em MongoDB.

Ponto de adaptacao:

- O backend da raiz ja registra `nivel_alerta` e `evento_deslizamento`.
- A rota pode ser portada como `GET /alerts`, derivando alertas reais de leituras com `nivel_alerta != verde` ou `evento_deslizamento = true`.
- Persistencia separada de alertas deve ser opcional e evitada inicialmente para manter a raiz simples.

### `limits`

Origem:

- `sensores_pi/app/api/limits/route.ts`

Funcoes atuais:

- Mantem limites de alerta em memoria.
- `GET` retorna limites atuais.
- `PUT` atualiza limites com validacao basica.

Ponto de adaptacao:

- A raiz atualmente tem limites fixos em `backend/app/risk.py`.
- A integracao pode seguir em duas fases:
  - Fase simples: expor `GET /limits` com os limites padrao do backend.
  - Fase persistente: salvar limites em uma colecao `settings` no MongoDB e fazer `risk.py` usar configuracao dinamica.

### `mqtt/webhook`

Origem:

- `sensores_pi/app/api/mqtt/webhook/route.ts`

Funcoes atuais:

- Recebe payload de broker MQTT por HTTP.
- Extrai `sensorType` do topico.
- Monta leitura no formato `sensorId`, `sensorType`, `value`, `unit`, `metadata`.

Ponto de adaptacao:

- Pode ser portado como `POST /mqtt/webhook`.
- Deve reutilizar o mesmo normalizador de `POST /api/sensors`.
- Deve salvar no formato real da raiz, preferencialmente chamando uma funcao compartilhada de criacao de leitura.

### `predictions`

Origem:

- `sensores_pi/app/api/predictions/route.ts`

Funcoes atuais:

- Atua como proxy para `http://127.0.0.1:8000/predictions`.
- Retorna erro caso o servico Python de predicao nao responda.

Ponto de adaptacao:

- Como a raiz ja e FastAPI, nao faz sentido manter proxy Next.js.
- A rota deve ser implementada diretamente no backend como `GET /predictions`.
- O conteudo preditivo pode ser inspirado em `sensores_pi/sevicos/servicos.py`, mas esta parte pertence ao backend, nao a `app/api`.

### `debug-db`

Origem:

- `sensores_pi/app/api/debug-db/route.ts`

Funcoes atuais:

- Inspeciona conexao, banco, colecoes e quantidade de documentos.

Ponto de adaptacao:

- A raiz ja tem `GET /health`.
- Se necessario, criar `GET /debug/db` somente para desenvolvimento.
- Evitar expor detalhes sensiveis em producao.

## Passo 2 - Plano de integracao na API raiz

Status: concluido em 2026-05-18.

### Objetivo

Portar os comportamentos uteis de `sensores_pi/app/api` para `backend/`, sem adicionar Next.js ao backend e sem alterar a estrutura principal do projeto.

### Arquivos provaveis de alteracao

- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/risk.py`
- possivelmente um novo modulo `backend/app/sensor_compat.py`
- possivelmente um novo modulo `backend/app/analytics.py`
- `backend/tests/`, para cobrir compatibilidade dos novos endpoints

### Decisoes tomadas

- `POST /api/sensors` aceita leituras parciais de `humidity`, `vibration` e `accelerometer`.
- Leituras parciais sao convertidas para o schema unificado `LeituraCreate` usando defaults seguros.
- `accelerometer` em `m/s2` e convertido para `g`, mantendo compatibilidade com a heuristica atual de `backend/app/risk.py`.
- `limits` foi implementado inicialmente como leitura estatica em memoria.
- `predictions` foi implementado com regressao linear simples em Python puro, sem novas dependencias como `numpy` ou `scikit-learn`.
- `alerts` e `analytics` sao derivados das leituras reais ja persistidas na colecao `leituras`.

### Ordem executada

1. Criar normalizador de payloads externos:
   - entrada `sensorType/value/metadata`;
   - saida compativel com `LeituraCreate`.
2. Adicionar endpoint compativel:
   - `POST /api/sensors`;
   - `GET /api/sensors`.
3. Adicionar webhook MQTT:
   - `POST /mqtt/webhook`;
   - conversao para o mesmo fluxo de leituras.
4. Adicionar analytics:
   - `GET /analytics`;
   - resumo baseado nas leituras reais da raiz.
5. Adicionar alerts:
   - `GET /alerts`;
   - derivado de `nivel_alerta` e `evento_deslizamento`.
6. Adicionar limits:
   - `GET /limits` inicialmente estatico;
   - `PUT /limits` somente se for decidido persistir configuracoes.
7. Adicionar predictions:
   - `GET /predictions`;
   - implementacao direta em Python/FastAPI.
8. Validar com testes:
   - payload de umidade;
   - payload de vibracao via MQTT;
   - payload de acelerometro;
   - resposta de analytics e alerts.

### Arquivos alterados

- `backend/app/sensor_compat.py`: normalizacao dos payloads de `sensores_pi` e MQTT para `LeituraCreate`, alem de conversao de leituras da raiz para formato `sensorType`.
- `backend/app/analytics.py`: analytics, limites estaticos e predicoes sem dependencias novas.
- `backend/app/main.py`: novas rotas FastAPI compativeis com `sensores_pi/app/api`.
- `backend/tests/test_api.py`: testes dos novos contratos.

### Rotas implementadas

- `POST /api/sensors`
- `GET /api/sensors`
- `POST /mqtt/webhook`
- `GET /analytics`
- `GET /alerts`
- `GET /limits`
- `GET /predictions`
- `GET /debug/db`

### Validacao

Comando executado:

```bash
.\.venv\Scripts\python.exe -m pytest
```

Resultado:

- 8 testes executados.
- 8 testes passaram.
- Cobertura funcional adicionada para payload `humidity`, payload `accelerometer`, webhook MQTT e rotas `analytics`/`alerts`.

## Contratos de compatibilidade sugeridos

### Payload `humidity`

```json
{
  "sensorId": "esp32-higrometro-01",
  "sensorType": "humidity",
  "value": 2480,
  "unit": "raw",
  "metadata": {
    "deviceId": "esp32-sensores-01",
    "ao": 2480,
    "d0": 0,
    "wet": true
  }
}
```

### Payload `vibration`

```json
{
  "sensorId": "esp32-vibracao-01",
  "sensorType": "vibration",
  "value": 1,
  "unit": "status",
  "metadata": {
    "deviceId": "esp32-sensores-01",
    "digitalRead": 1,
    "vibrando": true
  }
}
```

### Payload `accelerometer`

```json
{
  "sensorId": "esp32-acelerometro-01",
  "sensorType": "accelerometer",
  "value": {
    "x": 0.12,
    "y": 0.03,
    "z": 9.81
  },
  "unit": "m/s2",
  "metadata": {
    "deviceId": "esp32-sensores-01",
    "giroscopioX": 0.1,
    "giroscopioY": 0.2,
    "giroscopioZ": 0.3
  }
}
```

## Regras de conversao sugeridas

- `humidity`:
  - `umidade_solo` recebe `metadata.ao` ou `value`.
  - demais sensores recebem ultimo valor conhecido, valor padrao seguro, ou exigem payload combinado em fase posterior.
- `vibration`:
  - `inclinacao` pode receber `1` quando `vibrando/detected` for verdadeiro, se nao houver sensor dedicado de inclinacao.
  - registrar observacao indicando origem `vibration`.
- `accelerometer`:
  - `aceleracao_x/y/z` recebe `value.x/y/z`.
  - `giroscopio_x/y/z` recebe `metadata.giroscopioX/Y/Z`.
- `id_simulacao`:
  - usar `metadata.deviceId`, quando existir;
  - caso contrario, usar valor padrao `esp32-sensores-01`.

## Decisoes pendentes para evolucao

- Avaliar se `limits` deve ser persistido no MongoDB com `PUT /limits`.
- Avaliar se `predictions` deve evoluir para um servico com `numpy`/`scikit-learn`.
- Avaliar se `GET /api/sensors/stream` deve ser implementado com Server-Sent Events no FastAPI.

## Passo 3 - Proxima etapa sugerida

Status: aguardando comando.

### Objetivo

Conectar o frontend adaptado aos endpoints especificos da API integrada quando fizer sentido:

- usar `/analytics` para paineis consolidados;
- usar `/alerts` para notificacoes;
- usar `/predictions` para a aba de predicoes;
- manter `/leituras` como fonte principal de compatibilidade com o painel atual.
