import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { ComicDetailModal } from "@/components/library/ComicDetailModal";
import { ComicModal } from "@/components/comic-modal/ComicModal";
import { api } from "@/lib/api";
import type { ComicResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/library")({
  head: () => ({
    meta: [
      { title: "My Comics — ComicMe" },
      {
        name: "description",
        content: "All the comics you've made, in one place.",
      },
    ],
  }),
  component: LibraryPage,
});

const STYLE_ACCENT: Record<string, string> = {
  manga: "from-zap/40 to-paper",
  pixar: "from-hero/30 to-paper",
  superhero: "from-ink/20 to-paper",
};

const STYLE_LABEL: Record<string, string> = {
  manga: "MANGA",
  pixar: "PIXAR",
  superhero: "SUPERHERO",
};

function statusLabel(c: ComicResponse): string {
  if (c.status === "completed" || c.is_paid) return "Ready";
  if (c.status === "preview_ready") return c.is_paid ? "Ready" : "Preview";
  if (c.status === "generating") return `Drawing… ${c.progress_pct || 0}%`;
  if (c.status === "draft") return c.error_message || "Draft";
  if (c.status === "purchased") return "Unlocked";
  return c.status;
}

function ComicCard({
  comic,
  onOpen,
}: {
  comic: ComicResponse;
  onOpen: (c: ComicResponse) => void;
}) {
  const coverUrl = comic.cover_url
    ? comic.cover_url.startsWith("http")
      ? comic.cover_url
      : api.url(comic.cover_url)
    : null;

  return (
    <button
      onClick={() => onOpen(comic)}
      className="text-left group block ink-border-thick bg-paper hard-shadow hover:hard-shadow-lg hover:-translate-y-0.5 transition-transform overflow-hidden"
    >
      <div
        className={`relative aspect-[3/4] bg-gradient-to-b ${
          STYLE_ACCENT[comic.style_id] || "from-ink/10 to-paper"
        } overflow-hidden`}
      >
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={`${comic.title} cover`}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-ink/30 font-display text-3xl">
            {comic.status === "generating" ? "…" : "NO COVER"}
          </div>
        )}
        {comic.status === "generating" && (
          <div className="absolute bottom-0 left-0 right-0 h-1.5 bg-ink/20">
            <div
              className="h-full bg-hero transition-all duration-300"
              style={{ width: `${comic.progress_pct || 0}%` }}
            />
          </div>
        )}
        {comic.is_paid && (
          <div className="absolute top-2 right-2 bg-ink text-paper text-[9px] font-bold tracking-widest px-1.5 py-0.5">
            UNLOCKED
          </div>
        )}
        {!comic.is_paid && comic.payment_required && (
          <div className="absolute top-2 right-2 bg-hero text-paper text-[9px] font-bold tracking-widest px-1.5 py-0.5">
            ₹{Math.round(comic.amount_inr || 0)}
          </div>
        )}
      </div>
      <div className="p-3 bg-paper">
        <div className="text-[9px] font-bold tracking-widest text-ink/60">
          {STYLE_LABEL[comic.style_id] || comic.style_id.toUpperCase()} ·{" "}
          {comic.panel_count} PANELS
        </div>
        <h3 className="font-heavy text-sm text-ink line-clamp-1 mt-0.5">
          {comic.title || "Untitled"}
        </h3>
        <div className="text-[10px] font-bold text-ink/50 mt-1">
          {statusLabel(comic)}
        </div>
      </div>
    </button>
  );
}

