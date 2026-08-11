export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

export interface Candle {
  symbol: string;
  venue: string;
  timeframe: string;
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  confirmed: boolean;
}

export interface ConfluenceFactor {
  school: string;
  description: string;
  weight: number;
}

export interface RiskPlan {
  entry: number;
  stop_loss: number;
  take_profits: number[];
  risk_reward: number[];
  atr: number;
}

export interface TradeSignal {
  symbol: string;
  venue: string;
  timeframe: string;
  direction: "long" | "short";
  ts: string;
  confluences: ConfluenceFactor[];
  confluence_score: number;
  risk: RiskPlan;
  note?: string;
}

export interface DetectedLevel {
  label: string;
  price: number | null;
  price_range: [number, number] | null;
  pixel_bbox: [number, number, number, number];
  confidence: number;
}

export interface ChartAnalysisResponse {
  symbol: string | null;
  levels: DetectedLevel[];
  notes: string;
}

async function getJson<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Request failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as T;
}

export function fetchCandles(venue: string, symbol: string, timeframe = "1m", limit = 200) {
  return getJson<Candle[]>(
    `/market/candles?venue=${venue}&symbol=${symbol}&timeframe=${timeframe}&limit=${limit}`
  );
}

export function fetchSignal(venue: string, symbol: string, timeframe = "1m") {
  return getJson<TradeSignal>(`/signals?venue=${venue}&symbol=${symbol}&timeframe=${timeframe}`);
}

export function candleWsUrl(venue: string, symbol: string, timeframe = "1m") {
  return `${WS_BASE}/market/ws/${venue}/${symbol}/${timeframe}`;
}

export async function analyzeChart(
  file: File,
  opts: { symbol?: string; priceAtTop?: number; priceAtBottom?: number } = {}
): Promise<ChartAnalysisResponse> {
  const form = new FormData();
  form.append("image", file);
  if (opts.symbol) form.append("symbol", opts.symbol);
  if (opts.priceAtTop !== undefined) form.append("price_at_top", String(opts.priceAtTop));
  if (opts.priceAtBottom !== undefined) form.append("price_at_bottom", String(opts.priceAtBottom));

  const res = await fetch(`${API_BASE}/analyze-chart`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Chart analysis failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as ChartAnalysisResponse;
}
