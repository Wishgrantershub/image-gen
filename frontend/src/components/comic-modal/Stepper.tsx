const labels = ["Photo", "Style", "Premise", "Tier", "Generate"];

export function Stepper({ step }: { step: number }) {
  return (
    <div className="flex items-center gap-2 w-full">
      {labels.map((label, i) => {
        const n = i + 1;
        const active = n === step;
        const done = n < step;
        return (
          <div key={label} className="flex-1 flex flex-col items-center gap-1">
            <div className={`w-8 h-8 ink-border flex items-center justify-center font-heavy text-sm ${active ? "bg-hero text-paper" : done ? "bg-ink text-paper" : "bg-paper text-ink"}`}>
              {done ? "✓" : n}
            </div>
            <span className={`text-[10px] uppercase font-bold tracking-wider ${active ? "text-hero" : "text-ink/50"}`}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}
