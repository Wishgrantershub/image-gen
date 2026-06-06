import { useEffect, useState } from "react";
import {
  api,
  loadRazorpayScript,
  type RazorpaySuccessResponse,
} from "@/lib/api";
import type { ComicState, TierId } from "./types";
import { TIER_NAME_TO_ID } from "./types";

interface Props {
  state: ComicState;
  set: (p: Partial<ComicState>) => void;
  onDone: () => void;
}

export function StepGenerate({ state, set, onDone }: Props) {
  const [progress, setProgress] = useState(0);
  const [stepMsg, setStepMsg] = useState("Starting...");
  const [readyPanels, setReadyPanels] = useState<number[]>([]);
  const [currentToken, setCurrentToken] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const panelCount =
    state.tier === "Single" ? 6 : state.tier === "Story" ? 12 : state.tier === "Saga" ? 24 : 6;

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    const finish = (result: {
      shareToken: string;
      pdfUrl: string;
      coverUrl: string | null;
    }) => {
      if (cancelled) return;
      set({ result, error: null });
      setTimeout(onDone, 600);
    };

    const fail = (msg: string) => {
      if (cancelled) return;
      setLocalError(msg);
      set({ error: msg });
    };

    const poll = (token: string) => {
      pollTimer = setTimeout(async () => {
        if (cancelled) return;
        try {
          const s = await api.getComicStatus(token);
          if (cancelled) return;

          const pct = Math.max(0, Math.min(100, s.progress_pct || 0));
          setProgress(pct);
          setStepMsg(s.progress_message || s.progress_step || "Working...");

          // Reveal panels as they land
          if (s.ready_panel_numbers?.length) {
            setReadyPanels(s.ready_panel_numbers);
          }

          if (
            s.status === "completed" ||
            s.status === "preview_ready" ||
            pct >= 100 ||
            s.pdf_url
          ) {
            finish({
              shareToken: token,
              pdfUrl: s.pdf_url || api.url(`/api/comics/by-token/${token}/pdf`),
              coverUrl: s.cover_url,
            });
            return;
          }
          if (s.status === "failed") {
            fail(s.error_message || "Generation failed");
            return;
          }
          poll(token);
        } catch (e: any) {
          if (!cancelled) fail(`Lost connection: ${e.message || e}`);
        }
      }, 2500);
    };

    const charge = async (tierId: TierId): Promise<RazorpaySuccessResponse | null> => {
      let cfg;
      try {
        cfg = await api.getPaymentConfig();
      } catch (e: any) {
        fail(`Config fetch failed: ${e.message || e}`);
        return null;
      }
      if (cancelled) return null;

      if (cfg.razorpay_enabled) {
        setStepMsg("Opening secure payment...");
        let order;
        try {
          order = await api.createOrder(tierId, state.style!);
        } catch (e: any) {
          fail(`Order creation failed: ${e.message || e}`);
          return null;
        }
        if (cancelled) return null;
        try {
          await loadRazorpayScript();
        } catch {
          fail("Could not load Razorpay checkout");
          return null;
        }
        if (cancelled) return null;
        return new Promise<RazorpaySuccessResponse>((resolve, reject) => {
          const Rzp = (window as any).Razorpay;
          if (!Rzp) { reject(new Error("Razorpay not available")); return; }
          const rzp = new Rzp({
            key: order.key_id,
            amount: Math.round(order.amount_inr * 100),
            currency: order.currency,
            order_id: order.order_id,
            name: "ComicMe",
            description: `${tierId} tier comic`,
            handler: (resp: RazorpaySuccessResponse) => resolve(resp),
            modal: { ondismiss: () => reject(new Error("Payment cancelled")) },
            theme: { color: "#0F0F0F" },
          });
          rzp.on("payment.failed", (resp: any) =>
            reject(new Error(resp?.error?.description || "Payment failed"))
          );
          rzp.open();
        });
      }

      setStepMsg("Setting up payment...");
      try {
        const bypass = await api.demoBypass(tierId, state.style!);
        return {
          razorpay_payment_id: bypass.razorpay_payment_id,
          razorpay_order_id: bypass.razorpay_order_id,
          razorpay_signature: bypass.razorpay_signature,
        };
      } catch (e: any) {
        fail(`Payment setup failed: ${e.message || e}`);
        return null;
      }
    };

    const start = async () => {
      if (!state.photoFile || !state.style || !state.tier) {
        fail("Missing photo, style, or tier — please go back and complete all steps.");
        return;
      }
      const tierId: TierId = TIER_NAME_TO_ID[state.tier];

      let payment: RazorpaySuccessResponse | null;
      try {
        payment = await charge(tierId);
      } catch (e: any) {
        if (!cancelled) fail(`Payment: ${e.message || e}`);
        return;
      }
      if (!payment || cancelled) return;

      setStepMsg("Uploading your photo...");
      let created;
      try {
        created = await api.createComicAnonymous({
          file: state.photoFile,
          name: state.heroName.trim() || "Hero",
          style_id: state.style,
          tier_id: tierId,
          premise: state.premise.trim(),
          payment_verified: true,
          razorpay_payment_id: payment.razorpay_payment_id,
          razorpay_order_id: payment.razorpay_order_id,
          razorpay_signature: payment.razorpay_signature,
        });
      } catch (e: any) {
        if (!cancelled) fail(`Upload failed: ${e.message || e}`);
        return;
      }
      if (cancelled) return;

      setCurrentToken(created.share_token);
      setStepMsg("Drawing your comic...");
      poll(created.share_token);
    };

    start();

    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [retryKey]);

  const err = localError || state.error;

  const retry = () => {
    setLocalError(null);
    set({ error: null });
    setProgress(0);
    setReadyPanels([]);
    setCurrentToken(null);
    setStepMsg("Starting...");
    setRetryKey((k) => k + 1);
  };

  // Show up to 12 slots in a 3-col grid regardless of panelCount
  const displaySlots = Math.min(panelCount, 12);

  return (
    <div>
      <h3 className="font-heavy text-2xl text-ink mb-1">Inking your comic…</h3>
      <p className="text-ink/70 font-medium mb-4 text-sm">{stepMsg}</p>

      <div className="ink-border-thick bg-paper h-4 overflow-hidden mb-5">
        <div
          className="h-full bg-hero transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>

      {err ? (
        <div className="ink-border-thick bg-hero/10 p-4 text-sm">
          <p className="font-heavy text-hero mb-1">Something went wrong</p>
          <p className="text-ink/80 font-medium break-words">{err}</p>
          <button
            onClick={retry}
            className="mt-3 text-sm font-bold text-hero underline underline-offset-2"
          >
            ↻ Retry
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {Array.from({ length: displaySlots }).map((_, i) => {
            const panelNum = i + 1;
            const isReady = readyPanels.includes(panelNum);
            const imgUrl =
              currentToken
                ? api.url(`/api/comics/by-token/${currentToken}/panels/${panelNum}`)
                : null;
            return (
              <div
                key={i}
                className="aspect-square ink-border-thick overflow-hidden relative bg-paper/50"
              >
                {isReady && imgUrl ? (
                  <img
                    src={imgUrl}
                    alt={`Panel ${panelNum}`}
                    className="w-full h-full object-cover animate-pop-in"
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center gap-1">
                    <div className="font-display text-xl text-ink/20">•</div>
                    <div className="text-[10px] font-bold text-ink/30">{panelNum}</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
