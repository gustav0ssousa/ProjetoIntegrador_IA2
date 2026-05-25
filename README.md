# Projeto Integrador IA2 - GeoRisk

Sistema de monitoramento de risco de deslizamento com ESP32, sensores físicos, API FastAPI, MongoDB e dashboard React/Vite.

O projeto integra dados de higrômetro, sensor de vibração e MPU6050. A ESP32 envia leituras consolidadas para a API, a API persiste no MongoDB e o frontend apresenta os indicadores em um painel inspirado no dashboard `sensores_pi`.

## Arquitetura

```text
ESP32 MicroPython
  -> POST /leituras
FastAPI backend
  -> MongoDB
React/Vite frontend
  -> GET /leituras, /analytics, /alerts, /predictions
```

## Estrutura

```text
backend/        API FastAPI, modelos, risco, analytics e testes
frontend/       Dashboard React/Vite
src/            Firmware MicroPython principal da ESP32
boot.py         Funções auxiliares de boot/conexão
higrometro/     Projeto Arduino/PlatformIO usado como referência do dispositivo
sensores_pi/    Frontend/API Next.js usado como referência de integração
docker-compose.yml
```

Documentos complementares:

- [Markdowns.md](Markdowns.md): integração do frontend.
- [Integracao_API_sensores_pi.md](Integracao_API_sensores_pi.md): integração da API `sensores_pi`.
- [Implementacao_Dispositivo_Higrometro.md](Implementacao_Dispositivo_Higrometro.md): implementação do dispositivo.
- [Testes_Maquete_Acrilico.md](Testes_Maquete_Acrilico.md): roteiro de testes com morro em caixa de acrilico.

## Requisitos

- Docker Desktop ou Docker Engine.
- ESP32 com MicroPython gravado.
- `mpremote` para copiar arquivos para a ESP32.
- Python 3.11+ e Node.js 20+ são necessários somente para executar backend/frontend fora dos containers.

## Execução Com Docker

Todos os serviços da aplicação web estão conteinerizados:

| Serviço | Container | Porta |
|---|---|---:|
| MongoDB | `projeto-integrador-mongodb` | `27017` |
| Backend FastAPI | `projeto-integrador-backend` | `8000` |
| Frontend React/Nginx | `projeto-integrador-frontend` | `5173` |

Suba tudo pela raiz do projeto:

```powershell
docker compose up --build -d
```

Acompanhe os logs:

```powershell
docker compose logs -f
```

Abra:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
Docs API: http://localhost:8000/docs
MongoDB:  mongodb://localhost:27017
```

Verifique o estado dos containers:

```powershell
docker compose ps
```

Parar os serviços:

```powershell
docker compose down
```

Remover também o volume do MongoDB:

```powershell
docker compose down -v
```

O `docker-compose.yml` configura o backend para acessar o MongoDB pela rede interna Docker:

```text
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=deslizamentos_iot
MONGODB_COLLECTION=leituras
```

O frontend é compilado com `VITE_API_URL=http://localhost:8000` por padrão, porque a chamada HTTP é feita pelo navegador na máquina host. Para acessar o dashboard a partir de outro computador da rede, gere o build informando o IP da máquina que roda o backend:

```powershell
VITE_API_URL=http://IP_DA_MAQUINA:8000 docker compose up --build -d frontend
```

Depois de mudar `VITE_API_URL`, reconstrua o frontend.

## Backend

Endpoints principais:

- `GET /health`
- `POST /leituras`
- `GET /leituras`
- `GET /leituras/export/csv`
- `GET /simulacoes`
- `POST /api/sensors`
- `GET /api/sensors`
- `POST /mqtt/webhook`
- `GET /analytics`
- `GET /alerts`
- `GET /limits`
- `GET /predictions`

Execução local sem Docker, opcional:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Use `backend/.env.example` como referência se rodar fora do Compose.

## Frontend

Execução local sem Docker, opcional:

```powershell
cd frontend
npm install
npm run dev
```

Abra:

```text
http://localhost:5173
```

Por padrão o frontend usa:

```text
http://localhost:8000
```

Para alterar, crie `frontend/.env`:

```text
VITE_API_URL=http://localhost:8000
```

Build de produção:

```powershell
npm run build
```

## Firmware ESP32

O firmware principal fica em:

```text
src/main.py
```

Crie a configuração local:

```powershell
Copy-Item src\config.example.py src\config.py
```

Edite `src/config.py`:

