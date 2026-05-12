import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  CloudRain,
  Database,
  Download,
  Droplets,
  Gauge,
  RefreshCw,
  Shield,
  SlidersHorizontal,
  Wifi,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { csvExportUrl, fetchLeituras } from "./api";
import { sampleReadings } from "./sampleData";
import type { Leitura, NivelAlerta } from "./types";

const alertLabels: Record<NivelAlerta, string> = {
  verde: "Seguro",
  amarelo: "Atencao",
  laranja: "Risco elevado",
  vermelho: "Critico",
};

const alertRank: Record<NivelAlerta, number> = {
  verde: 1,
  amarelo: 2,
  laranja: 3,
  vermelho: 4,
};

function formatTime(value?: string) {
  if (!value) return "--:--";
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function formatDate(value?: string) {
  if (!value) return "--";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function clamp(value: number, max: number) {
  return Math.max(0, Math.min(max, value));
}

function vibrationIndex(reading?: Leitura) {
  if (!reading) return 0;
  const { sensores } = reading;
  const accel = Math.sqrt(
    sensores.aceleracao_x ** 2 + sensores.aceleracao_y ** 2 + (sensores.aceleracao_z - 1) ** 2,
  );
  const gyro = Math.max(
    Math.abs(sensores.giroscopio_x),
    Math.abs(sensores.giroscopio_y),
    Math.abs(sensores.giroscopio_z),
  );
  return Number((accel * 42 + gyro * 0.35).toFixed(1));
}

function slopeDegrees(reading?: Leitura) {
  if (!reading) return 0;
  const { aceleracao_x, aceleracao_y, aceleracao_z, inclinacao } = reading.sensores;
  const angle = Math.atan2(Math.sqrt(aceleracao_x ** 2 + aceleracao_y ** 2), Math.abs(aceleracao_z)) * (180 / Math.PI);
  return Number((angle + inclinacao * 14).toFixed(1));
}

function toPercent(value: number) {
  return Number(((clamp(value, 4095) / 4095) * 100).toFixed(1));
}

function getHighestAlert(items: Leitura[]): NivelAlerta {
  return items.reduce<NivelAlerta>((highest, item) => {
    return alertRank[item.nivel_alerta] > alertRank[highest] ? item.nivel_alerta : highest;
  }, "verde");
}

function SensorCard({
  icon,
  title,
  value,
  unit,
  alert,
  progress,
  trend,
  footerLeft,
  footerRight,
  color,
  data,
}: {
  icon: ReactNode;
  title: string;
  value: string;
  unit: string;
  alert: NivelAlerta;
  progress: number;
  trend: string;
  footerLeft: string;
  footerRight: string;
  color: string;
  data: { time: string; value: number }[];
}) {
  const gradientId = `fill-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

  return (
    <section className="sensor-card">
      <div className="card-topline">
        <div className="sensor-title">
          <span className="icon-box" style={{ color }}>
            {icon}
          </span>
          <span>{title}</span>
        </div>
        <span className={`alert-pill ${alert}`}>{alertLabels[alert]}</span>
      </div>

      <div className="metric-row">
        <strong>{value}</strong>
        <span>{unit}</span>
        <small>{trend}</small>
      </div>

      <div className="risk-scale">
        <div className="scale-labels">
          <span>0</span>
          <span>Atencao</span>
          <span>Critico</span>
        </div>
        <div className="scale-track">
          <span style={{ width: `${progress}%`, background: color }} />
        </div>
      </div>

      <div className="mini-chart">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.38} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="card-footer">
        <span>{footerLeft}</span>
        <span>{footerRight}</span>
      </div>
    </section>
  );
}

export function App() {
  const [readings, setReadings] = useState<Leitura[]>(sampleReadings);
  const [isUsingSample, setIsUsingSample] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date().toISOString());

  async function loadReadings() {
    setIsLoading(true);
    try {
      const data = await fetchLeituras();
      if (data.length > 0) {
        setReadings(data);
        setIsUsingSample(false);
      }
    } catch {
      setReadings(sampleReadings);
      setIsUsingSample(true);
    } finally {
      setLastUpdated(new Date().toISOString());
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadReadings();
    const interval = window.setInterval(loadReadings, 8000);
    return () => window.clearInterval(interval);
  }, []);

  const ordered = useMemo(() => {
    return [...readings].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }, [readings]);

  const latest = ordered.at(-1);
  const recent = ordered.slice(-18);
  const highestAlert = getHighestAlert(recent);
  const moisture = latest ? toPercent(latest.sensores.umidade_solo) : 0;
  const rain = latest ? toPercent(latest.sensores.chuva) : 0;
  const vibration = vibrationIndex(latest);
  const slope = slopeDegrees(latest);
  const events = readings.filter((item) => item.evento_deslizamento || item.nivel_alerta !== "verde");
  const simulations = new Set(readings.map((item) => item.id_simulacao)).size;

  const chartRows = recent.map((item) => ({
    time: formatTime(item.timestamp).slice(0, 5),
    umidade: toPercent(item.sensores.umidade_solo),
    chuva: toPercent(item.sensores.chuva),
    vibracao: vibrationIndex(item),
    inclinacao: slopeDegrees(item),
  }));

  return (
    <main className="dashboard">
      <header className="app-header">
        <div className="brand-block">
          <span className="brand-icon">
            <Shield size={25} />
          </span>
          <div>
            <div className="brand-title">
              <h1>GeoSentinel Pro</h1>
              <span>v4.2.1</span>
            </div>
            <p>Sistema Inteligente de Monitoramento de Risco de Deslizamento</p>
          </div>
        </div>

        <div className="header-status">
          <div className={`status-chip ${highestAlert}`}>
            <span />
            Status: {alertLabels[highestAlert]}
          </div>
          <div className="header-meta">
            <Gauge size={16} />
            <div>
              <strong>{formatTime(latest?.timestamp)}</strong>
              <small>{formatDate(latest?.timestamp)}</small>
            </div>
          </div>
          <div className="header-meta online">
            <Wifi size={16} />
            <div>
              <strong>{isUsingSample ? "Amostra" : "Online"}</strong>
              <small>{readings.length} leituras</small>
            </div>
          </div>
          <button className="refresh-button" onClick={loadReadings} disabled={isLoading} title="Atualizar leituras">
            <RefreshCw size={16} className={isLoading ? "spin" : ""} />
            <span>{formatTime(lastUpdated).slice(0, 5)}</span>
          </button>
        </div>
      </header>

      <section className="summary-strip">
        <div>
          <Database size={18} />
          <span>{simulations}</span>
          <small>simulacoes</small>
        </div>
        <div>
          <Activity size={18} />
          <span>{readings.length}</span>
          <small>leituras</small>
        </div>
        <div>
          <AlertTriangle size={18} />
          <span>{events.length}</span>
          <small>alertas/eventos</small>
        </div>
        <a href={csvExportUrl()} className="export-link" title="Exportar CSV">
          <Download size={18} />
          <span>CSV</span>
        </a>
      </section>

      <section className="main-grid">
        <SensorCard
          icon={<Activity size={22} />}
          title="Vibracao do Solo"
          value={vibration.toFixed(1)}
          unit="indice"
          alert={latest?.nivel_alerta ?? "verde"}
          progress={clamp((vibration / 55) * 100, 100)}
          trend={vibration > 25 ? "instavel" : "estavel"}
          footerLeft={`Media: ${(chartRows.reduce((sum, row) => sum + row.vibracao, 0) / Math.max(chartRows.length, 1)).toFixed(1)}`}
          footerRight="Critico: > 55"
          color="#2f80ff"
          data={chartRows.map((row) => ({ time: row.time, value: row.vibracao }))}
        />
        <SensorCard
          icon={<Droplets size={22} />}
          title="Umidade do Solo"
          value={moisture.toFixed(1)}
          unit="%"
          alert={moisture > 68 ? "laranja" : moisture > 44 ? "amarelo" : "verde"}
          progress={moisture}
          trend={moisture > 68 ? "alta" : "normal"}
          footerLeft={`ADC: ${latest?.sensores.umidade_solo ?? 0}`}
          footerRight="Critico: > 68%"
          color="#19d3c5"
          data={chartRows.map((row) => ({ time: row.time, value: row.umidade }))}
        />
        <SensorCard
          icon={<SlidersHorizontal size={22} />}
          title="Inclinacao do Solo"
          value={slope.toFixed(1)}
          unit="graus"
          alert={latest?.sensores.inclinacao ? "vermelho" : slope > 24 ? "laranja" : "verde"}
          progress={clamp((slope / 35) * 100, 100)}
          trend={latest?.sensores.inclinacao ? "ativada" : "normal"}
          footerLeft={`SW-520D: ${latest?.sensores.inclinacao ? "ativo" : "inativo"}`}
          footerRight="Limite: 35 graus"
          color="#a15cff"
          data={chartRows.map((row) => ({ time: row.time, value: row.inclinacao }))}
        />
        <SensorCard
          icon={<CloudRain size={22} />}
          title="Sensor de Chuva"
          value={rain.toFixed(1)}
          unit="%"
          alert={rain > 62 ? "laranja" : rain > 28 ? "amarelo" : "verde"}
          progress={rain}
          trend={rain > 62 ? "intensa" : rain > 28 ? "presente" : "baixa"}
          footerLeft={`ADC: ${latest?.sensores.chuva ?? 0}`}
          footerRight="Critico: > 62%"
          color="#20b8ff"
          data={chartRows.map((row) => ({ time: row.time, value: row.chuva }))}
        />
      </section>

      <section className="analysis-grid">
        <article className="panel wide">
          <div className="panel-heading">
            <div>
              <h2>Evolucao dos Sensores</h2>
              <p>Ultimas leituras recebidas da API</p>
            </div>
            <span className={`alert-pill ${highestAlert}`}>{alertLabels[highestAlert]}</span>
          </div>
          <div className="line-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartRows}>
                <CartesianGrid stroke="#18304f" strokeDasharray="3 8" />
                <XAxis dataKey="time" stroke="#7184a5" tickLine={false} axisLine={false} />
                <YAxis stroke="#7184a5" tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "#0d1c35", border: "1px solid #244b77", borderRadius: 8 }} />
                <Line type="monotone" dataKey="umidade" stroke="#19d3c5" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="chuva" stroke="#20b8ff" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="vibracao" stroke="#2f80ff" strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="inclinacao" stroke="#a15cff" strokeWidth={3} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <h2>Eventos Recentes</h2>
              <p>Alertas e possiveis deslizamentos</p>
            </div>
          </div>
          <div className="event-list">
            {events.slice(0, 6).map((item) => (
              <div className="event-row" key={item.id}>
                <span className={`event-dot ${item.nivel_alerta}`} />
                <div>
                  <strong>{alertLabels[item.nivel_alerta]}</strong>
                  <small>
                    {item.id_simulacao} - {formatTime(item.timestamp)}
                  </small>
                </div>
                <span>{item.evento_deslizamento ? "confirmado" : "monitorar"}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
