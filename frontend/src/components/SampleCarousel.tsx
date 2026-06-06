import { useRef } from "react";
import s1 from "@/assets/sample-1.jpg";
import s2 from "@/assets/sample-2.jpg";
import s3 from "@/assets/sample-3.jpg";

const samples = [
  { img: s1, title: "The Last Defender", style: "Superhero" },
  { img: s2, title: "Sakura Strike", style: "Manga" },
  { img: s3, title: "Pip's Big Adventure", style: "Pixar" },
];

export function SampleCarousel() {
  const ref = useRef<HTMLDivElement>(null);
  const scroll = (dir: 1 | -1) => {
    ref.current?.scrollBy({ left: dir * 400, behavior: "smooth" });
  };

  return (
    <section id="samples" className="py-20 bg-ink text-paper relative overflow-hidden">
      <div className="absolute inset-0 halftone-red opacity-15 pointer-events-none" />
      <div className="mx-auto max-w-7xl px-4 sm:px-6 relative">
        <div className="flex items-end justify-between mb-10">
          <div>
            <h2 className="font-heavy text-4xl md:text-5xl">Recently made.</h2>
            <p className="mt-2 text-paper/70 font-medium">Real comics from real people. Made in seconds.</p>
          </div>
          <div className="hidden md:flex gap-2">
            <button onClick={() => scroll(-1)} aria-label="Previous" className="w-12 h-12 ink-border bg-paper text-ink font-heavy hover:bg-zap transition-colors">←</button>
            <button onClick={() => scroll(1)} aria-label="Next" className="w-12 h-12 ink-border bg-paper text-ink font-heavy hover:bg-zap transition-colors">→</button>
          </div>
        </div>
        <div ref={ref} className="flex gap-6 overflow-x-auto snap-x snap-mandatory pb-6 -mx-4 px-4 scroll-smooth">
          {samples.map((s, i) => (
            <article key={i} className="snap-start shrink-0 w-[300px] md:w-[360px]">
              <div className="bg-paper p-3 ink-border-thick hard-shadow-hero">
                <img src={s.img} alt={s.title} width={800} height={1024} loading="lazy" className="w-full aspect-[4/5] object-cover ink-border" />
                <div className="mt-3 flex items-center justify-between">
                  <h3 className="font-heavy text-ink text-lg">{s.title}</h3>
                  <span className="text-xs bg-zap ink-border px-2 py-0.5 font-bold text-ink">{s.style}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
