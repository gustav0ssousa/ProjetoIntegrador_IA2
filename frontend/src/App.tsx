import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  Download,
  Droplets,
  Gauge,
  LayoutDashboard,
  Minus,
  Radio,
  RefreshCw,
  Shield,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Waves,
  Wifi,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
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

type View = "overview" | "monitoring" | "history" | "predictions";
type Trend = "increasing" | "decreasing" | "stable";

type ChartRow = {
  time: string;
  date: string;
  umidade: number;
  vibracao: number;
  inclinacao: number;
  risco: number;
};

type PredictionMetric = {
  id: string;
  label: string;
  unit: string;
  current: number;
  prediction: number;
  confidence: number;
  trend: Trend;
  riskLabel: "baixo" | "medio" | "alto";
  description: string;
  color: string;
  data: { time: string; value: number }[];
};

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

const navItems: { id: View; label: string; icon: ReactNode }[] = [
  { id: "overview", label: "Dashboard", icon: <LayoutDashboard size={16} /> },
  { id: "predictions", label: "Predicoes", icon: <TrendingUp size={16} /> },
  { id: "monitoring", label: "Monitoramento", icon: <Radio size={16} /> },
  { id: "history", label: "Historico", icon: <BarChart3 size={16} /> },
];

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

function clamp(value: number, max = 100) {
  return Math.max(0, Math.min(max, value));
}

