import { getSessionToken } from "@/hooks/use-session";

const API_BASE =
  (typeof window !== "undefined" && (window as any).__COMICME_API__) ||
  (import.meta as any).env?.VITE_API_BASE ||
  "http://localhost:8000";

export type StyleId = "manga" | "pixar" | "superhero";
export type TierId = "basic" | "premium" | "deluxe";

export interface ComicStyle {
  id: StyleId;
  name: string;
  tagline: string;
  description: string;
  emoji: string;
  accent_color: string;
  preview_palette: string[];
  default_panel_count: number;
  sample_premises: string[];
}

export interface ComicTier {
  id: TierId;
  name: string;
  panel_count: number;
  panel_layout: string;
  price_inr: number;
  tagline: string;
}

export interface ComicPanel {
  page_number: number;
  caption: string;
  speech: string;
  bubble_kind: string;
  image_url: string;
  image_path?: string | null;
}

export interface ComicResponse {
  id: number;
  share_token: string;
  title: string;
  style_id: string;
  tier_id: string;
  panel_count: number;
  panel_layout: string;
  status: string;
  progress_step: string | null;
  progress_message: string | null;
  progress_pct: number;
  error_message: string | null;
  cover_url: string | null;
  pdf_url: string | null;
  share_url: string | null;
  panels: ComicPanel[];
  is_paid: boolean;
  payment_required: boolean;
  amount_inr: number | null;
}

export interface ComicStatus {
  id: number;
  status: string;
  progress_step: string | null;
  progress_message: string | null;
  progress_pct: number;
  error_message: string | null;
  pdf_url: string | null;
  cover_url: string | null;
  panel_count: number;
  completed_panels: number;
  ready_panel_numbers: number[];
}

export interface PaymentConfig {
  razorpay_configured: boolean;
  razorpay_enabled: boolean;
  key_id: string;
  is_live: boolean;
  demo_bypass_available: boolean;
  currency: string;
}

export interface RazorpaySuccessResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export function loadRazorpayScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof (window as any).Razorpay !== "undefined") {
      resolve();
      return;
    }
    const existing = document.querySelector(
      'script[data-razorpay-checkout]'
    ) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () =>
        reject(new Error("Failed to load Razorpay"))
      );
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.dataset.razorpayCheckout = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Razorpay"));
    document.body.appendChild(script);
  });
}

export interface CreateOrderResponse {
  order_id: string;
  amount_inr: number;
  currency: string;
  tier_id: string;
  key_id: string;
  status: string;
}

export interface DemoBypassResponse {
  verified: boolean;
  tier_id: string;
  amount_inr: number;
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
  key_id: string;
  message: string;
  story_id: number | null;
  is_paid: boolean | null;
}

export interface PaymentVerifyResponse {
  verified: boolean;
  message: string;
  story_id: number | null;
  is_paid: boolean | null;
}

export interface SessionInfo {
  session_token: string;
  is_new: boolean;
}

class HttpError extends Error {
  status: number;
  body: any;
  constructor(status: number, message: string, body: any) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function http<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  const sessionToken = getSessionToken();
  if (sessionToken) headers["X-Session-Token"] = sessionToken;
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      try {
        body = await res.text();
      } catch {
        body = null;
      }
    }
    const detail =
      (body && typeof body === "object" && body.detail) ||
      (typeof body === "string" ? body : res.statusText);
    throw new HttpError(res.status, `${res.status} ${detail}`, body);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return (await res.json()) as T;
  }
  return undefined as unknown as T;
}

async function downloadBlob(path: string, filename: string): Promise<void> {
  const headers: Record<string, string> = {};
  const sessionToken = getSessionToken();
  if (sessionToken) headers["X-Session-Token"] = sessionToken;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {}
    const detail = (body && body.detail) || res.statusText;
    throw new HttpError(res.status, `${res.status} ${detail}`, body);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noreferrer";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export const api = {
  base: API_BASE,
  url: (path: string) => `${API_BASE}${path}`,
  HttpError,

  getStyles: () =>
    http<{ styles: ComicStyle[]; tiers: ComicTier[] }>("/api/comics/styles"),

  getPaymentConfig: () => http<PaymentConfig>("/api/payment/config"),

  startSession: (existingToken?: string) =>
    http<SessionInfo>("/api/session/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_token: existingToken ?? null }),
    }),

  getMySession: () => http<SessionInfo>("/api/session/me"),

  getMyLibrary: () => http<ComicResponse[]>("/api/library/me"),

  deleteLibraryItem: (storyId: number) =>
    http<{ deleted: boolean; id: number }>(`/api/library/${storyId}`, {
      method: "DELETE",
    }),

  getComicById: (storyId: number) =>
    http<ComicResponse>(`/api/comics/${storyId}`),

  createOrder: (tier_id: TierId, style_id?: StyleId, story_id?: number) =>
    http<CreateOrderResponse>("/api/payment/create-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tier_id, style_id, story_id }),
    }),

  verifyPayment: (args: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
    story_id?: number;
  }) =>
    http<PaymentVerifyResponse>("/api/payment/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    }),

  demoBypass: (
    tier_id: TierId,
    style_id?: StyleId,
    story_id?: number
  ) =>
    http<DemoBypassResponse>("/api/payment/demo-bypass", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tier_id, style_id, story_id }),
    }),

  createComicAnonymous: (args: {
    file: File;
    name: string;
    style_id: StyleId;
    tier_id: TierId;
    premise: string;
    payment_verified?: boolean;
    razorpay_payment_id?: string;
    razorpay_order_id?: string;
    razorpay_signature?: string;
  }) => {
    const fd = new FormData();
    fd.append("photo", args.file);
    fd.append("name", args.name);
    fd.append("style_id", args.style_id);
    fd.append("tier_id", args.tier_id);
    fd.append("premise", args.premise);
    if (args.payment_verified) fd.append("payment_verified", "true");
    if (args.razorpay_payment_id)
      fd.append("razorpay_payment_id", args.razorpay_payment_id);
    if (args.razorpay_order_id)
      fd.append("razorpay_order_id", args.razorpay_order_id);
    if (args.razorpay_signature)
      fd.append("razorpay_signature", args.razorpay_signature);
    return http<ComicResponse>("/api/comics/create-anonymous", {
      method: "POST",
      body: fd,
    });
  },

  getComicStatus: (shareToken: string) =>
    http<ComicStatus>(`/api/comics/by-token/${shareToken}/status`),

  getComic: (shareToken: string) =>
    http<ComicResponse>(`/api/comics/by-token/${shareToken}`),

  listSamples: () =>
    http<{ samples: { id: string; pdf_url: string; cover_url: string }[] }>(
      "/api/comics/samples"
    ),

  /**
   * Download a comic PDF using the session-aware endpoint. The browser saves
   * the file via a programmatic anchor click. Throws HttpError on payment
   * gates (402) and other failures.
   */
  downloadPdf: (storyId: number, filename?: string) =>
    downloadBlob(
      `/api/comics/${storyId}/pdf`,
      filename || `comicme_${storyId}.pdf`
    ),
};