```python
CONFIG = {
    "wifi_ssid": "NOME_DA_REDE",
    "wifi_password": "SENHA_DA_REDE",
    "api_url": "http://IP_DO_BACKEND:8000/leituras",
    "api_key": "",
    "device_id": "esp32-sensores-01",
    "send_interval_ms": 3000,
    "moisture_dry_adc": 4095,
    "moisture_wet_adc": 1500,
    "moisture_wet_threshold": 3400,
    "moisture_digital_active_low": True,
    "moisture_use_digital_wet": False,
    "vibration_active_high": False,
    "vibration_sample_count": 25,
    "vibration_event_samples": 0,
    "vibration_sample_delay_ms": 4,
    "vibration_edge_threshold": 4,
    "vibration_continuous_windows": 2,
    "acceleration_attention_threshold_g": 0.4,
    "acceleration_alert_threshold_g": 0.7,
    "buzzer_active_high": True,
    "buzzer_pulse_moisture_min_threshold": 2400,
    "buzzer_continuous_moisture_threshold": 3400,
    "buzzer_normal_pulse_ms": 80,
    "buzzer_normal_interval_ms": 5000,
}
```

Use o IP local do computador que roda o backend, não `localhost`.

Envie os arquivos para a ESP32:

```powershell
mpremote connect COM5 cp boot.py :boot.py
mpremote connect COM5 cp src/config.py :config.py
mpremote connect COM5 cp src/main.py :main.py
mpremote connect COM5 reset
mpremote connect COM5 repl
```

Troque `COM5` pela porta real da placa.

## Sensores

Pinagem usada pelo firmware:

| Componente | GPIO |
|---|---:|
| HW-103A AO | 34 |
| HW-103A DO | 27 |
| Buzzer | 25 |
| SW-520 | 26 |
| MPU6050 SDA | 21 |
| MPU6050 SCL | 22 |

O firmware envia uma leitura consolidada para `POST /leituras`, com:

- aceleração em `g`;
- giroscópio em `graus/s`;
- umidade normalizada `0-4095`, onde maior valor significa mais umidade para as predições;
- ADC bruto do HW-103A, estado digital, amostras, bordas e sequência do SW-520 em campos próprios e em `observacoes_experimento`;
- `mpu_motion_g`, movimento calculado em relação ao repouso, usando os limiares `0.400 g` e `0.700 g`;
- `inclinacao = 1` quando o SW-520 detectar variação rápida e contínua, configurada por `vibration_edge_threshold` e `vibration_continuous_windows`;
- observações técnicas do ciclo em `observacoes_experimento`.

No boot, o firmware imprime um diagnóstico do SW-520 com GPIO, valor bruto inicial, polaridade e status da interrupção. Durante a execução, observe `bordas`, `irq` e `polling`: se esses valores continuarem `0` mesmo com vibração forte, revise VCC, GND, DO no GPIO 26, polaridade `vibration_active_high` e se o firmware novo foi enviado para a ESP32.

O buzzer usa tres comportamentos pela umidade normalizada: abaixo de `2400` fica sem som; de `2400` ate `3399` usa pulso curto e espacado, configurado por `buzzer_normal_pulse_ms` e `buzzer_normal_interval_ms`; a partir de `buzzer_continuous_moisture_threshold` usa sinal continuo. Pelo MPU6050, movimento ate `0.400 g` fica normal, acima de `0.400 g` ate `0.700 g` gera pulso de atencao, e acima de `0.700 g` gera alerta continuo. Vibracao continua do SW-520 tambem aciona sinal continuo.

Para calibrar a maquete, anote o AO do HW-103A com o solo seco e depois com o solo saturado. Use esses valores em `moisture_dry_adc` e `moisture_wet_adc`. Em muitos módulos resistivos o AO fica menor quando há mais água, por isso o firmware converte a leitura para uma escala preditiva crescente.

O pino digital `DO` do HW-103A depende do trimpot do módulo e pode inverter a leitura. Por padrão, `moisture_use_digital_wet` fica `False`, então o firmware usa o `AO` normalizado para decidir se o solo está molhado e imprime o `DO` apenas como diagnóstico.

## Testes

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest
```

Frontend:

```powershell
cd frontend
npm run build
```

Firmware:

```powershell
python -m compileall src
```

## Fluxo De Execução Local

1. Subir MongoDB, backend e frontend:

```powershell
docker compose up --build -d
```

2. Configurar `src/config.py` com o IP da máquina que expõe o backend em `8000`.

3. Enviar firmware para a ESP32.

4. Validar dados:

```text
http://localhost:8000/docs
http://localhost:5173
```

## Segurança E Boas Práticas

- Não versionar `src/config.py`, `.env` ou senhas reais.
- Usar IP da máquina na rede para a ESP32 acessar a API.
- Calibrar `moisture_wet_threshold` com solo seco e molhado reais.
- Confirmar a polaridade do sensor de vibração antes de usar em demonstração.
- Manter `higrometro/` e `sensores_pi/` como referências, não como apps principais da raiz.
