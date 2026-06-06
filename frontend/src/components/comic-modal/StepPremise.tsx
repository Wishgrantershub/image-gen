import { Textarea } from "@/components/ui/textarea";
import type { ComicState } from "./types";

const examples = [
  "A barista who discovers the espresso machine is a portal to another dimension.",
  "A grandma vigilante taking down scammers one phone call at a time.",
  "Two best friends crash-land on a candy planet.",
];

export function StepPremise({ state, set }: { state: ComicState; set: (p: Partial<ComicState>) => void }) {
  const left = 200 - state.premise.length;
  return (
    <div>
      <h3 className="font-heavy text-2xl text-ink mb-1">What's the story?</h3>
      <p className="text-ink/70 font-medium mb-5 text-sm">One sentence. We'll do the rest.</p>
      <Textarea
        value={state.premise}
        onChange={(e) => set({ premise: e.target.value.slice(0, 200) })}
        placeholder="A mild-mannered programmer who can stop time, but only for 10 seconds…"
        rows={4}
        className="ink-border-thick bg-paper font-medium text-base resize-none focus-visible:ring-hero"
      />
      <div className="flex justify-between mt-2 text-xs font-bold">
        <span className="text-ink/60">Try: "{examples[Math.floor(state.premise.length / 70) % examples.length]}"</span>
        <span className={left < 30 ? "text-hero" : "text-ink/60"}>{left} left</span>
      </div>
    </div>
  );
}
