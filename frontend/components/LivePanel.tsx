"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, PhoneOff, Radio } from "lucide-react";
import { Card } from "@/components/ui/card";
import { DecisionCard } from "@/components/DecisionCard";
import { HoldTimer } from "@/components/HoldTimer";
import { StatusPill } from "@/components/StatusPill";
import { Transcript } from "@/components/Transcript";
import { useCallStream } from "@/lib/useCallStream";

export function LivePanel() {
  const live = useCallStream();
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const lastCall = useRef<string | null>(null);

  useEffect(() => {
    if (live.callId && live.callId !== lastCall.current) {
      lastCall.current = live.callId;
      setStartedAt(Date.now());
    }
  }, [live.callId]);

  const active = live.status === "on_call" || live.status === "waiting_on_you";
  const idle = live.status === "idle" && !live.ended;

  return (
    <Card className="flex min-h-[30rem] flex-col border-border/60 bg-card/70 p-5 backdrop-blur lg:min-h-[38rem]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Radio className="size-4 text-emerald-400" />
          Live call
        </div>
        <div className="flex items-center gap-3">
          {active && <HoldTimer startedAt={startedAt} running={active} />}
          <StatusPill status={live.status} />
        </div>
      </div>

      {live.provider && (
        <p className="mt-1 text-xs text-muted-foreground">
          {live.objective ? `${live.objective} · ` : ""}
          <span className="text-foreground/70">{live.provider}</span>
        </p>
      )}

      {live.decision && (
        <div className="mt-4">
          <DecisionCard
            decisionId={live.decision.decision_id}
            question={live.decision.question}
            options={live.decision.options}
            timeoutS={live.decision.timeout_s}
            openedAt={live.decision.openedAt}
          />
        </div>
      )}

      {live.lastResolved && !live.decision && live.status !== "ended" && (
        <p className="mt-3 rounded-lg bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
          You said “{live.lastResolved.answer}” — Holdline is back on the line.
        </p>
      )}

      <div className="mt-4 min-h-0 flex-1 overflow-hidden rounded-xl border border-border/50 bg-background/40">
        {idle ? (
          <div className="grid h-full place-items-center px-6 text-center text-sm text-muted-foreground">
            No call in progress. Plan one on the left — the transcript, the hold
            timer, and any decision Holdline needs from you show up here in real time.
          </div>
        ) : (
          <div className="h-full p-3">
            <Transcript turns={live.transcript} />
          </div>
        )}
      </div>

      {live.ended && (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-border/60 bg-background/50 p-3 text-sm">
          {live.ended.outcome === "cancelled" || live.ended.confirmation_number ? (
            <CheckCircle2 className="size-5 text-emerald-400" />
          ) : (
            <PhoneOff className="size-5 text-muted-foreground" />
          )}
          <div>
            <div className="font-medium capitalize">
              {live.ended.outcome.replace(/_/g, " ")}
            </div>
            {live.ended.confirmation_number && (
              <div className="font-mono text-xs text-emerald-300">
                confirmation {live.ended.confirmation_number}
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
