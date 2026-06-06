const steps = [
  { n: "01", t: "Upload", d: "Drop in a clear photo of yourself, a friend, your dog — anyone really." },
  { n: "02", t: "Pick a style", d: "Manga, Pixar, or classic Superhero. Each one a totally different vibe." },
  { n: "03", t: "Get your comic", d: "A 6-panel comic page lands in your inbox. PDF + share link included." },
];

export function HowItWorks() {
  return (
    <section id="how" className="py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="max-w-2xl">
          <h2 className="font-heavy text-4xl md:text-5xl text-ink">How it works.</h2>
          <p className="mt-3 text-ink/70 font-medium">Three steps. One coffee break. A comic starring you.</p>
        </div>
        <div className="mt-12 grid md:grid-cols-3 gap-6">
          {steps.map((s, i) => (
            <div
              key={s.n}
              className="bg-paper ink-border-thick p-6 hard-shadow relative"
              style={{ transform: `rotate(${i === 1 ? 1 : -0.5}deg)` }}
            >
              <div className="font-display text-5xl text-hero">{s.n}</div>
              <h3 className="mt-2 font-heavy text-2xl text-ink">{s.t}</h3>
              <p className="mt-2 text-ink/80 font-medium">{s.d}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
