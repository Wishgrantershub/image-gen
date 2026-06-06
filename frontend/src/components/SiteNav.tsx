import { Button } from "@/components/ui/button";
import { Link } from "@tanstack/react-router";

export function SiteNav({ onOpen }: { onOpen: () => void }) {
  return (
    <header className="sticky top-0 z-40 bg-paper/90 backdrop-blur border-b-4 border-ink">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <span className="inline-block bg-hero text-paper px-2 py-0.5 -rotate-3 font-display text-2xl tracking-wider ink-border">
            COMIC
          </span>
          <span className="font-display text-2xl tracking-wider text-ink">ME!</span>
        </Link>
        <nav className="hidden md:flex items-center gap-8 font-semibold text-ink">
          <a href="/#how" className="hover:text-hero transition-colors">How it works</a>
          <a href="/#samples" className="hover:text-hero transition-colors">Samples</a>
          <a href="/#pricing" className="hover:text-hero transition-colors">Pricing</a>
          <Link
            to="/library"
            className="hover:text-hero transition-colors font-semibold"
            activeProps={{ className: "text-hero underline underline-offset-4" }}
          >
            My Library
          </Link>
        </nav>
        <Button
          onClick={onOpen}
          className="bg-hero text-paper hover:bg-hero hover:-translate-y-0.5 ink-border hard-shadow font-heavy tracking-wide transition-transform"
        >
          Make Your Comic
        </Button>
      </div>
    </header>
  );
}