function toPercent(value: number) {
  return Number(((clamp(value, 4095) / 4095) * 100).toFixed(1));
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

function riskScore(reading?: Leitura) {
  if (!reading) return 0;
  const base = alertRank[reading.nivel_alerta] * 18;
  const moisture = toPercent(reading.sensores.umidade_solo) > 68 ? 18 : 0;
  const slope = reading.sensores.inclinacao ? 18 : 0;
  return clamp(base + moisture + slope);
}

function getHighestAlert(items: Leitura[]): NivelAlerta {
  return items.reduce<NivelAlerta>((highest, item) => {
    return alertRank[item.nivel_alerta] > alertRank[highest] ? item.nivel_alerta : highest;
  }, "verde");
}

function getTrend(values: number[]): Trend {
  if (values.length < 2) return "stable";
  const first = values[0];
  const last = values[values.length - 1];
  const delta = last - first;
  if (Math.abs(delta) < Math.max(1, Math.abs(first) * 0.04)) return "stable";
  return delta > 0 ? "increasing" : "decreasing";
}

function predictNext(values: number[]) {
  if (values.length === 0) {
    return { prediction: 0, confidence: 0, trend: "stable" as Trend };
  }

  if (values.length < 3) {
    return {
      prediction: Number(values[values.length - 1].toFixed(1)),
      confidence: 0.35,
      trend: getTrend(values),
    };
  }

  const xMean = (values.length - 1) / 2;
  const yMean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const numerator = values.reduce((sum, value, index) => sum + (index - xMean) * (value - yMean), 0);
  const denominator = values.reduce((sum, _value, index) => sum + (index - xMean) ** 2, 0);
  const slope = denominator === 0 ? 0 : numerator / denominator;
  const intercept = yMean - slope * xMean;
  const prediction = intercept + slope * values.length;
  const range = Math.max(...values) - Math.min(...values) || 1;
  const meanError =
    values.reduce((sum, value, index) => sum + Math.abs(value - (intercept + slope * index)), 0) / values.length;
  const confidence = clamp((1 - meanError / range) * 100) / 100;

  return {
    prediction: Number(prediction.toFixed(1)),
    confidence: Number(Math.max(0.2, Math.min(0.96, confidence)).toFixed(2)),
    trend: getTrend(values),
  };
}

function makePrediction(
  id: string,
  label: string,
  unit: string,
  values: number[],
  data: { time: string; value: number }[],
  color: string,
  highThreshold: number,
): PredictionMetric {
  const recentValues = values.slice(-30);
  const current = Number((recentValues.at(-1) ?? 0).toFixed(1));
  const prediction = predictNext(recentValues);
  const predicted = Math.max(0, prediction.prediction);
  const riskLabel = predicted >= highThreshold ? "alto" : predicted >= highThreshold * 0.72 ? "medio" : "baixo";

  return {
    id,
    label,
    unit,
    current,
    prediction: Number(predicted.toFixed(1)),
    confidence: prediction.confidence,
    trend: prediction.trend,
    riskLabel,
    color,
    data,
    description:
      riskLabel === "alto"
        ? "Tendencia exige verificacao rapida."
        : riskLabel === "medio"
          ? "Tendencia pede acompanhamento continuo."
          : "Tendencia dentro da faixa esperada.",
  };
}

function SectionTitle({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="section-title">
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}

function StatusCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <article className="status-card" style={{ color: tone }}>
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

function StatTile({
  icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <article className="stat-tile">
      <span className="tile-icon" style={{ color: tone }}>
        {icon}
      </span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
        <p>{detail}</p>
      </div>
    </article>
  );
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
          <span style={{ width: `${clamp(progress)}%`, background: color }} />
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

function PredictionCard({ metric }: { metric: PredictionMetric }) {
  const TrendIcon = metric.trend === "increasing" ? TrendingUp : metric.trend === "decreasing" ? TrendingDown : Minus;

  return (
    <article className={`prediction-card ${metric.riskLabel}`}>
      <div className="prediction-heading">
        <div>
          <span>{metric.label}</span>
          <strong>{metric.riskLabel.toUpperCase()}</strong>
        </div>
        <TrendIcon size={22} />
      </div>
      <div className="prediction-values">
        <div>
          <small>Atual</small>
          <strong>
            {metric.current}
            <span>{metric.unit}</span>
          </strong>
        </div>
        <div>
          <small>Proxima leitura</small>
          <strong>
            {metric.prediction}
            <span>{metric.unit}</span>
          </strong>
        </div>
      </div>
      <p>{metric.description}</p>
      <div className="confidence-track">
        <span style={{ width: `${metric.confidence * 100}%`, background: metric.color }} />
      </div>
      <small>Confianca estimada: {(metric.confidence * 100).toFixed(0)}%</small>
    </article>
  );
}

export function App() {
  const [activeView, setActiveView] = useState<View>("overview");
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
  const recent = ordered.slice(-24);
  const highestAlert = getHighestAlert(recent);
  const moisture = latest ? toPercent(latest.sensores.umidade_solo) : 0;
  const vibration = vibrationIndex(latest);
  const slope = slopeDegrees(latest);
  const events = readings.filter((item) => item.evento_deslizamento || item.nivel_alerta !== "verde");
  const simulations = new Set(readings.map((item) => item.id_simulacao)).size;
  const activeAlerts = events.filter((item) => item.nivel_alerta === "laranja" || item.nivel_alerta === "vermelho").length;

  const riskCounts = readings.reduce<Record<NivelAlerta, number>>(
    (counts, item) => {
      counts[item.nivel_alerta] += 1;
      return counts;
    },
    { verde: 0, amarelo: 0, laranja: 0, vermelho: 0 },
  );

  const chartRows: ChartRow[] = recent.map((item) => ({
    time: formatTime(item.timestamp).slice(0, 5),
    date: formatDate(item.timestamp),
    umidade: toPercent(item.sensores.umidade_solo),
    vibracao: vibrationIndex(item),
    inclinacao: slopeDegrees(item),
    risco: riskScore(item),
  }));

  const predictions = [
    makePrediction(
      "umidade",
      "Umidade do solo",
      "%",
      chartRows.map((row) => row.umidade),
      chartRows.map((row) => ({ time: row.time, value: row.umidade })),
      "#4CAF50",
      70,
    ),
    makePrediction(
      "vibracao",
      "Vibracao",
      " idx",
      chartRows.map((row) => row.vibracao),
      chartRows.map((row) => ({ time: row.time, value: row.vibracao })),
      "#81C784",
      55,
    ),
    makePrediction(
      "inclinacao",
      "Inclinacao",
      " graus",
      chartRows.map((row) => row.inclinacao),
      chartRows.map((row) => ({ time: row.time, value: row.inclinacao })),
      "#A5D6A7",
      35,
    ),
  ];

  return (
    <main className="dashboard">
      <header className="app-header">
        <div className="brand-block">
          <span className="brand-icon">
            <ShieldCheck size={23} />
          </span>
          <div>
            <p className="brand-eyebrow">GeoRisk</p>
            <div className="brand-title">
              <h1>Painel de monitoramento</h1>
            </div>
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

      <nav className="view-tabs" aria-label="Navegacao principal">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={activeView === item.id ? "active" : ""}
            onClick={() => setActiveView(item.id)}
            type="button"
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
        <a href={csvExportUrl()} title="Exportar CSV">
          <Download size={16} />
          <span>CSV</span>
        </a>
      </nav>

      {activeView === "overview" && (
        <>
          <section className="dashboard-hero">
            <div>
              <p>GeoRisk</p>
              <h2>Visao geral do sistema</h2>
              <span>Monitoramento em tempo real dos sensores e indicadores de risco para apoiar decisoes rapidas.</span>
            </div>
            <div className="hero-status-grid">
              <StatusCard label="Status da API" value={isUsingSample ? "Amostra" : "Online"} tone={isUsingSample ? "#FFC107" : "#4CAF50"} />
              <StatusCard label="Alertas ativos" value={String(activeAlerts)} />
            </div>
          </section>

          <section className="summary-grid">
            <StatTile icon={<Activity size={22} />} label="Ultima leitura" value={latest ? `${formatTime(latest.timestamp)}` : "Sem dados"} detail={latest ? `${latest.id_simulacao} em ${formatDate(latest.timestamp)}` : "Nenhuma leitura recebida"} tone="#4CAF50" />
            <StatTile icon={<Shield size={22} />} label="Nivel de risco" value={alertLabels[highestAlert]} detail="maior nivel das leituras recentes" tone={highestAlert === "verde" ? "#4CAF50" : highestAlert === "amarelo" ? "#FFC107" : "#F44336"} />
            <StatTile icon={<Droplets size={22} />} label="Leitura do higrometro" value={`${moisture.toFixed(1)}%`} detail={`ADC ${latest?.sensores.umidade_solo ?? 0}`} tone="#66BB6A" />
            <StatTile icon={<Sparkles size={22} />} label="Reconhecimento" value={`${events.length}`} detail="alertas totais analisados" tone="#A5D6A7" />
          </section>

          <section className="compact-sensor-grid">
            <article>
              <span><Droplets size={18} /></span>
              <small>Higrometro</small>
              <strong>{moisture.toFixed(1)}%</strong>
              <p>{latest ? formatTime(latest.timestamp) : "Sem dados"}</p>
            </article>
            <article>
              <span><Gauge size={18} /></span>
              <small>Acelerometro</small>
              <strong>{slope.toFixed(1)}g</strong>
              <p>{latest ? formatTime(latest.timestamp) : "Sem dados"}</p>
            </article>
            <article>
              <span><Waves size={18} /></span>
              <small>Vibracao</small>
              <strong>{vibration.toFixed(1)}</strong>
              <p>{vibration > 25 ? "Subindo" : "Estavel"}</p>
            </article>
          </section>

          <section className="dashboard-main">
            <article className="panel dashboard-chart-panel">
              <div className="panel-heading">
                <div>
                  <h2>Grafico de umidade</h2>
                  <p>Ultimas leituras do higrometro</p>
                </div>
                <Sparkles size={18} />
              </div>
              <div className="line-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartRows}>
                    <CartesianGrid stroke="#333333" strokeDasharray="3 3" opacity={0.5} />
                    <XAxis dataKey="time" stroke="#CCCCCC" tickLine={false} axisLine={false} fontSize={11} />
                    <YAxis stroke="#CCCCCC" tickLine={false} axisLine={false} fontSize={11} />
                    <Tooltip contentStyle={{ background: "#1A1A1A", border: "1px solid #333333", borderRadius: 8 }} />
                    <Line type="monotone" dataKey="umidade" stroke="#4CAF50" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className="panel risk-panel">
              <div className="panel-heading">
                <div>
                  <h2>Visao de risco</h2>
                  <p>Interpretacao atual do sistema</p>
                </div>
              </div>
              <div className="risk-summary-box">
                <small>Ultima leitura processada</small>
                <strong>{latest ? `${moisture.toFixed(1)}%` : "Sem dados"}</strong>
                <p>{latest ? `${latest.id_simulacao} - ${formatTime(latest.timestamp)}` : "Nenhuma leitura recebida"}</p>
              </div>
              <div className={`risk-summary-box ${highestAlert}`}>
                <small>Interpretacao</small>
                <strong>{alertLabels[highestAlert]}</strong>
                <p>{highestAlert === "verde" ? "Condicao estavel dentro dos limites definidos." : "Ha sinais que recomendam acompanhamento continuo."}</p>
              </div>
            </article>
          </section>

          <section className="info-card-grid">
            <article>
              <h3>Ultimos registros</h3>
              {ordered.slice(-5).reverse().map((reading) => (
                <div key={reading.id}>
                  <strong>{toPercent(reading.sensores.umidade_solo).toFixed(1)}%</strong>
                  <span>{formatTime(reading.timestamp)}</span>
                </div>
              ))}
            </article>
            <article>
              <h3>Indicador tecnico</h3>
              <p>O painel prioriza dados reais recebidos pela API da raiz para analise operacional.</p>
              <p>Os dados sao adaptados para a organizacao visual do dashboard `sensores_pi`.</p>
            </article>
            <article>
              <h3>Atencao</h3>
              <p>Valores de risco sao indicativos e baseados nos limites atuais do backend.</p>
              <p>Mantenha a ESP32 conectada para maior precisao historica.</p>
            </article>
          </section>
        </>
      )}

      {activeView === "monitoring" && (
        <>
          <SectionTitle eyebrow="Monitoramento" title="Leituras em tempo quase real">
            <button className="inline-action" onClick={loadReadings} type="button">
              <RefreshCw size={16} />
              Atualizar
            </button>
          </SectionTitle>

          <section className="analysis-grid">
            <article className="panel wide">
              <div className="panel-heading">
                <div>
                  <h2>Evolucao dos sensores</h2>
                  <p>Ultimas leituras recebidas da API da raiz</p>
                </div>
                <span className={`alert-pill ${highestAlert}`}>{alertLabels[highestAlert]}</span>
              </div>
              <div className="line-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartRows}>
                    <CartesianGrid stroke="#293548" strokeDasharray="3 8" />
                    <XAxis dataKey="time" stroke="#8d9ab1" tickLine={false} axisLine={false} />
                    <YAxis stroke="#8d9ab1" tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ background: "#111720", border: "1px solid #334155", borderRadius: 8 }} />
                    <Line type="monotone" dataKey="umidade" stroke="#18d0a8" strokeWidth={3} dot={false} />
                    <Line type="monotone" dataKey="vibracao" stroke="#38a5ff" strokeWidth={3} dot={false} />
                    <Line type="monotone" dataKey="inclinacao" stroke="#b786ff" strokeWidth={3} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Eventos recentes</h2>
                  <p>Alertas e possiveis deslizamentos</p>
                </div>
              </div>
              <div className="event-list">
                {events.slice(0, 8).map((item) => (
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
                {events.length === 0 && <p className="muted-copy">Nenhum alerta carregado.</p>}
              </div>
            </article>
          </section>

          <section className="table-panel">
            <div className="panel-heading">
              <div>
                <h2>Registros brutos</h2>
                <p>Dados no contrato atual do backend FastAPI</p>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Horario</th>
                    <th>Simulacao</th>
                    <th>Umidade</th>
                    <th>Vibracao</th>
                    <th>Inclinacao</th>
                    <th>Nivel</th>
                  </tr>
                </thead>
                <tbody>
                  {[...ordered].reverse().slice(0, 18).map((item) => (
                    <tr key={item.id}>
                      <td>{formatTime(item.timestamp)}</td>
                      <td>{item.id_simulacao}</td>
                      <td>{toPercent(item.sensores.umidade_solo).toFixed(1)}%</td>
                      <td>{vibrationIndex(item).toFixed(1)}</td>
                      <td>{slopeDegrees(item).toFixed(1)} graus</td>
                      <td>
                        <span className={`alert-pill ${item.nivel_alerta}`}>{alertLabels[item.nivel_alerta]}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {activeView === "history" && (
        <>
          <SectionTitle eyebrow="Historico" title="Analise consolidada das leituras" />

          <section className="history-grid">
            <article className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Distribuicao por risco</h2>
                  <p>Total classificado no backend</p>
                </div>
              </div>
              <div className="bar-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={[
                      { nivel: "Seguro", total: riskCounts.verde, fill: "#18d0a8" },
                      { nivel: "Atencao", total: riskCounts.amarelo, fill: "#ffdd75" },
                      { nivel: "Elevado", total: riskCounts.laranja, fill: "#ffbd59" },
                      { nivel: "Critico", total: riskCounts.vermelho, fill: "#ff6b7a" },
                    ]}
                  >
                    <CartesianGrid stroke="#293548" strokeDasharray="3 8" />
                    <XAxis dataKey="nivel" stroke="#8d9ab1" tickLine={false} axisLine={false} />
                    <YAxis stroke="#8d9ab1" tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip contentStyle={{ background: "#111720", border: "1px solid #334155", borderRadius: 8 }} />
                    <Bar dataKey="total" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Pontuacao de risco</h2>
                  <p>Serie derivada das leituras recentes</p>
                </div>
              </div>
              <div className="bar-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartRows}>
                    <CartesianGrid stroke="#293548" strokeDasharray="3 8" />
                    <XAxis dataKey="time" stroke="#8d9ab1" tickLine={false} axisLine={false} />
                    <YAxis stroke="#8d9ab1" tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ background: "#111720", border: "1px solid #334155", borderRadius: 8 }} />
                    <Area type="monotone" dataKey="risco" stroke="#ffbd59" fill="#ffbd5933" strokeWidth={3} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </article>
          </section>

          <section className="timeline-panel">
            <div className="panel-heading">
              <div>
                <h2>Linha do tempo</h2>
                <p>Resumo das ultimas leituras por horario</p>
              </div>
            </div>
            <div className="timeline-list">
              {[...ordered].reverse().slice(0, 14).map((item) => (
                <article key={item.id} className="timeline-item">
                  <span className={`event-dot ${item.nivel_alerta}`} />
                  <div>
                    <strong>{formatDate(item.timestamp)} as {formatTime(item.timestamp)}</strong>
                    <p>
                      {item.id_simulacao}: umidade {toPercent(item.sensores.umidade_solo).toFixed(1)}%, vibracao{" "}
                      {vibrationIndex(item).toFixed(1)}.
                    </p>
                  </div>
                  <span className={`alert-pill ${item.nivel_alerta}`}>{alertLabels[item.nivel_alerta]}</span>
                </article>
              ))}
            </div>
          </section>
        </>
      )}

      {activeView === "predictions" && (
        <>
          <SectionTitle eyebrow="Predicoes" title="Tendencias calculadas no frontend">
            <span className="section-note">Sem depender de rotas Next.js; usa as leituras carregadas da raiz.</span>
          </SectionTitle>

          <section className="prediction-grid">
            {predictions.map((metric) => (
              <PredictionCard key={metric.id} metric={metric} />
            ))}
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Historico usado nas predicoes</h2>
                <p>As linhas mostram os ultimos pontos considerados pelo calculo linear simples.</p>
              </div>
            </div>
            <div className="line-chart compact">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartRows}>
                  <CartesianGrid stroke="#293548" strokeDasharray="3 8" />
                  <XAxis dataKey="time" stroke="#8d9ab1" tickLine={false} axisLine={false} />
                  <YAxis stroke="#8d9ab1" tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: "#111720", border: "1px solid #334155", borderRadius: 8 }} />
                  {predictions.map((metric) => (
                    <Line
                      key={metric.id}
                      type="monotone"
                      dataKey={metric.id}
                      stroke={metric.color}
                      strokeWidth={3}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
