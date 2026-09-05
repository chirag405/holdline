"use client";

import { useEffect, useState } from "react";
import { PhoneCall } from "lucide-react";
import { BorderTrail } from "@/components/ui/border-trail";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  decisionId: string;
  question: string;
  options: string[];
  timeoutS: number;
  openedAt: number;
}

/** The moment the whole product exists for: the agent is holding the line and
 *  needs a human call. Big, unmissable, with a countdown. */
export function DecisionCard({
  decisionId,
  question,
  options,
  timeoutS,
  openedAt,
}: Props) {
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, []);

  const remaining = Math.max(0, timeoutS - (now - openedAt) / 1000);
  const pct = Math.max(0, Math.min(1, remaining / timeoutS));
  const urgent = remaining < timeoutS * 0.33;

  async function answer(opt: string) {
    if (submitting) return;
    setSubmitting(opt);
    try {
      await api.answer(decisionId, opt);
    } catch {
      setSubmitting(null);
    }
  }

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-3xl border bg-card/90 p-6 shadow-2xl backdrop-blur",
        urgent ? "border-red-500/50" : "border-amber-500/50",
      )}
    >
      <BorderTrail
        size={90}
        className={urgent ? "bg-red-400" : "bg-amber-400"}
        transition={{ repeat: Infinity, duration: 4, ease: "linear" }}
      />

      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-300">
        <PhoneCall className="size-4 animate-pulse" />
        Holdline is holding the line — your call
      </div>

      <p className="mt-3 text-lg font-medium text-foreground">{question}</p>

      <div className="mt-5 flex flex-wrap gap-3">
        {options.map((opt, i) => (
          <Button
            key={opt}
            size="lg"
            variant={i === 0 ? "default" : "secondary"}
            disabled={!!submitting}
            onClick={() => answer(opt)}
            className={cn(
              "rounded-xl",
              i === 0 && "bg-emerald-500 text-emerald-950 hover:bg-emerald-400",
            )}
          >
            {submitting === opt ? "Sending…" : opt}
          </Button>
        ))}
      </div>

      <div className="mt-5">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/60">
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-200",
              urgent ? "bg-red-400" : "bg-amber-400",
            )}
            style={{ width: `${pct * 100}%` }}
          />
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">
          {remaining > 0
            ? `Auto-falls back to your safe default in ${Math.ceil(remaining)}s`
            : "Falling back to your safe default…"}
        </p>
      </div>
    </div>
  );
}
