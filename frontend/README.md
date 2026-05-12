# Frontend

Dashboard React/Vite para visualizar as leituras recebidas pela API FastAPI.

## Rodar localmente

```powershell
cd frontend
npm install
npm run dev
```

Abra:

```text
http://localhost:5173
```

Por padrao, o frontend consome:

```text
http://localhost:8000
```

Para alterar, crie um `.env` com:

```text
VITE_API_URL=http://localhost:8000
```

Se a API estiver desligada ou sem leituras, a interface mostra dados de exemplo
para facilitar a apresentacao e a validacao visual.
