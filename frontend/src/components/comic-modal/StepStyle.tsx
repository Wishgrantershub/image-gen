import type { ComicState, StyleKey } from "./types";
import manga from "@/assets/style-manga.jpg";
import pixar from "@/assets/style-pixar.jpg";
import superhero from "@/assets/style-superhero.jpg";

const styles: { key: StyleKey; label: string; img: string; desc: string }[] = [
  { key: "manga", label: "Manga", img: manga, desc: "B&W, screentones, dramatic angles" },
  { key: "pixar", label: "Pixar", img: pixar, desc: "3D, warm, cheerful" },
  { key: "superhero", label: "Superhero", img: superhero, desc: "Bold ink, classic Marvel/DC" },
];

export function StepStyle({ state, set }: { state: ComicState; set: (p: Partial<ComicState>) => void }) {
  return (
    <div>
      <h3 className="font-heavy text-2xl text-ink mb-1">Pick a style.</h3>
      <p className="text-ink/70 font-medium mb-5 text-sm">Each one totally changes the vibe.</p>
      <div className="grid grid-cols-3 gap-3">
        {styles.map((s) => {
          const active = state.style === s.key;
          return (
            <button
              key={s.key}
              onClick={() => set({ style: s.key })}
              className={`text-left bg-paper ink-border-thick transition-all ${active ? "hard-shadow-hero -translate-y-1" : "hover:hard-shadow"}`}
            >
              <div className="relative">
                <img src={s.img} alt={s.label} className="w-full aspect-square object-cover" />
                {active && (
                  <div className="absolute top-2 right-2 w-8 h-8 bg-hero text-paper ink-border flex items-center justify-center font-heavy">✓</div>
                )}
              </div>
              <div className="p-3 border-t-[3px] border-ink">
                <p className="font-heavy text-ink">{s.label}</p>
                <p className="text-xs text-ink/60 font-medium mt-0.5">{s.desc}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
