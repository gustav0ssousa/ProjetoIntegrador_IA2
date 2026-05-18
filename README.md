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

## Requisitos

- Python 3.11 ou superior recomendado.
- Node.js 20 ou superior recomendado.
- Docker Desktop ou Docker Engine.
- ESP32 com MicroPython gravado.
- `mpremote` para copiar arquivos para a ESP32.

## Configuração Do Banco

Suba o MongoDB pela raiz:

```powershell
docker compose up -d mongodb
```

O MongoDB ficará disponível em:

```text
mongodb://localhost:27017
```

## Backend

Crie e configure o ambiente:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Crie o arquivo `.env` a partir de `backend/.env.example`:

```text
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=deslizamentos_iot
MONGODB_COLLECTION=leituras
```

Rode a API:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa:

```text
http://localhost:8000/docs
```

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

## Frontend

Instale dependências e rode:

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
    "moisture_wet_threshold": 3800,
    "vibration_active_high": True,
    "acceleration_alert_ms2": 12.0,
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
| Higrômetro AO | 34 |
| Higrômetro DO | 27 |
| Buzzer | 25 |
| Vibração | 26 |
| MPU6050 SDA | 21 |
| MPU6050 SCL | 22 |

O firmware envia uma leitura consolidada para `POST /leituras`, com:

- aceleração em `g`;
- giroscópio em `graus/s`;
- umidade como ADC bruto `0-4095`;
- `chuva = 0`, pois o dispositivo atual não possui sensor de chuva;
- `inclinacao = 1` quando houver vibração;
- observações técnicas do ciclo em `observacoes_experimento`.

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

1. Subir MongoDB:

```powershell
docker compose up -d mongodb
```

2. Rodar backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Rodar frontend:

```powershell
cd frontend
npm run dev
```

4. Configurar `src/config.py` com o IP do backend.

5. Enviar firmware para a ESP32.

6. Validar dados:

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

