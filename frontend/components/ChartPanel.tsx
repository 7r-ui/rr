"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickData } from "lightweight-charts";
import { Candle, candleWsUrl, fetchCandles } from "@/lib/api";

const TIMEFRAMES = ["1m", "5m", "15m", "1h"];

function toCandlestickData(c: Candle): CandlestickData {
  return {
    time: Math.floor(new Date(c.open_time).getTime() / 1000) as CandlestickData["time"],
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  };
}

export default function ChartPanel({ venue, symbol }: { venue: string; symbol: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [timeframe, setTimeframe] = useState("1m");
  const [status, setStatus] = useState<"loading" | "live" | "empty">("loading");

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#cbd5e1" },
      grid: { vertLines: { color: "rgba(255,255,255,0.05)" }, horzLines: { color: "rgba(255,255,255,0.05)" } },
      width: containerRef.current.clientWidth,
      height: 420,
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#4ade80",
      downColor: "#f87171",
      borderVisible: false,
      wickUpColor: "#4ade80",
      wickDownColor: "#f87171",
    });
    chartRef.current = chart;
    seriesRef.current = series;

    const onResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let cancelled = false;

    async function load() {
      setStatus("loading");
      const candles = await fetchCandles(venue, symbol, timeframe);
      if (cancelled || !seriesRef.current) return;
      if (!candles || candles.length === 0) {
        setStatus("empty");
        return;
      }
      seriesRef.current.setData(candles.map(toCandlestickData));
      setStatus("live");

      ws = new WebSocket(candleWsUrl(venue, symbol, timeframe));
      ws.onmessage = (event) => {
        if (!seriesRef.current) return;
        try {
          const candle: Candle = JSON.parse(event.data);
          seriesRef.current.update(toCandlestickData(candle));
        } catch {
          // ignore malformed frames
        }
      };
    }
    load();

    return () => {
      cancelled = true;
      ws?.close();
    };
  }, [venue, symbol, timeframe]);

  return (
    <div className="glass p-6 h-[500px] flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold uppercase tracking-wide">
          {symbol} <span className="text-white/40 text-sm">{venue}</span>
        </h3>
        <div className="flex gap-2">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1 rounded-lg text-sm transition ${
                tf === timeframe ? "bg-primary text-black" : "bg-white/10 text-white/70 hover:bg-white/20"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
      {status === "empty" && (
        <div className="text-white/50 text-sm mb-2">
          No cached candles yet for this venue/symbol/timeframe — ingestion may still be warming up.
        </div>
      )}
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
