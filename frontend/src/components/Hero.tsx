import { Button } from "@/components/ui/button";
import heroImg from "@/assets/hero-comic.jpg";

export function Hero({ onOpen }: { onOpen: () => void }) {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 halftone-bg opacity-20 pointer-events-none" />
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-16 md:py-24 grid md:grid-cols-2 gap-12 items-center relative">
        <div>
          <div className="inline-block bg-zap ink-border px-3 py-1 mb-6 font-bold text-sm -rotate-2">
            ⚡ AI COMIC GENERATOR
          </div>
          <h1 className="font-heavy text-5xl md:text-7xl leading-[0.95] text-ink">
            Turn anyone into a{" "}
            <span className="relative inline-block">
              <span className="relative z-10 text-paper px-2 bg-hero -rotate-1 inline-block">comic book</span>
            </span>{" "}
            hero in <span className="text-hero">60 seconds.</span>
          </h1>
          <p className="mt-6 text-lg text-ink/80 max-w-md font-medium">
            Upload a photo. Pick a style. Get a 6-panel comic starring you — ready to print, share, or frame.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Button
              onClick={onOpen}
              size="lg"
              className="bg-ink text-paper hover:bg-ink hover:-translate-y-1 ink-border hard-shadow-hero font-heavy text-lg px-8 py-6 transition-transform"
            >
              Make Your Comic →
            </Button>
            <a
              href="#samples"
              className="inline-flex items-center px-6 py-3 font-bold text-ink hover:text-hero transition-colors underline underline-offset-4"
            >
              See samples
            </a>
          </div>
          <div className="mt-8 flex items-center gap-6 text-sm font-semibold text-ink/70">
            <span>★★★★★ 12k+ comics made</span>
            <span className="hidden sm:inline">⚡ ~60s avg</span>
          </div>
        </div>
        <div className="relative">
          <div className="absolute -inset-4 bg-zap -rotate-3 ink-border" aria-hidden />
          <img
            src={heroImg}
            alt="Pop-art comic hero illustration"
            width={1024}
            height={1024}
            className="relative ink-border-thick w-full aspect-square object-cover"
          />
          <div className="absolute -bottom-6 -right-4 bg-paper ink-border px-4 py-2 font-display text-2xl rotate-6 hard-shadow">
            POW!
          </div>
        </div>
      </div>
    </section>
  );
}
