const NAV_ITEMS = [
  { icon: "📊", label: "Dashboard" },
  { icon: "🕯️", label: "Charts" },
  { icon: "⚡", label: "Signals" },
  { icon: "👁️", label: "Vision Parser" },
  { icon: "⚙️", label: "Settings" },
];

export default function Sidebar() {
  return (
    <aside className="glass w-64 shrink-0 p-6 h-fit sticky top-6">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
          NexusTrade AI
        </h1>
        <p className="text-white/50 text-xs mt-1">Real-time confluence trading platform</p>
      </div>
      <nav className="space-y-2">
        {NAV_ITEMS.map((item, i) => (
          <div
            key={item.label}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl cursor-pointer transition ${
              i === 0 ? "bg-primary/20 text-white border-r-2 border-primary" : "text-white/60 hover:bg-white/10"
            }`}
          >
            <span>{item.icon}</span>
            <span className="text-sm">{item.label}</span>
          </div>
        ))}
      </nav>
    </aside>
  );
}
