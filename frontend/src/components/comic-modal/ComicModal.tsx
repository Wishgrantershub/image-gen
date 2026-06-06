import { useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Stepper } from "./Stepper";
import { StepUpload } from "./StepUpload";
import { StepStyle } from "./StepStyle";
import { StepPremise } from "./StepPremise";
import { StepTier } from "./StepTier";
import { StepGenerate } from "./StepGenerate";
import { StepDone } from "./StepDone";
import { initialState, type ComicState } from "./types";

export function ComicModal({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [step, setStep] = useState(1);
  const [state, setState] = useState<ComicState>(initialState);

  const set = (patch: Partial<ComicState>) => setState((s) => ({ ...s, ...patch }));

  const reset = () => {
    setStep(1);
    setState(initialState);
  };

  const close = () => {
    onOpenChange(false);
    setTimeout(reset, 300);
  };

  const onStepFourNext = () => {
    if (!state.tier) return;
    setStep(5);
  };

  const canNext =
    (step === 1 && !!state.photoFile) ||
    (step === 2 && !!state.style) ||
    (step === 3 && state.premise.trim().length >= 4) ||
    (step === 4 && !!state.tier);

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(o) : close())}>
      <DialogContent className="max-w-2xl bg-paper ink-border-thick p-0 gap-0 [&>button]:text-ink">
        <DialogTitle className="sr-only">Make your comic</DialogTitle>

        <div className="px-6 pt-6 pb-4 border-b-[3px] border-ink bg-zap">
          <Stepper step={state.result ? 6 : step} />
        </div>

        <div className="p-6 min-h-[340px]">
          {state.result ? (
            <StepDone result={state.result} onClose={close} />
          ) : (
            <>
              {step === 1 && <StepUpload state={state} set={set} />}
              {step === 2 && <StepStyle state={state} set={set} />}
              {step === 3 && <StepPremise state={state} set={set} />}
              {step === 4 && <StepTier state={state} set={set} />}
              {step === 5 && (
                <StepGenerate
                  state={state}
                  set={set}
                  onDone={() => {
                    /* ComicState.result flips; StepDone renders */
                  }}
                />
              )}
            </>
          )}
        </div>

        {!state.result && step < 5 && (
          <div className="px-6 py-4 border-t-[3px] border-ink bg-paper flex items-center justify-between">
            <Button
              variant="ghost"
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              disabled={step === 1}
              className="font-bold"
            >
              ← Back
            </Button>
            <Button
              onClick={step === 4 ? onStepFourNext : () => setStep((s) => s + 1)}
              disabled={!canNext}
              className="bg-hero text-paper hover:bg-hero ink-border hard-shadow font-heavy px-6"
            >
              {step === 4 ? "Generate →" : "Next →"}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
