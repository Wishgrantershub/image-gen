import type { ComicState } from "./types";
import { tiers } from "@/components/PricingStrip";

export function StepTier({ state, set }: { state: ComicState; set: (p: Partial<ComicState>) => void }) {
  return (
    <div>
      <h3 className="font-heavy text-2xl text-ink mb-1">Pick a tier.</h3>
      <p className="text-ink/70 font-medium mb-5 text-sm">Pay once, comic's yours.</p>
      <div className="grid grid-cols-3 gap-3">
        {tiers.map((t) => {
          const active = state.tier === t.name;
          return (
            <button
              key={t.name}
              onClick={() => set({ tier: t.name as ComicState["tier"] })}
              className={`text-left p-4 ink-border-thick transition-all ${active ? "bg-hero text-paper hard-shadow -translate-y-1" : "bg-paper text-ink hover:bg-zap/30"}`}
            >
              <p className="font-heavy text-lg">{t.name}</p>
              <p className="font-display text-3xl mt-1">₹{t.price}</p>
              <p className={`text-xs font-bold mt-1 ${active ? "text-paper/80" : "text-ink/60"}`}>{t.panels}</p>
              <ul className={`mt-3 space-y-1 text-xs font-medium ${active ? "text-paper/90" : "text-ink/80"}`}>
                {t.feats.slice(0, 3).map((f) => (
                  <li key={f}>✓ {f}</li>
                ))}
              </ul>
            </button>
          );
        })}
      </div>
    </div>
  );
}
