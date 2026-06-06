import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ComicResponse, StyleId, TierId } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  comic: ComicResponse | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onDeleted?: (id: number) => void;
  onPaidUpdated?: (id: number) => void;
}

type Action =
  | { kind: "idle" }
  | { kind: "paying" }
  | { kind: "downloading" }
  | { kind: "deleting" }
  | { kind: "error"; message: string };

const STYLE_LABEL: Record<string, string> = {
  manga: "MANGA",
  pixar: "PIXAR",
  superhero: "SUPERHERO",
};

function formatPrice(amount: number | null | undefined): string {
  if (amount == null) return "₹--";
  return `₹${Math.round(amount)}`;
}

export function ComicDetailModal({
  comic,
  open,
  onOpenChange,
  onDeleted,
  onPaidUpdated,
}: Props) {
  const [action, setAction] = useState<Action>({ kind: "idle" });
  const [paymentConfig, setPaymentConfig] = useState<{
    razorpay_enabled: boolean;
  } | null>(null);
  const [confirmedPayment, setConfirmedPayment] = useState<{
    razorpay_payment_id: string;
    razorpay_order_id: string;
    razorpay_signature: string;
  } | null>(null);

  useEffect(() => {
    if (!open) return;
    setAction({ kind: "idle" });
    api
      .getPaymentConfig()
      .then((c) => setPaymentConfig({ razorpay_enabled: c.razorpay_enabled }))
      .catch(() => setPaymentConfig({ razorpay_enabled: false }));
  }, [open, comic?.id]);

  if (!comic) return null;

  const coverUrl = comic.cover_url
    ? comic.cover_url.startsWith("http")
      ? comic.cover_url
      : api.url(comic.cover_url)
    : null;

  const handleDownload = async () => {
    setAction({ kind: "downloading" });
    try {
      await api.downloadPdf(comic.id, `comicme_${comic.share_token || comic.id}.pdf`);
      setAction({ kind: "idle" });
    } catch (e: any) {
      setAction({ kind: "error", message: e?.message || "Download failed" });
    }
  };

  const handlePay = async () => {
    setAction({ kind: "paying" });
    try {
      const cfg = await api.getPaymentConfig();
      if (cfg.razorpay_enabled) {
        const order = await api.createOrder(
          comic.tier_id as TierId,
          comic.style_id as StyleId,
          comic.id
        );
        await new Promise<void>((resolve, reject) => {
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
            handler: (resp: {
              razorpay_payment_id: string;
              razorpay_order_id: string;
              razorpay_signature: string;
            }) => {
              setConfirmedPayment(resp);
              resolve();
            },
            modal: { ondismiss: () => reject(new Error("Payment cancelled")) },
            theme: { color: "#0F0F0F" },
          });
          rzp.on("payment.failed", (resp: any) =>
            reject(new Error(resp?.error?.description || "Payment failed"))
          );
          rzp.open();
        });
        const verify = await api.verifyPayment({
          ...confirmedPayment!,
          story_id: comic.id,
        });
        if (verify.verified && verify.is_paid) {
          onPaidUpdated?.(comic.id);
          setAction({ kind: "idle" });
        } else {
          setAction({
            kind: "error",
            message: verify.message || "Verification failed",
          });
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
          onPaidUpdated?.(comic.id);
          setAction({ kind: "idle" });
        } else {
          setAction({
            kind: "error",
            message: verify.message || "Verification failed",
          });
        }
      }
    } catch (e: any) {
      setAction({ kind: "error", message: e?.message || "Payment failed" });
    }
  };

  const handleDelete = async () => {
    if (!confirm("Delete this comic from your library? This cannot be undone."))
      return;
    setAction({ kind: "deleting" });
    try {
      await api.deleteLibraryItem(comic.id);
      onDeleted?.(comic.id);
      onOpenChange(false);
    } catch (e: any) {
      setAction({ kind: "error", message: e?.message || "Delete failed" });
    }
  };

  const isBusy =
    action.kind === "paying" ||
    action.kind === "downloading" ||
    action.kind === "deleting";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl bg-paper ink-border-thick p-0 gap-0 max-h-[90vh] overflow-y-auto [&>button]:text-ink">
        <DialogTitle className="sr-only">{comic.title}</DialogTitle>

        <div className="px-6 pt-6 pb-4 border-b-[3px] border-ink bg-zap flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold tracking-widest text-ink/60">
              {STYLE_LABEL[comic.style_id] || comic.style_id.toUpperCase()} ·{" "}
              {comic.tier_id.toUpperCase()} · {comic.panel_count} PANELS
            </div>
            <h2 className="font-heavy text-2xl text-ink mt-0.5">{comic.title}</h2>
          </div>
          <div className="flex items-center gap-2">
            {comic.is_paid ? (
              <span className="text-[10px] font-bold tracking-widest bg-ink text-paper px-2 py-1 ink-border">
                UNLOCKED
              </span>
            ) : comic.payment_required ? (
              <span className="text-[10px] font-bold tracking-widest bg-hero text-paper px-2 py-1 ink-border">
                PAY TO UNLOCK
              </span>
            ) : (
              <span className="text-[10px] font-bold tracking-widest bg-paper text-ink px-2 py-1 ink-border">
                FREE
              </span>
            )}
          </div>
        </div>

        <div className="p-6 grid gap-6 md:grid-cols-[280px_1fr]">
          <div>
            <div className="aspect-[3/4] ink-border-thick hard-shadow overflow-hidden bg-paper">
              {coverUrl ? (
                <img
                  src={coverUrl}
                  alt={`${comic.title} cover`}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-ink/40 font-display text-2xl">
                  NO COVER
                </div>
              )}
            </div>

            <div className="mt-4 flex flex-col gap-2">
              {comic.is_paid ? (
                <Button
                  onClick={handleDownload}
                  disabled={isBusy}
                  className="bg-ink text-paper ink-border hard-shadow font-heavy"
                >
                  {action.kind === "downloading"
                    ? "Downloading…"
                    : "↓ Export PDF"}
                </Button>
              ) : comic.payment_required ? (
                <Button
                  onClick={handlePay}
                  disabled={isBusy}
                  className="bg-hero text-paper hover:bg-hero ink-border hard-shadow font-heavy"
                >
                  {action.kind === "paying"
                    ? "Processing…"
                    : `Pay ${formatPrice(comic.amount_inr)} to unlock`}
                </Button>
              ) : (
                <Button
                  onClick={handleDownload}
                  disabled={isBusy}
                  className="bg-ink text-paper ink-border hard-shadow font-heavy"
                >
                  {action.kind === "downloading"
                    ? "Downloading…"
                    : "↓ Export PDF"}
                </Button>
              )}

              {paymentConfig?.razorpay_enabled && comic.is_paid && (
                <p className="text-[10px] text-ink/60 text-center font-bold">
                  PAYMENT VERIFIED · DOWNLOADS UNLOCKED
                </p>
              )}

              {!paymentConfig?.razorpay_enabled && (
                <p className="text-[10px] text-ink/60 text-center font-bold">
                  FREE TIER · ALL DOWNLOADS OPEN
                </p>
              )}

              <Button
                onClick={handleDelete}
                disabled={isBusy}
                variant="ghost"
                className="text-ink/60 hover:text-hero font-bold text-xs"
              >
                {action.kind === "deleting" ? "Deleting…" : "Delete from library"}
              </Button>

              {action.kind === "error" && (
                <p className="text-xs text-hero font-bold break-words">
                  {action.message}
                </p>
              )}
            </div>
          </div>

          <div>
            <div className="font-heavy text-sm text-ink/70 mb-2 tracking-widest">
              ALL PANELS
            </div>
            {comic.panels && comic.panels.length > 0 ? (
              <div
                className={cn(
                  "grid gap-2",
                  comic.panel_count <= 6
                    ? "grid-cols-2 sm:grid-cols-3"
                    : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4"
                )}
              >
                {comic.panels.map((p) => (
                  <div
                    key={p.page_number}
                    className="ink-border overflow-hidden bg-paper relative group"
                  >
                    <div className="aspect-[4/3] bg-paper">
                      <img
                        src={api.url(p.image_url)}
                        alt={`Panel ${p.page_number}`}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    </div>
                    <div className="absolute top-1 left-1 bg-ink text-paper text-[10px] font-bold w-5 h-5 flex items-center justify-center rounded-full">
                      {p.page_number}
                    </div>
                    {p.speech && (
                      <div className="absolute bottom-0 left-0 right-0 bg-paper/95 px-2 py-1 text-[10px] font-medium text-ink border-t-2 border-ink line-clamp-2">
                        {p.speech}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="ink-border p-8 text-center text-ink/50 font-medium">
                Panels are still rendering. Close and reopen in a moment.
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
