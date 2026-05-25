export type NivelAlerta = "verde" | "amarelo" | "laranja" | "vermelho";

export type Sensores = {
  aceleracao_x: number;
  aceleracao_y: number;
  aceleracao_z: number;
  giroscopio_x: number;
  giroscopio_y: number;
  giroscopio_z: number;
  umidade_solo: number;
  inclinacao: number;
  hw103a_ao?: number | null;
  hw103a_do?: number | null;
  hw103a_do_wet?: boolean | null;
  sw520_raw?: number | null;
  sw520_hits?: number | null;
  sw520_edges?: number | null;
  sw520_streak?: number | null;
  mpu_motion_g?: number | null;
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