function LibraryPage() {
  const [open, setOpen] = useState(false);
  const [detailComic, setDetailComic] = useState<ComicResponse | null>(null);
  const qc = useQueryClient();

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["library", "me"],
    queryFn: () => api.getMyLibrary(),
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    if (!data) return;
    const hasInProgress = data.some(
      (c) => c.status === "generating" || c.status === "draft"
    );
    if (!hasInProgress) return;
    const t = setInterval(() => {
      qc.invalidateQueries({ queryKey: ["library", "me"] });
    }, 5000);
    return () => clearInterval(t);
  }, [data, qc]);

  const handleOpen = (c: ComicResponse) => setDetailComic(c);
  const handleCloseDetail = () => setDetailComic(null);
  const handleDeleted = (id: number) => {
    qc.setQueryData<ComicResponse[]>(["library", "me"], (prev) =>
      prev ? prev.filter((c) => c.id !== id) : prev
    );
  };
  const handlePaidUpdated = (id: number) => {
    qc.setQueryData<ComicResponse[]>(["library", "me"], (prev) =>
      prev
        ? prev.map((c) =>
            c.id === id
              ? { ...c, is_paid: true, status: "purchased" }
              : c
          )
        : prev
    );
    if (detailComic && detailComic.id === id) {
      setDetailComic({
        ...detailComic,
        is_paid: true,
        status: "purchased",
      });
    }
  };

  return (
    <div className="min-h-screen bg-paper text-ink">
      <SiteNav onOpen={() => setOpen(true)} />
      <main className="mx-auto max-w-7xl px-4 sm:px-6 py-10">
        <div className="flex items-end justify-between mb-8 flex-wrap gap-4">
          <div>
            <div className="text-[10px] font-bold tracking-widest text-ink/60">
              YOUR LIBRARY
            </div>
            <h1 className="font-heavy text-4xl text-ink mt-1">My Comics</h1>
            <p className="text-ink/70 font-medium text-sm mt-1 max-w-md">
              Everything you've made, on this device. Click a cover to see all
              panels, or export the PDF.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => refetch()}
              variant="ghost"
              className="font-bold"
              disabled={isFetching}
            >
              {isFetching ? "Refreshing…" : "↻ Refresh"}
            </Button>
            <Button
              onClick={() => setOpen(true)}
              className="bg-hero text-paper ink-border hard-shadow font-heavy"
            >
              + New Comic
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="ink-border-thick bg-paper p-12 text-center">
            <div className="font-display text-3xl text-ink/50 animate-pulse">
              Loading your comics…
            </div>
          </div>
        ) : error ? (
          <div className="ink-border-thick bg-hero/10 p-6 text-sm">
            <p className="font-heavy text-hero mb-1">Could not load library</p>
            <p className="text-ink/80 font-medium break-words">
              {(error as Error).message}
            </p>
            <p className="text-xs text-ink/60 mt-2">
              If you're seeing this on a new device, your library follows your
              browser session, not your account.
            </p>
          </div>
        ) : !data || data.length === 0 ? (
          <div className="ink-border-thick bg-paper p-12 text-center">
            <div className="font-display text-6xl text-ink/30">∅</div>
            <h2 className="mt-2 font-heavy text-2xl text-ink">
              No comics yet
            </h2>
            <p className="text-ink/70 font-medium text-sm mt-1 max-w-md mx-auto">
              Make your first one — upload a photo, pick a vibe, get a 6-panel
              AI comic in about 60 seconds.
            </p>
            <Button
              onClick={() => setOpen(true)}
              className="mt-5 bg-hero text-paper ink-border hard-shadow font-heavy"
            >
              Make your first comic →
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-5">
            {data.map((c) => (
              <ComicCard key={c.id} comic={c} onOpen={handleOpen} />
            ))}
          </div>
        )}

        <div className="mt-12 ink-border bg-paper p-5 text-xs text-ink/70 font-medium">
          <p className="font-heavy text-ink text-sm mb-1">How this works</p>
          <ul className="list-disc list-inside space-y-1">
            <li>
              Your library is tied to this browser, not an account. If you
              clear cookies, the library on this device resets.
            </li>
            <li>
              Comics in progress (drawing…) refresh every 5 seconds
              automatically.
            </li>
            <li>
              <strong>Free tier:</strong> export PDFs anytime.
            </li>
            <li>
              <strong>Paid tier:</strong> only unlocked comics can be exported.
              Click a card → "Pay ₹X" → Razorpay checkout → export unlocks.
            </li>
          </ul>
        </div>
      </main>
      <SiteFooter />
      <ComicModal open={open} onOpenChange={setOpen} />
      <ComicDetailModal
        comic={detailComic}
        open={!!detailComic}
        onOpenChange={(o) => !o && handleCloseDetail()}
        onDeleted={handleDeleted}
        onPaidUpdated={handlePaidUpdated}
      />
    </div>
  );
}
