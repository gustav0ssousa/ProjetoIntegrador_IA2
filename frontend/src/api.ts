import type { Leitura, LeituraListResponse } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchLeituras(): Promise<Leitura[]> {
  const response = await fetch(`${API_URL}/leituras?limit=80`);
  if (!response.ok) {
    throw new Error("Nao foi possivel carregar as leituras da API.");
  }
  const payload = (await response.json()) as LeituraListResponse;
  return payload.items;
}

export function csvExportUrl(): string {
  return `${API_URL}/leituras/export/csv`;
}
