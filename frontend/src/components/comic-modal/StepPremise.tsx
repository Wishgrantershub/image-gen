import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import type { ComicState } from "./types";

const SURPRISE_PREMISES = [
  "Discovers a secret door in their bedroom leading to a neon cloud city.",
  "Accidentally drinks a potion that lets them talk to stray animals.",
  "Finds an ancient robot buried in the backyard who needs a co-pilot.",
  "Wakes up with gravity-defying sneakers and must save the school from aliens.",
  "Enters a cooking contest where every ingredient has a magical superpower.",
  "A quiet detective who can see the last 60 seconds of any object they touch.",
  "Inherits a cosmic starship that only runs on spicy ramen noodles.",
  "Teams up with a mischievous thunder fox to restore daylight to the valley.",
];

const ARCHETYPES = [
  { label: "🚀 Space Ranger", text: "Crash-lands on a glowing crystal asteroid and discovers a hidden alien sanctuary." },
  { label: "⚔️ Samurai", text: "A young blade master on a quest to recover the stolen constellation sword." },
  { label: "🐉 Dragon Tamer", text: "Befriends an abandoned baby dragon whose sneezes create miniature fireworks." },
  { label: "🕵️ Time Detective", text: "Investigates mysterious clockwork anomalies causing yesterday to repeat backwards." },
  { label: "⚡ Superhero", text: "Gains the power of lightning and leaps across rooftops to defend the city." },
];

export function StepPremise({ state, set }: { state: ComicState; set: (p: Partial<ComicState>) => void }) {
  const left = 200 - state.premise.length;

  const handleSurprise = () => {
    const random = SURPRISE_PREMISES[Math.floor(Math.random() * SURPRISE_PREMISES.length)];
    set({ premise: random });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-heavy text-2xl text-ink">What's the story?</h3>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleSurprise}
          className="text-xs font-bold ink-border bg-zap/30 hover:bg-zap flex items-center gap-1.5"
        >
          <span>🎲</span> Surprise Me
        </Button>
      </div>
      <p className="text-ink/70 font-medium mb-3 text-sm">One sentence. We'll do the rest.</p>

      <Textarea
        value={state.premise}
        onChange={(e) => set({ premise: e.target.value.slice(0, 200) })}
        placeholder="A mild-mannered hero who discovers their watch can pause time for 10 seconds…"
        rows={3}
        className="ink-border-thick bg-paper font-medium text-base resize-none focus-visible:ring-hero"
      />

      <div className="flex justify-between mt-1.5 text-xs font-bold mb-4">
        <span className="text-ink/60">Tip: Click an archetype below or write your own.</span>
        <span className={left < 30 ? "text-hero" : "text-ink/60"}>{left} left</span>
      </div>

      <div>
        <p className="text-[11px] font-bold text-ink/50 uppercase tracking-wider mb-2">Quick Archetypes</p>
        <div className="flex flex-wrap gap-1.5">
          {ARCHETYPES.map((a) => (
            <button
              key={a.label}
              type="button"
              onClick={() => set({ premise: a.text })}
              className="text-xs font-bold px-2.5 py-1 ink-border bg-paper hover:bg-zap/40 transition-colors"
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
