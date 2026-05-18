# Integracao do frontend `sensores_pi` na raiz

## Passo 1 - Reenquadramento do escopo

Status: concluido em 2026-05-18.

### Premissa corrigida

A pasta `sensores_pi/` sera considerada apenas como origem de frontend. Portanto, nesta integracao:

- Nao vou migrar `sensores_pi/app/api` para o `backend/`.
- Nao vou usar `sensores_pi/sevicos/servicos.py` como API da raiz.
- Nao vou alterar `src/main.py` neste fluxo, porque a origem agora nao inclui firmware.
- Nao vou transformar a raiz em Next.js.

O alvo correto e adaptar o conteudo visual, componentes, tipos e configuracoes uteis do frontend de `sensores_pi/` para a organizacao atual da raiz.

### Estrutura que sera preservada

- `backend/`: permanece como API FastAPI da raiz.
- `frontend/`: permanece como aplicacao React/Vite principal.
- `src/`: permanece como firmware MicroPython da raiz.
- `docker-compose.yml`: permanece como containerizacao da raiz.
- `sensores_pi/`: permanece como pasta de referencia/origem, sem ser promovida a app principal.

### Diferencas importantes

- `frontend/` usa:
  - Vite;
  - React 19;
  - CSS unico em `frontend/src/styles.css`;
  - consumo da API da raiz por `VITE_API_URL`;
  - contrato de dados `Leitura` com `sensores`.
- `sensores_pi/` usa:
  - Next.js;
  - estrutura `app/`, `components/`, `hooks/`, `lib/`, `types/`;
  - aliases `@/*`;
  - shadcn/ui, Radix, Tailwind e hooks que dependem de rotas internas `/api/...`;
  - contrato de dados `SensorReading` com `sensorType`, `value`, `metadata`.

### Consequencia tecnica

A integracao nao deve copiar a aplicacao Next.js diretamente para a raiz. O caminho mais seguro e portar a experiencia de interface para o `frontend/` Vite existente, mantendo compatibilidade com a API FastAPI atual.

## Passo 2 - Integracao do frontend na raiz

Status: concluido em 2026-05-18.

### Objetivo

Trazer conteudo e configuracoes de frontend de `sensores_pi/` para `frontend/`, preservando o padrao da raiz.

### Acoes executadas

1. Atualizar configuracoes do `frontend/` quando forem compativeis:
   - manter Vite;
   - adicionar alias `@` para `src`;
   - manter scripts `dev`, `build` e `preview`;
   - nao adicionar dependencias de Next.js, shadcn, Radix ou Tailwind.
2. Portar a estrutura visual:
   - adaptar as ideias das telas `page.tsx`, `monitoramento`, `history` e `predicoes` em uma aplicacao Vite com abas internas;
   - manter uma experiencia operacional com visao geral, monitoramento, historico e predicoes;
   - evitar migrar rotas Next.js, server components ou hooks dependentes de `/api/...` do Next.
3. Adaptar tipos e consumo de dados:
   - manter o tipo `Leitura` da raiz;
   - criar funcoes de derivacao para exibir umidade, chuva, vibracao, inclinacao e risco;
   - manter `frontend/src/api.ts` apontando para a API FastAPI.
4. Atualizar estilos:
   - trazer a identidade visual util de `sensores_pi` para `frontend/src/styles.css`;
   - preservar raio de borda, densidade e organizacao de painel operacional.
5. Validar:
   - `npm run build` executado com sucesso em `frontend/`;
   - sem erros TypeScript;
   - backend, firmware e Docker nao foram alterados neste passo.

### Arquivos alterados

- `frontend/src/App.tsx`: novo painel Vite com abas de visao geral, monitoramento, historico e predicoes.
- `frontend/src/styles.css`: estilos atualizados para a experiencia integrada.
- `frontend/src/api.ts`: `fetchLeituras` agora aceita limite configuravel.
- `frontend/vite.config.ts`: alias `@` apontando para `/src`.
- `frontend/tsconfig.json`: `baseUrl` e `paths` compativeis com o alias.

### Resultado esperado

`frontend/` contem a experiencia adaptada do frontend de `sensores_pi`, mas ainda funciona como app Vite da raiz e consome a API existente em `/leituras`.

### Validacao

Comando executado:

```bash
npm run build
```

Resultado:

- TypeScript compilou sem erros.
- Vite gerou build de producao com sucesso.
- Aviso restante: bundle acima de 500 kB por causa das dependencias de graficos, sem bloquear a execucao.

## Passo 3 - Proxima etapa sugerida

Status: aguardando comando.

### Objetivo

Conectar, se desejado, as abas do frontend a endpoints especificos da API integrada descrita em `Integracao_API_sensores_pi.md`, como `/analytics`, `/alerts`, `/limits` e `/predictions`.
