# Testes em maquete de morro com caixa de acrilico

Este guia descreve como testar o sistema GeoRisk em uma maquete física com caixa de acrilico, terra seca e terra molhada, gerando dados consistentes para monitoramento e futuras predicoes.

## Objetivo

Simular diferentes condicoes de estabilidade de um pequeno morro dentro de uma caixa de acrilico e registrar leituras dos sensores:

- `HW-103A`: umidade do solo, via leitura analogica e digital.
- `SW-520`: inclinacao, vibracao ou movimento brusco.
- `MPU6050`: aceleracao, inclinacao dinamica e giroscopio.
- `Buzzer`: pulso curto em condicao normal e alerta continuo quando uma condicao de risco for detectada.

Nesta versao do projeto nao ha sensor de chuva. A umidade deve ser simulada molhando a terra diretamente e o payload nao deve conter campo de chuva.

## Materiais

- Caixa de acrilico transparente.
- Terra seca.
- Terra umida ou agua para molhar gradualmente a terra.
- ESP32 com MicroPython.
- Sensor `HW-103A`.
- Sensor `SW-520`.
- Modulo `MPU6050`.
- Buzzer.
- Jumpers e protoboard.
- Cabo USB para alimentacao e monitor serial.
- Computador rodando Docker, backend e frontend.
- Opcional: seringa, borrifador ou conta-gotas para umedecer a terra com mais controle.

## Montagem da maquete

1. Coloque uma camada de terra no fundo da caixa de acrilico.
2. Modele um pequeno morro inclinado em uma das laterais.
3. Separe visualmente tres regioes:
   - topo do morro;
   - meio da encosta;
   - base da encosta.
4. Posicione o `HW-103A` na regiao que recebera umidade durante o teste.
5. Fixe o `MPU6050` em uma parte da encosta ou em uma pequena placa presa a terra, para captar inclinacao e movimento.
6. Posicione o `SW-520` no corpo da maquete ou na estrutura que possa se mover quando a encosta ceder.
7. Deixe o buzzer fora da terra e longe de umidade.

Evite enterrar completamente os modulos eletronicos. Apenas a haste/sonda do sensor de umidade deve entrar em contato com a terra.

## Pinagem usada

| Componente | Pino ESP32 |
|---|---:|
| HW-103A AO | GPIO 34 |
| HW-103A DO | GPIO 27 |
| Buzzer | GPIO 25 |
| SW-520 | GPIO 26 |
| MPU6050 SDA | GPIO 21 |
| MPU6050 SCL | GPIO 22 |

## Preparacao do sistema

Suba os servicos:

```bash
docker compose up --build -d
```

Verifique:

```text
Backend:  http://localhost:8000/health
Docs API: http://localhost:8000/docs
Painel:   http://localhost:5173
```

No arquivo `src/config.py`, configure a URL da API usando o IP da maquina na rede local:

```python
CONFIG = {
    "api_url": "http://IP_DA_MAQUINA:8000/leituras",
}
```

Nao use `localhost` na ESP32, porque `localhost` dentro da placa aponta para a propria placa.

Envie o firmware:

```bash
mpremote connect PORTA_DA_ESP32 cp boot.py :boot.py
mpremote connect PORTA_DA_ESP32 cp src/config.py :config.py
mpremote connect PORTA_DA_ESP32 cp src/main.py :main.py
mpremote connect PORTA_DA_ESP32 reset
mpremote connect PORTA_DA_ESP32 repl
```

## Calibracao do HW-103A

O firmware usa uma escala normalizada de `0` a `4095`, onde valores maiores indicam mais umidade.

1. Com a sonda no ar ou em terra bem seca, anote o valor exibido como `HW-103A AO bruto`.
2. Coloque a sonda em terra bem molhada, sem submergir o modulo eletronico, e anote o novo valor.
3. Atualize `src/config.py`:

```python
"moisture_dry_adc": 4095,
"moisture_wet_adc": 1500,
"moisture_wet_threshold": 3400,
"buzzer_pulse_moisture_min_threshold": 2400,
"buzzer_continuous_moisture_threshold": 3400,
```

Use seus valores reais no lugar de `4095` e `1500`. O `moisture_wet_threshold` define a partir de qual umidade normalizada o sistema considera solo molhado. O buzzer fica sem som abaixo de `buzzer_pulse_moisture_min_threshold`, pulsa a partir desse valor e passa para sinal continuo em `buzzer_continuous_moisture_threshold`.

## Sequencia recomendada de testes

### Teste 1 - Solo seco e estavel

Objetivo: gerar a linha de base.

1. Deixe a maquete seca.
2. Mantenha a caixa parada.
3. Colete leituras por 2 a 5 minutos.
4. Verifique se:
   - umidade normalizada fica baixa;
   - `SW-520` fica estavel;
   - `MPU6050` nao apresenta mudancas bruscas;
   - buzzer permanece desligado.

Resultado esperado: risco baixo ou moderado, sem evento de deslizamento.

### Teste 2 - Solo parcialmente umido

Objetivo: observar a evolucao gradual da umidade.

