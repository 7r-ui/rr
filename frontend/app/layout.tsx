import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NexusTrade AI",
  description: "Real-time financial analysis platform — SMC/Elliott confluence signals, live market data, AI chart vision.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
