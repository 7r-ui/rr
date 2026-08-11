"use client";

import { useEffect, useState } from "react";
import { fetchSignal, TradeSignal } from "@/lib/api";

export default function SignalsPanel({ venue, symbol, timeframe }: { venue: string; symbol: string; timeframe: string }) {
  const [signal, setSignal] = useState<TradeSignal | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      const s = await fetchSignal(venue, symbol, timeframe);
      if (!cancelled) setSignal(s);
    }
    poll();
    const id = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [venue, symbol, timeframe]);

  return (
    <div className="glass p-6">
      <h3 className="text-lg font-semibold mb-4">Confluence Signal</h3>
      {signal === undefined && <p className="text-white/50 text-sm">Loading…</p>}
      {signal === null && (
        <p className="text-white/50 text-sm">
          No aligned multi-school signal right now — SMC, liquidity and Elliott factors aren&apos;t
          agreeing, or the plan doesn&apos;t clear the minimum risk:reward.
        </p>
      )}
      {signal && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span
              className={`px-3 py-1 rounded-full text-sm font-bold uppercase ${
                signal.direction === "long" ? "bg-success/20 text-success" : "bg-danger/20 text-danger"
              }`}
            >
              {signal.direction}
            </span>
            <span className="text-white/60 text-sm">score {signal.confluence_score.toFixed(2)}</span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-white/50">Entry</div>
              <div className="font-mono">{signal.risk.entry.toFixed(4)}</div>
            </div>
            <div>
              <div className="text-white/50">Stop Loss</div>
              <div className="font-mono text-danger">{signal.risk.stop_loss.toFixed(4)}</div>
            </div>
            <div className="col-span-2">
              <div className="text-white/50">Take Profits (R:R)</div>
              <div className="font-mono text-success">
                {signal.risk.take_profits
                  .map((tp, i) => `${tp.toFixed(4)} (${signal.risk.risk_reward[i].toFixed(1)}R)`)
                  .join(" · ")}
              </div>
            </div>
          </div>
          <ul className="space-y-1 text-sm text-white/70">
            {signal.confluences.map((c, i) => (
              <li key={i}>
                <span className="text-primary uppercase text-xs mr-2">{c.school}</span>
                {c.description}
              </li>
            ))}
          </ul>
          {signal.note && <p className="text-xs text-white/40">{signal.note}</p>}
        </div>
      )}
    </div>
  );
}
