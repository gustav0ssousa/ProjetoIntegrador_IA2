export type NivelAlerta = "verde" | "amarelo" | "laranja" | "vermelho";

export type Sensores = {
  aceleracao_x: number;
  aceleracao_y: number;
  aceleracao_z: number;
  giroscopio_x: number;
  giroscopio_y: number;
  giroscopio_z: number;
  umidade_solo: number;
  chuva: number;
  inclinacao: number;
};

export type Leitura = {
  id: string;
  timestamp: string;
  id_simulacao: string;
  sensores: Sensores;
  nivel_alerta: NivelAlerta;
  evento_deslizamento: boolean;
  observacoes_experimento?: string | null;
};

export type LeituraListResponse = {
  total: number;
  limit: number;
  offset: number;
  items: Leitura[];
};
