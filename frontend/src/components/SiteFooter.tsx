export function SiteFooter() {
  return (
    <footer className="bg-ink text-paper py-10 border-t-4 border-hero">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 flex flex-col md:flex-row justify-between gap-4 items-center">
        <div className="flex items-center gap-2">
          <span className="inline-block bg-hero text-paper px-2 py-0.5 -rotate-3 font-display text-xl tracking-wider">COMIC</span>
          <span className="font-display text-xl tracking-wider">ME!</span>
        </div>
        <p className="text-sm text-paper/60 font-medium">© {new Date().getFullYear()} ComicMe — Made with ⚡ and ink.</p>
        <div className="flex gap-4 text-sm font-semibold">
          <a href="#" className="hover:text-zap">Twitter</a>
          <a href="#" className="hover:text-zap">Instagram</a>
          <a href="#" className="hover:text-zap">Terms</a>
        </div>
      </div>
    </footer>
  );
}
