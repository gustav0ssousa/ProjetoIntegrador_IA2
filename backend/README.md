# API local do projeto

API FastAPI para receber leituras do ESP32, salvar no MongoDB e exportar dados
para dashboard ou analise em Python.

## Subir MongoDB

Na raiz do projeto:

```powershell
docker compose up -d mongodb
```

## Rodar a API

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentacao interativa:

```text
http://localhost:8000/docs
```

No ESP32, use o IP do computador na rede, nao `localhost`.

Exemplo:

```text
http://192.168.0.10:8000/leituras
```

## Payload esperado em `POST /leituras`

```json
{
  "timestamp": "2026-05-07T20:30:00",
  "id_simulacao": "SIM_001",
  "aceleracao_x": 0.02,
  "aceleracao_y": 0.01,
  "aceleracao_z": 1.0,
  "giroscopio_x": 0.1,
  "giroscopio_y": 0.0,
  "giroscopio_z": 0.2,
  "umidade_solo": 720,
  "inclinacao": 0,
  "hw103a_ao": 3375,
  "hw103a_do": 1,
  "hw103a_do_wet": false,
  "sw520_raw": 0,
  "sw520_hits": 0,
  "sw520_edges": 0,
  "sw520_streak": 0,
  "mpu_motion_g": 0.03,
  "evento_deslizamento": false,
  "observacoes_experimento": "Solo argiloso, maquete em condicao estavel."
}
```

`nivel_alerta` e opcional. Quando ele nao for enviado, a API calcula uma
classificacao inicial usando umidade normalizada, vibração contínua do SW-520, movimento do MPU6050 e inclinacao.

## Endpoints principais

- `GET /health`: verifica API e MongoDB.
- `POST /leituras`: recebe uma leitura do ESP32.
- `GET /leituras`: lista leituras com filtros por simulacao e periodo.
- `GET /leituras/{id}`: consulta uma leitura especifica.
- `GET /leituras/export/csv`: exporta leituras em CSV.
- `GET /simulacoes`: resume as simulacoes gravadas.

## Testes

```powershell
cd backend
pip install -r requirements-dev.txt
pytest tests -q
```