1. Umedeca a parte superior ou central da encosta aos poucos.
2. Aguarde a agua se distribuir pela terra.
3. Colete leituras por 5 a 10 minutos.
4. Observe a variacao de `umidade_solo` no painel.

Resultado esperado: aumento progressivo da umidade, sem necessariamente acionar evento de deslizamento.

### Teste 3 - Solo saturado

Objetivo: simular condicao critica de instabilidade.

1. Molhe a terra ate a encosta perder firmeza.
2. Evite contato de agua com a ESP32 e com os modulos eletronicos.
3. Observe se a terra se desloca ou se a estrutura do sensor muda de posicao.
4. Colete leituras antes, durante e depois da saturacao.

Resultado esperado: umidade alta e possivel elevacao do nivel de alerta.

### Teste 4 - Movimento controlado da encosta

Objetivo: validar `SW-520`, `MPU6050` e buzzer.

1. Com cuidado, incline levemente a caixa ou pressione a encosta.
2. Simule pequenos deslocamentos da terra.
3. Observe no monitor serial:
   - `SW-520: VARIACAO RAPIDA` quando houver mudanças rápidas em uma janela;
   - `SW-520: VIBRACAO CONTINUA` quando a variação rápida se repetir;
   - aumento em `bordas`, `irq`, `polling` e `sequencia`;
   - mudancas de aceleracao e giroscopio;
   - buzzer ligado.

Resultado esperado: `inclinacao = 1` ou `evento_deslizamento = true` quando houver vibração rápida e contínua.

Se `bordas`, `irq` e `polling` permanecerem em `0` durante a vibração, confira se o pino `DO` do SW-520 esta no GPIO 26, se o sensor esta alimentado e se `vibration_active_high` combina com o modulo usado.

### Teste 5 - Deslizamento simulado

Objetivo: gerar exemplos de evento para treinamento e analise.

1. Prepare a encosta com terra umida.
2. Aumente gradualmente a umidade ou provoque pequeno deslocamento mecanico.
3. Registre o instante aproximado do deslizamento.
4. Continue coletando por pelo menos 1 minuto apos o evento.

Resultado esperado: leituras com umidade elevada, movimento detectado e evento marcado.

## Registro dos experimentos

Para cada rodada, anote manualmente:

| Campo | Exemplo |
|---|---|
| Identificador | `teste_solo_umido_01` |
| Condicao inicial | solo seco, morro firme |
| Acao aplicada | umidade adicionada no topo |
| Horario de inicio | `14:05` |
| Horario do evento | `14:08` |
| Resultado observado | pequena ruptura na base |
| Observacao | sensor ficou inclinado apos o deslocamento |

No backend, use `id_simulacao` para separar os testes. Exemplo em `src/config.py`:

```python
"device_id": "maquete-acrilico-teste-01",
```

Troque o valor a cada campanha de teste se quiser separar os dados por experimento.

## Validacao dos dados

Consulte as ultimas leituras:

```bash
curl "http://localhost:8000/leituras?limit=5"
```

Exporte CSV:

```text
http://localhost:8000/leituras/export/csv
```

Campos esperados no CSV:

- `timestamp`
- `id_simulacao`
- `aceleracao_x`
- `aceleracao_y`
- `aceleracao_z`
- `giroscopio_x`
- `giroscopio_y`
- `giroscopio_z`
- `umidade_solo`
- `inclinacao`
- `nivel_alerta`
- `evento_deslizamento`
- `observacoes_experimento`

## Boas praticas para gerar dados de predicao

- Faça varias rodadas de cada condicao, nao apenas um teste unico.
- Mantenha intervalos constantes de envio, por exemplo `3000 ms` ou `10000 ms`.
- Registre testes estaveis e testes com evento. Dados apenas de evento nao ajudam a diferenciar normalidade.
- Evite mexer na posicao dos sensores no meio de uma rodada, exceto quando o objetivo for simular deslocamento.
- Anote alteracoes externas, como quantidade de agua adicionada ou movimento manual da caixa.
- Nao misture campanhas muito diferentes com o mesmo `device_id`, se o objetivo for comparar cenarios.

## Cuidados de seguranca

- Nao deixe agua entrar em contato com a ESP32, protoboard ou conexoes energizadas.
- Mantenha o buzzer e a ESP32 fora da caixa ou em uma area elevada e seca.
- Desligue a alimentacao antes de reposicionar sensores.
- Se a caixa acumular agua no fundo, retire o excesso antes de continuar.
- Use pouca agua por vez para evitar encharcar os modulos.

## Checklist rapido

- [ ] Containers rodando e API saudavel.
- [ ] ESP32 conectada ao Wi-Fi.
- [ ] `api_url` aponta para o IP correto da maquina.
- [ ] HW-103A calibrado com seco e molhado.
- [ ] MPU6050 aparece no scan I2C.
- [ ] SW-520 mostra aumento de `bordas` e `sequencia` quando a maquete vibra rapidamente.
- [ ] Buzzer da pulso curto em condicao normal e fica continuo em alerta.
- [ ] Painel mostra novas leituras.
- [ ] CSV exporta dados sem campo de chuva.
