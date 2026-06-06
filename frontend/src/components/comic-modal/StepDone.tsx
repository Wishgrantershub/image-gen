import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ComicResult } from "./types";

export function StepDone({
  result,
  onClose,
}: {
  result: ComicResult;
  onClose: () => void;
}) {
  const link = `${window.location.origin}/c/${result.shareToken}`;
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="text-center py-2">
      <div className="font-display text-6xl text-hero animate-pop-in">DONE!</div>
      <h3 className="mt-2 font-heavy text-2xl text-ink">Your comic is ready.</h3>
      <p className="text-ink/70 font-medium text-sm mt-1">Download the PDF or share the link.</p>

      {result.coverUrl && (
        <div className="mt-5 flex justify-center">
          <img
            src={api.url(result.coverUrl)}
            alt="Comic cover"
            className="max-h-48 ink-border-thick hard-shadow"
          />
        </div>
      )}

      <div className="mt-5 grid gap-3">
        <Button asChild className="bg-ink text-paper ink-border hard-shadow font-heavy py-6">
          <a href={api.url(result.pdfUrl)} download target="_blank" rel="noreferrer">
            ↓ Download PDF
          </a>
        </Button>
        <div className="flex gap-2">
          <input value={link} readOnly className="flex-1 ink-border bg-paper px-3 py-2 font-mono text-sm text-ink" />
          <Button onClick={copy} variant="secondary" className="ink-border font-bold">
            {copied ? "Copied!" : "Copy"}
          </Button>
        </div>
        <Button variant="ghost" onClick={onClose} className="font-bold">
          Make another →
        </Button>
      </div>
    </div>
  );
}
