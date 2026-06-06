import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import type { ComicState } from "./types";

export function StepUpload({ state, set }: { state: ComicState; set: (p: Partial<ComicState>) => void }) {
  const onDrop = useCallback(
    (files: File[]) => {
      const f = files[0];
      if (!f) return;
      const url = URL.createObjectURL(f);
      set({ photo: url, photoName: f.name, photoFile: f, error: null });
    },
    [set]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [] },
    multiple: false,
  });

  return (
    <div>
      <h3 className="font-heavy text-2xl text-ink mb-1">Drop your photo.</h3>
      <p className="text-ink/70 font-medium mb-5 text-sm">Front-facing portraits work best. JPG or PNG.</p>

      {state.photo ? (
        <div className="flex gap-4 items-center">
          <img src={state.photo} alt="Upload preview" className="w-32 h-32 object-cover ink-border-thick" />
          <div className="flex-1 min-w-0">
            <p className="font-bold text-ink truncate">{state.photoName}</p>
            <button
              onClick={() => set({ photo: null, photoName: null, photoFile: null })}
              className="mt-2 text-sm font-bold text-hero underline underline-offset-2"
            >
              Replace photo
            </button>
          </div>
        </div>
      ) : (
        <div
          {...getRootProps()}
          className={`ink-border-thick p-12 text-center cursor-pointer transition-colors ${isDragActive ? "bg-zap" : "bg-paper hover:bg-zap/30"}`}
        >
          <input {...getInputProps()} />
          <div className="font-display text-5xl text-hero mb-2">+</div>
          <p className="font-heavy text-ink text-lg">{isDragActive ? "Drop it!" : "Drag & drop a photo"}</p>
          <p className="text-sm font-medium text-ink/60 mt-1">or click to browse</p>
        </div>
      )}

      <div className="mt-5">
        <label className="font-heavy text-ink block mb-1">Hero's name</label>
        <input
          type="text"
          value={state.heroName}
          onChange={(e) => set({ heroName: e.target.value })}
          placeholder="e.g. Aarav"
          maxLength={32}
          className="w-full ink-border-thick bg-paper font-medium text-base px-3 py-2 focus-visible:ring-hero focus:outline-none"
        />
        <p className="text-xs font-bold text-ink/60 mt-1">We'll print this on the cover.</p>
      </div>
    </div>
  );
}
