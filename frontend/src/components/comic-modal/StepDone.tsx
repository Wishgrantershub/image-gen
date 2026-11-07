import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ComicResult } from "./types";

export function StepDone({
  result,
  email,
  onClose,
}: {
  result: ComicResult;
  email?: string;
  onClose: () => void;
}) {
  const link = `${window.location.origin}/c/${result.shareToken}`;
  const [copied, setCopied] = useState(false);
  const hasEmail = !!email?.trim();

  const copy = async () => {
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="text-center py-2">
      <div className="font-display text-6xl text-hero animate-pop-in">
        {hasEmail ? "ON IT!" : "DONE!"}
      </div>
      <h3 className="mt-2 font-heavy text-2xl text-ink">
        {hasEmail ? "We're drawing your comic." : "Your comic is ready."}
      </h3>
      <p className="text-ink/70 font-medium text-sm mt-1">
        {hasEmail ? (
          <>
            Your comic will arrive at <span className="font-bold text-ink">{email}</span> in about 2-4 minutes.
            You can also track it in your library below.
          </>
        ) : (
          "Download the PDF or share the link."
        )}
      </p>

      {result.coverUrl && (
        <div className="mt-4 flex justify-center">
          <img
            src={api.url(result.coverUrl)}
            alt="Comic cover"
            className="max-h-48 ink-border-thick hard-shadow"
          />
        </div>
      )}

      {hasEmail && (
        <div className="mt-4 ink-border bg-paper p-3.5 rounded-lg text-left">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-hero/20 flex items-center justify-center text-hero font-bold text-base">
              ✉
            </div>
            <div className="flex-1">
              <div className="font-bold text-ink text-sm">Delivery to your inbox active</div>
              <div className="text-ink/60 text-xs font-mono">{email}</div>
            </div>
          </div>
        </div>
      )}

      <div className="mt-5 grid gap-2.5">
        <Button asChild className="bg-hero text-paper hover:bg-hero ink-border hard-shadow font-heavy py-5">
          <a href={link} target="_blank" rel="noreferrer">
            View Comic in New Tab →
          </a>
        </Button>
        <div className="flex gap-2">
          <input value={link} readOnly className="flex-1 ink-border bg-paper px-3 py-2 font-mono text-sm text-ink" />
          <Button onClick={copy} variant="secondary" className="ink-border font-bold">
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
        <Button variant="ghost" onClick={onClose} className="font-bold">
          Close & Return to Home
        </Button>
      </div>
    </div>
  );
}
