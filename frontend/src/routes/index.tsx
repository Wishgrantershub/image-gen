import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { SiteNav } from "@/components/SiteNav";
import { Hero } from "@/components/Hero";
import { SampleCarousel } from "@/components/SampleCarousel";
import { HowItWorks } from "@/components/HowItWorks";
import { PricingStrip } from "@/components/PricingStrip";
import { SiteFooter } from "@/components/SiteFooter";
import { ComicModal } from "@/components/comic-modal/ComicModal";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ComicMe — Turn anyone into a comic book hero in 60 seconds" },
      { name: "description", content: "Upload a photo, pick a style, get a 6-panel AI-generated comic starring you. Manga, Pixar, or Superhero. From ₹99." },
      { property: "og:title", content: "ComicMe — Your AI comic generator" },
      { property: "og:description", content: "Turn anyone into a comic book hero in 60 seconds." },
      { property: "og:type", content: "website" },
    ],
  }),
  component: Index,
});

function Index() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-paper text-ink">
      <SiteNav onOpen={() => setOpen(true)} />
      <main>
        <Hero onOpen={() => setOpen(true)} />
        <SampleCarousel />
        <HowItWorks />
        <PricingStrip onOpen={() => setOpen(true)} />
      </main>
      <SiteFooter />
      <ComicModal open={open} onOpenChange={setOpen} />
    </div>
  );
}
