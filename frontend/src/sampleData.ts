import type { Leitura } from "./types";

const now = new Date("2026-05-11T19:46:00-03:00").getTime();

export const sampleReadings: Leitura[] = Array.from({ length: 28 }, (_, index) => {
  const step = 27 - index;
  const umidade = 1620 + Math.round(Math.sin(step / 3) * 180 + step * 34);
  const chuva = step > 16 ? 1180 + step * 18 : 420 + step * 12;
  const vibracao = step > 21 ? 0.56 : 0.12 + Math.sin(step / 2) * 0.04;
  const inclinacao = step > 24 ? 1 : 0;
  const alerta = inclinacao ? "vermelho" : step > 21 ? "laranja" : step > 14 ? "amarelo" : "verde";

  return {
    id: `sample-${index}`,
    timestamp: new Date(now - index * 60_000).toISOString(),
    id_simulacao: step > 19 ? "SIM_003" : step > 9 ? "SIM_002" : "SIM_001",
    sensores: {
      aceleracao_x: Number((vibracao + Math.sin(step) * 0.02).toFixed(2)),
      aceleracao_y: Number((0.04 + Math.cos(step / 2) * 0.03).toFixed(2)),
      aceleracao_z: Number((1 + Math.sin(step / 4) * 0.08).toFixed(2)),
      giroscopio_x: Number((step * 1.4).toFixed(1)),
      giroscopio_y: Number((step * 0.7).toFixed(1)),
      giroscopio_z: Number((step * 1.1).toFixed(1)),
      umidade_solo: Math.min(4095, umidade),
      chuva: Math.min(4095, chuva),
      inclinacao,
    },
    nivel_alerta: alerta,
    evento_deslizamento: Boolean(inclinacao),
    observacoes_experimento: inclinacao ? "Mudanca brusca detectada no sensor SW-520D." : null,
  } satisfies Leitura;
});
