import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState, useCallback } from "react";
import { api, loadRazorpayScript, type ComicResponse, type TierId, type StyleId } from "@/lib/api";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { BookOpen, LayoutGrid, Maximize2, ChevronLeft, ChevronRight, X } from "lucide-react";

export const Route = createFileRoute("/c/$token")({
  head: () => ({
    meta: [
      { title: "ComicMe — Shared Comic" },
      { name: "description", content: "View this AI-generated comic from ComicMe." },
    ],
  }),
  component: ShareComicPage,
});

function panelGridClass(layout: string): string {
  switch (layout) {
    case "3x4":
      return "grid-cols-1 sm:grid-cols-2 md:grid-cols-3";
    case "4x6":
      return "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4";
    default:
      return "grid-cols-1 sm:grid-cols-2 md:grid-cols-3";
  }
}

function ShareComicPage() {
  const { token } = Route.useParams();
  const [comic, setComic] = useState<ComicResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "stream">("grid");
  const [activeLightboxIndex, setActiveLightboxIndex] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let pollInterval: ReturnType<typeof setInterval> | null = null;

    const fetchComic = async (showLoading = false) => {
      if (showLoading) setLoading(true);
      try {
        const c = await api.getComic(token);
        if (cancelled) return;
        setComic(c);
        setLoading(false);

        // If generating, auto-poll every 3s
        const isGenerating = c.status === "generating" || (c.progress_pct < 100 && !c.pdf_url);
        if (isGenerating && !pollInterval) {
          pollInterval = setInterval(async () => {
            if (cancelled) return;
            try {
              const updated = await api.getComic(token);
              if (cancelled) return;
              setComic(updated);
              const stillGen = updated.status === "generating" || (updated.progress_pct < 100 && !updated.pdf_url);
              if (!stillGen && pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
              }
            } catch {
              // ignore transient poll error
            }
          }, 3000);
        }
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || "Comic not found");
        setLoading(false);
      }
    };

    fetchComic(true);

    return () => {
      cancelled = true;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [token]);

  // Handle keyboard events for lightbox navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (activeLightboxIndex === null || !comic?.panels) return;
      if (e.key === "Escape") {
        setActiveLightboxIndex(null);
      } else if (e.key === "ArrowLeft") {
        setActiveLightboxIndex((prev) => (prev !== null && prev > 0 ? prev - 1 : prev));
      } else if (e.key === "ArrowRight") {
        setActiveLightboxIndex((prev) =>
          prev !== null && prev < comic.panels.length - 1 ? prev + 1 : prev
        );
      }
    },
    [activeLightboxIndex, comic?.panels]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const handleUnlock = async () => {
    if (!comic) return;
    setPaying(true);
    try {
      const cfg = await api.getPaymentConfig();
      if (cfg.razorpay_enabled) {
        const order = await api.createOrder(
          comic.tier_id as TierId,
          comic.style_id as StyleId,
          comic.id
        );
        await loadRazorpayScript();
        const paymentResp = await new Promise<{
          razorpay_payment_id: string;
          razorpay_order_id: string;
          razorpay_signature: string;
        }>((resolve, reject) => {
          const Rzp = (window as any).Razorpay;
          if (!Rzp) {
            reject(new Error("Razorpay not available"));
            return;
          }
          const rzp = new Rzp({
            key: order.key_id,
            amount: Math.round(order.amount_inr * 100),
            currency: order.currency,
            order_id: order.order_id,
            name: "ComicMe",
            description: `Unlock ${comic.title}`,
            handler: (resp: any) => resolve(resp),
            modal: { ondismiss: () => reject(new Error("Payment cancelled")) },
            theme: { color: "#0F0F0F" },
          });
          rzp.on("payment.failed", (resp: any) =>
            reject(new Error(resp?.error?.description || "Payment failed"))
          );
          rzp.open();
        });

        const verify = await api.verifyPayment({
          ...paymentResp,
          story_id: comic.id,
        });
        if (verify.verified && verify.is_paid) {
          setComic((prev) => (prev ? { ...prev, is_paid: true, status: "purchased" } : prev));
        }
      } else {
        const bypass = await api.demoBypass(
          comic.tier_id as TierId,
          comic.style_id as StyleId,
          comic.id
        );
        const verify = await api.verifyPayment({
          razorpay_payment_id: bypass.razorpay_payment_id,
          razorpay_order_id: bypass.razorpay_order_id,
          razorpay_signature: bypass.razorpay_signature,
          story_id: comic.id,
        });
        if (verify.verified && verify.is_paid) {
          setComic((prev) => (prev ? { ...prev, is_paid: true, status: "purchased" } : prev));
        }
      }
    } catch (e: any) {
      alert(e?.message || "Payment could not be processed");
    } finally {
      setPaying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-paper text-ink flex flex-col">
        <SiteNav />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="text-2xl font-bold animate-pulse">Loading comic…</div>
          </div>
        </div>
        <SiteFooter />
      </div>
    );
  }

  if (error || !comic) {
    return (
      <div className="min-h-screen bg-paper text-ink flex flex-col">
        <SiteNav />
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-md text-center">
            <h1 className="text-5xl font-bold">404</h1>
            <p className="mt-4 text-ink/60">{error || "Comic not found."}</p>
            <Link to="/">
              <Button className="mt-6">Go home</Button>
            </Link>
          </div>
        </div>
        <SiteFooter />
      </div>
    );
  }

  const isGenerating =
    comic.status === "generating" || (comic.progress_pct < 100 && !comic.pdf_url);
  const canDownload = comic.pdf_url && (comic.is_paid || !comic.payment_required);

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col">
      <SiteNav />
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8">
        <h1 className="text-3xl sm:text-4xl font-display font-bold text-center mb-1">
          {comic.title}
        </h1>
        <p className="text-center text-ink/50 text-sm mb-6">
          {comic.panel_count} panels · {comic.panel_layout} layout
        </p>

        {isGenerating && (
          <div className="text-center mb-6 p-4 ink-border rounded-lg bg-paper">
            <div className="font-bold text-lg">{comic.progress_message || "Generating…"}</div>
            <div className="mt-2 h-2 bg-ink/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-hero transition-all duration-500"
                style={{ width: `${comic.progress_pct}%` }}
              />
            </div>
            <div className="mt-1 text-xs text-ink/40">{comic.progress_pct}%</div>
          </div>
        )}

        {comic.cover_url && (
          <div className="mb-8 flex justify-center">
            <div className="ink-border rounded-lg overflow-hidden bg-paper max-w-sm w-full shadow-md">
              <img
                src={api.url(comic.cover_url)}
                alt={comic.title}
                className="w-full object-contain"
              />
            </div>
          </div>
        )}

        {comic.panels && comic.panels.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <div className="font-heavy text-sm text-ink/70 tracking-widest flex items-center gap-2">
                <span>STORY PANELS</span>
                <span className="text-xs bg-ink/10 px-2 py-0.5 rounded-full font-mono font-normal">
                  {comic.panels.length}
                </span>
              </div>
              <div className="inline-flex rounded-lg ink-border p-0.5 bg-paper/60 backdrop-blur-xs text-xs">
                <button
                  type="button"
                  onClick={() => setViewMode("grid")}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
                    viewMode === "grid"
                      ? "bg-ink text-paper shadow-xs"
                      : "text-ink/70 hover:text-ink"
                  }`}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span>Grid Overview</span>
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("stream")}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded font-medium transition-colors ${
                    viewMode === "stream"
                      ? "bg-ink text-paper shadow-xs"
                      : "text-ink/70 hover:text-ink"
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>Reading Stream</span>
                </button>
              </div>
            </div>

            {viewMode === "grid" ? (
              <div className={`grid gap-3 items-start ${panelGridClass(comic.panel_layout)}`}>
                {comic.panels.map((p, idx) => (
                  <div
                    key={p.page_number}
                    onClick={() => setActiveLightboxIndex(idx)}
                    className="self-start ink-border rounded-lg overflow-hidden bg-paper shadow-xs hover:shadow-md transition-all cursor-pointer group relative"
                  >
                    <img
                      src={api.url(p.image_url)}
                      alt={`Panel ${p.page_number}`}
                      className="w-full h-auto block object-contain"
                      loading="lazy"
                    />
                    <div className="absolute top-2 left-2 bg-ink/90 text-paper text-xs font-bold w-6 h-6 flex items-center justify-center rounded-full shadow-xs">
                      {p.page_number}
                    </div>
                    <div className="absolute inset-0 bg-ink/0 group-hover:bg-ink/10 transition-colors flex items-center justify-center">
                      <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-ink/80 text-paper p-1.5 rounded-full shadow-md">
                        <Maximize2 className="w-4 h-4" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="max-w-2xl mx-auto space-y-6">
                {comic.panels.map((p, idx) => (
                  <div
                    key={p.page_number}
                    onClick={() => setActiveLightboxIndex(idx)}
                    className="ink-border rounded-xl overflow-hidden bg-paper shadow-md cursor-pointer hover:shadow-lg transition-all relative group"
                  >
                    <div className="relative">
                      <img
                        src={api.url(p.image_url)}
                        alt={`Panel ${p.page_number}`}
                        className="w-full h-auto block object-contain"
                        loading="lazy"
                      />
                      <div className="absolute top-3 left-3 bg-ink/90 text-paper text-xs font-bold px-2.5 py-1 rounded-full shadow-md flex items-center gap-1.5">
                        <span>PANEL {p.page_number}</span>
                      </div>
                      <div className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity bg-ink/80 text-paper text-xs px-2.5 py-1 rounded-full flex items-center gap-1 shadow-md">
                        <Maximize2 className="w-3.5 h-3.5" />
                        <span>Tap to zoom</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Lightbox Modal */}
        {activeLightboxIndex !== null && comic.panels && comic.panels[activeLightboxIndex] && (
          <div
            className="fixed inset-0 z-50 bg-ink/90 backdrop-blur-sm flex flex-col items-center justify-center p-4"
            onClick={() => setActiveLightboxIndex(null)}
          >
            <div
              className="relative max-w-4xl max-h-[90vh] flex flex-col items-center"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-full flex items-center justify-between text-paper pb-2 px-1">
                <span className="font-heavy text-sm tracking-wider">
                  PANEL {comic.panels[activeLightboxIndex].page_number} OF {comic.panels.length}
                </span>
                <button
                  type="button"
                  onClick={() => setActiveLightboxIndex(null)}
                  className="p-1 rounded-full bg-paper/10 hover:bg-paper/20 text-paper transition-colors"
                  aria-label="Close lightbox"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="relative ink-border rounded-xl overflow-hidden bg-black max-h-[80vh] flex items-center justify-center">
                <img
                  src={api.url(comic.panels[activeLightboxIndex].image_url)}
                  alt={`Panel ${comic.panels[activeLightboxIndex].page_number}`}
                  className="max-h-[80vh] max-w-full object-contain"
                />

                {activeLightboxIndex > 0 && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveLightboxIndex((prev) => (prev !== null ? prev - 1 : 0));
                    }}
                    className="absolute left-2 top-1/2 -translate-y-1/2 bg-ink/80 hover:bg-ink text-paper p-2 rounded-full shadow-md transition-all"
                    aria-label="Previous panel"
                  >
                    <ChevronLeft className="w-6 h-6" />
                  </button>
                )}

                {activeLightboxIndex < comic.panels.length - 1 && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveLightboxIndex((prev) => (prev !== null ? prev + 1 : 0));
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 bg-ink/80 hover:bg-ink text-paper p-2 rounded-full shadow-md transition-all"
                    aria-label="Next panel"
                  >
                    <ChevronRight className="w-6 h-6" />
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-3 justify-center items-center">
          {canDownload && comic.pdf_url && (
            <a href={api.url(comic.pdf_url)} download>
              <Button size="lg" className="bg-ink text-paper ink-border hard-shadow font-heavy">
                ↓ Download High-Res PDF
              </Button>
            </a>
          )}
          {comic.payment_required && !comic.is_paid && (
            <div className="flex flex-col sm:flex-row items-center gap-3 p-4 ink-border rounded-lg bg-zap/20">
              <div className="text-center sm:text-left">
                <div className="font-heavy text-base text-ink">Preview Ready! Unlock High-Res PDF</div>
                <p className="text-xs text-ink/70">
                  Instant print-ready PDF without watermarks for ₹{comic.amount_inr || 99}.
                </p>
              </div>
              <Button
                size="lg"
                onClick={handleUnlock}
                disabled={paying}
                className="bg-hero text-paper hover:bg-hero ink-border hard-shadow font-heavy"
              >
                {paying ? "Opening Checkout…" : `Unlock & Download (₹${comic.amount_inr || 99})`}
              </Button>
            </div>
          )}
          <Link to="/">
            <Button variant="outline" size="lg">
              Make your own comic
            </Button>
          </Link>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
