# Implementacao do dispositivo `higrometro`

## Passo 1 - Diagnostico da pasta

Status: concluido em 2026-05-18.

### Estrutura encontrada

- `higrometro/platformio.ini`: projeto PlatformIO para ESP32 usando framework Arduino.
- `higrometro/src/main.cpp`: firmware principal atual.
- `higrometro/src/copia_main.txt`: versao anterior do firmware usando biblioteca `Adafruit_MPU6050`.
- `higrometro/src/comandos.txt`: comandos manuais antigos de upload/monitor.
- `higrometro/include/`, `higrometro/lib/`, `higrometro/test/`: estrutura padrao do PlatformIO.
- `higrometro/.pio/` e `higrometro/.vscode/`: arquivos gerados/localmente pelo PlatformIO.

### Configuracao PlatformIO atual

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200

lib_deps =
  adafruit/Adafruit MPU6050
  adafruit/Adafruit Unified Sensor
```

Observacao: o `main.cpp` atual le o MPU6050 por I2C bruto, usando `Wire.h`, entao as bibliotecas Adafruit ainda estao declaradas, mas nao sao usadas diretamente nessa versao.

## Hardware mapeado

### Placa

- ESP32 DevKit (`esp32dev` no PlatformIO).
- Serial monitor em `115200`.

### Sensores e atuadores

| Componente | Pino ESP32 | Uso |
|---|---:|---|
| Higrometro analogico `AO` | GPIO 34 | `analogRead`, leitura bruta 0-4095 |
| Higrometro digital `DO` | GPIO 27 | `digitalRead`, estado digital do modulo |
| Buzzer | GPIO 25 | Alarme local |
| Sensor de vibracao | GPIO 26 | Entrada digital com `INPUT_PULLUP` |
| MPU6050 SDA | GPIO 21 | Barramento I2C |
| MPU6050 SCL | GPIO 22 | Barramento I2C |

### Limites locais

- `LIMITE_MOLHADO = 3800`
- No firmware atual:
  - `wet = ao < LIMITE_MOLHADO`
  - `buzzerOn = wet || vibrando || magnitude > 12.0`

Ponto de atencao: o backend da raiz interpreta maior umidade/risco a partir de valores ADC mais altos em `risk.py`. O firmware atual considera solo molhado quando `ao < 3800`. Antes de calibrar a maquete, essa diferenca precisa ser validada com leituras reais do sensor.

## Comportamento do firmware atual

### Inicializacao

1. Inicia `Serial` em `115200`.
2. Configura pinos:
   - `PINO_SENSOR_AO` como entrada.
   - `PINO_SENSOR_DO` como entrada.
   - `PINO_BUZZER` como saida.
   - `PINO_VIBRACAO` como `INPUT_PULLUP`.
3. Inicializa I2C em SDA `21` e SCL `22`.
4. Tenta acordar o MPU6050 no endereco `0x68`.
5. Conecta ao Wi-Fi.

### Loop principal

A cada ciclo:

1. Le higrometro analogico e digital.
2. Le sensor de vibracao.
3. Le acelerometro, giroscopio e temperatura do MPU6050, se conectado.
4. Calcula magnitude da aceleracao.
5. Liga ou desliga o buzzer.
6. Exibe diagnostico no monitor serial.
7. A cada `3000 ms`, envia tres payloads HTTP:
   - `humidity`
   - `vibration`
   - `accelerometer`

## Integracao com a API da raiz

### Endpoint atual no firmware

O firmware aponta para um endpoint no formato:

```cpp
const char* serverUrl = "http://<IP_DO_SERVIDOR>:3000/api/sensors";
```

Como a API integrada da raiz agora esta em FastAPI, o destino recomendado e:

```cpp
const char* serverUrl = "http://<IP_DO_BACKEND>:8000/api/sensors";
```

Exemplo em rede local:

```cpp
const char* serverUrl = "http://192.168.0.10:8000/api/sensors";
```

### Compatibilidade ja implementada no backend

O backend da raiz ja aceita os payloads enviados pelo `higrometro`:

- `POST /api/sensors` para `humidity`, `vibration` e `accelerometer`.
- `POST /mqtt/webhook` para payloads equivalentes via broker/bridge MQTT.
- `GET /api/sensors` para retorno no formato `sensorType`.
- `GET /analytics`, `/alerts`, `/limits` e `/predictions` para consumo futuro.

## Payloads enviados pelo dispositivo

### Higrometro

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
    "wet": true,
    "buzzerOn": true,
    "limiteMolhado": 3800
  }
}
```

