import { Button } from "@/components/ui/button";

export const tiers = [
  { name: "Single", price: 99, panels: "6 panels", feats: ["1 style", "PDF download", "Share link"] },
  { name: "Story", price: 299, panels: "12 panels", feats: ["3 styles to choose", "HD PDF + PNG", "Share link", "No watermark"], featured: true },
  { name: "Saga", price: 499, panels: "24 panels", feats: ["All styles", "Print-ready PDF", "Custom dedication", "Priority queue"] },
];

export function PricingStrip({ onOpen }: { onOpen: () => void }) {
  return (
    <section id="pricing" className="py-20 bg-zap relative overflow-hidden">
      <div className="absolute inset-0 halftone-bg opacity-10 pointer-events-none" />
      <div className="mx-auto max-w-7xl px-4 sm:px-6 relative">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-heavy text-4xl md:text-5xl text-ink">Pick your tier.</h2>
          <p className="mt-3 text-ink/80 font-medium">Pay once. No subscription. Yours forever.</p>
        </div>
        <div className="mt-12 grid md:grid-cols-3 gap-6">
          {tiers.map((t) => (
            <div
              key={t.name}
              className={`p-6 ink-border-thick ${t.featured ? "bg-hero text-paper hard-shadow-lg scale-105" : "bg-paper text-ink hard-shadow"}`}
            >
              {t.featured && (
                <div className="inline-block bg-zap text-ink ink-border px-2 py-0.5 text-xs font-bold mb-3 -rotate-2">MOST POPULAR</div>
              )}
              <h3 className="font-heavy text-2xl">{t.name}</h3>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="font-display text-5xl">₹{t.price}</span>
              </div>
              <p className={`mt-1 font-semibold text-sm ${t.featured ? "text-paper/80" : "text-ink/60"}`}>{t.panels}</p>
              <ul className="mt-5 space-y-2 font-medium text-sm">
                {t.feats.map((f) => (
                  <li key={f} className="flex gap-2"><span>✓</span>{f}</li>
                ))}
              </ul>
              <Button
                onClick={onOpen}
                className={`mt-6 w-full ink-border font-heavy ${t.featured ? "bg-paper text-ink hover:bg-zap" : "bg-ink text-paper hover:bg-hero"}`}
              >
                Choose {t.name}
              </Button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
