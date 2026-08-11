"use client";

import { useState } from "react";
import { analyzeChart, ChartAnalysisResponse } from "@/lib/api";

export default function ChartUpload() {
  const [result, setResult] = useState<ChartAnalysisResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const res = await analyzeChart(file);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chart analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="glass p-6">
      <h3 className="text-lg font-semibold mb-2">AI Vision Chart Parser</h3>
      <p className="text-white/50 text-sm mb-4">
        Upload a chart screenshot to detect support/resistance levels via edge detection, plus
        SMC-pattern estimates from the vision model (if configured).
      </p>
      <input
        type="file"
        accept="image/png,image/jpeg"
        onChange={onFileChange}
        className="text-sm text-white/70 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary file:text-black file:cursor-pointer"
      />
      {busy && <p className="text-white/50 text-sm mt-3">Analyzing…</p>}
      {error && <p className="text-danger text-sm mt-3">{error}</p>}
      {result && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-white/40">{result.notes}</p>
          <ul className="text-sm space-y-1">
            {result.levels.map((lv, i) => (
              <li key={i} className="flex justify-between">
                <span className="capitalize text-white/70">{lv.label}</span>
                <span className="font-mono">
                  {lv.price !== null ? lv.price.toFixed(4) : "(unmapped)"}{" "}
                  <span className="text-white/40">{(lv.confidence * 100).toFixed(0)}%</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