### Vibracao

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

### Acelerometro

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
    "mpuConectado": true,
    "magnitude": 9.81,
    "giroscopioX": 0.1,
    "giroscopioY": 0.2,
    "giroscopioZ": 0.3,
    "temperatura": 28.4
  }
}
```

## Configuracoes sensiveis

O `main.cpp` atual contem SSID, senha de Wi-Fi, URL da API e chave de API diretamente no codigo.

Para documentacao e evolucao, usar sempre placeholders:

```cpp
const char* ssid = "NOME_DA_REDE";
const char* password = "SENHA_DA_REDE";
const char* serverUrl = "http://IP_DO_BACKEND:8000/api/sensors";
const char* apiKey = "CHAVE_OPCIONAL";
```

Recomendacao para o proximo passo:

- mover credenciais para um arquivo local ignorado pelo Git, como `secrets.h`;
- manter um `secrets.example.h` versionado;
- evitar registrar SSID/senha reais em documentacao, commits ou prints.

## Passo 2 - Implementacao na raiz

Status: concluido em 2026-05-18.

### Objetivo

Trazer a configuracao do dispositivo para a organizacao da raiz, mantendo compatibilidade com a API FastAPI ja integrada.

### Decisao de implementacao

A logica de coleta do `higrometro/src/main.cpp` foi portada para o firmware MicroPython da raiz em `src/main.py`.

Em vez de enviar tres documentos parciais para `/api/sensors`, a raiz agora envia uma leitura consolidada para:

```text
POST /leituras
```

Isso preserva o contrato principal do backend da raiz e grava um documento unico contendo:

- umidade do solo;
- vibracao/inclinacao;
- aceleracao;
- giroscopio;
- observacoes tecnicas do ciclo.

### Arquivos alterados

- `src/main.py`: firmware MicroPython com leitura do higrometro, sensor de vibracao, buzzer e MPU6050.
- `src/config.example.py`: exemplo de configuracao local.
- `.gitignore`: ignora `src/config.py`, para evitar versionar credenciais reais.

### Configuracao local

Criar um arquivo local `src/config.py` baseado em `src/config.example.py`:

```python
CONFIG = {
    "wifi_ssid": "NOME_DA_REDE",
    "wifi_password": "SENHA_DA_REDE",
    "api_url": "http://IP_DO_BACKEND:8000/leituras",
    "api_key": "",
    "device_id": "esp32-sensores-01",
    "send_interval_ms": 3000,
    "moisture_wet_threshold": 3800,
    "vibration_active_high": True,
    "acceleration_alert_ms2": 12.0,
}
```

### Dados enviados para a raiz

Payload consolidado:

```json
{
  "id_simulacao": "esp32-sensores-01",
  "aceleracao_x": 0.01,
  "aceleracao_y": 0.02,
  "aceleracao_z": 1.0,
  "giroscopio_x": 0.1,
  "giroscopio_y": 0.2,
  "giroscopio_z": 0.3,
  "umidade_solo": 2480,
  "inclinacao": 0,
  "evento_deslizamento": false,
  "observacoes_experimento": "higrometro_ao=2480; higrometro_do=0; wet=True; vibracao_raw=0; mpu_temp=28.4; magnitude_ms2=9.81"
}
```

### Regras aplicadas

- `umidade_solo` recebe o valor analogico do higrometro (`AO`).
- `inclinacao` recebe `1` quando o sensor de vibracao acusa evento.
- `evento_deslizamento` recebe `true` somente quando houver vibracao ou magnitude acima do limite configurado.
- Solo molhado nao marca `evento_deslizamento` diretamente; ele influencia o risco via `umidade_solo`.
- Aceleracao e giroscopio sao lidos do MPU6050 por I2C bruto.
- Aceleracao e enviada em `g`, que e o formato esperado pela heuristica atual do backend.

### Validacao executada

Comando:

```powershell
python -m compileall src
```

Resultado:

- `src/main.py` compila sem erro de sintaxe.
- `src/config.example.py` compila sem erro de sintaxe.

## Passo 3 - Validacao em bancada

Status: aguardando comando.

### Caminho recomendado

1. Decidir o alvo do firmware:
   - alvo atual definido como MicroPython na raiz.
2. Copiar `src/config.example.py` para `src/config.py`.
3. Preencher Wi-Fi e IP real do backend.
4. Enviar `boot.py`, `src/config.py` e `src/main.py` para a ESP32.
5. Calibrar sensores:
   - registrar valores `ao` em solo seco;
   - registrar valores `ao` em solo umido;
   - validar se o limite `3800` faz sentido;
   - alinhar os limites com `backend/app/risk.py`.
6. Validar polaridade do sensor de vibracao:
   - o firmware atual usa `vibrando = digitalRead(PINO_VIBRACAO) == HIGH`;
   - alguns modulos podem sinalizar evento em `LOW`;
   - confirmar no monitor serial antes de fixar a regra.
7. Validar MPU6050:
   - confirmar endereco I2C `0x68`;
   - confirmar `WHO_AM_I`;
   - comparar leitura parada com aproximadamente `z ~= 9.8 m/s2`.
8. Testar envio real:
   - backend rodando em `:8000`;
   - MongoDB ativo;
   - ESP32 na mesma rede;
   - monitor serial aberto em `115200`.

## Comandos de build e upload

### Firmware antigo Arduino/PlatformIO

Executar dentro da pasta `higrometro/`, caso seja necessario voltar ao firmware Arduino:

```powershell
platformio run
platformio run --target upload
platformio device monitor --baud 115200
```

Se for necessario informar a porta:

```powershell
platformio run --target upload --upload-port COM5
platformio device monitor --port COM5 --baud 115200
```

### Firmware atual MicroPython da raiz

Com `mpremote`, a partir da raiz do projeto:

```powershell
mpremote connect COM5 cp boot.py :boot.py
mpremote connect COM5 cp src/config.py :config.py
mpremote connect COM5 cp src/main.py :main.py
mpremote connect COM5 reset
mpremote connect COM5 repl
```

Troque `COM5` pela porta real da ESP32.

## Checklist de validacao em bancada

- ESP32 liga e abre serial em `115200`.
- Wi-Fi conecta e imprime IP local.
- MPU6050 responde no I2C.
- Higrometro altera `AO` ao trocar seco/molhado.
- `DO` do higrometro muda quando o trimpot do modulo e ajustado.
- Sensor de vibracao muda estado quando acionado.
- Buzzer liga nas condicoes esperadas.
- API responde `201` no envio para `/api/sensors`.
- `GET /leituras` mostra documentos persistidos.
- `GET /api/sensors` mostra leituras no formato esperado pelo frontend de origem.

## Riscos tecnicos observados

- Credenciais hardcoded no firmware.
- Endpoint atual aponta para `:3000`, mas a API da raiz usa `:8000`.
- `apiKey` enviada pelo firmware nao e validada atualmente pelo FastAPI da raiz.
- Bibliotecas Adafruit estao declaradas no PlatformIO, mas o firmware atual usa I2C bruto.
- O firmware envia tres documentos separados por ciclo; isso funciona com a camada de compatibilidade, mas pode gerar leituras parciais no banco.
- A regra de umidade do firmware pode estar invertida em relacao aos limites atuais do backend.
- A polaridade do sensor de vibracao precisa ser confirmada com o modulo real.
