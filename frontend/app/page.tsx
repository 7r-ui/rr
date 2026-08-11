"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import ChartPanel from "@/components/ChartPanel";
import SignalsPanel from "@/components/SignalsPanel";
import ChartUpload from "@/components/ChartUpload";

const WATCHLIST = [
  { venue: "binance", symbol: "btcusdt", label: "BTC/USDT (Binance)" },
  { venue: "binance", symbol: "ethusdt", label: "ETH/USDT (Binance)" },
  { venue: "bybit", symbol: "btcusdt", label: "BTC/USDT (Bybit)" },
];

export default function Home() {
  const [selected, setSelected] = useState(WATCHLIST[0]);
  const timeframe = "1m";

  return (
    <div className="flex gap-6 p-6 max-w-[1600px] mx-auto">
      <Sidebar />
      <main className="flex-1 space-y-6">
        <header className="glass p-5 flex justify-between items-center">
          <h2 className="text-xl font-semibold">Market Dashboard</h2>
          <select
            value={`${selected.venue}:${selected.symbol}`}
            onChange={(e) => {
              const [venue, symbol] = e.target.value.split(":");
              const match = WATCHLIST.find((w) => w.venue === venue && w.symbol === symbol);
              if (match) setSelected(match);
            }}
            className="bg-white/10 border border-white/10 rounded-lg px-3 py-2 text-sm"
          >
            {WATCHLIST.map((w) => (
              <option key={`${w.venue}:${w.symbol}`} value={`${w.venue}:${w.symbol}`}>
                {w.label}
              </option>
            ))}
          </select>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <ChartPanel venue={selected.venue} symbol={selected.symbol} />
          </div>
          <SignalsPanel venue={selected.venue} symbol={selected.symbol} timeframe={timeframe} />
        </div>

        <ChartUpload />
      </main>
    </div>
  );
}
