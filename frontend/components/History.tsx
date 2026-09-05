"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, PhoneCall } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api, type Call } from "@/lib/api";
import { useCallStream } from "@/lib/useCallStream";

const OUTCOME_TONE: Record<string, string> = {
  cancelled: "bg-emerald-500/15 text-emerald-300",
  resolved: "bg-emerald-500/15 text-emerald-300",
  refused: "bg-amber-500/15 text-amber-300",
  needs_human: "bg-amber-500/15 text-amber-300",
  failed: "bg-red-500/15 text-red-300",
};

export function History() {
  const [calls, setCalls] = useState<Call[]>([]);
  const live = useCallStream();

  useEffect(() => {
    const load = () => api.calls().then((r) => setCalls(r.calls)).catch(() => {});
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [live.ended, live.callId]);

  if (calls.length === 0) {
    return (
      <Card className="border-border/60 bg-card/70 p-8 text-center text-sm text-muted-foreground backdrop-blur">
        No calls yet. Once Holdline makes one, it lands here with the full
        transcript, outcome, and confirmation number.
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {calls.map((c) => (
        <Link key={c.call_id} href={`/calls/${c.call_id}`}>
          <Card className="group flex items-center gap-4 border-border/60 bg-card/70 p-4 backdrop-blur transition hover:border-emerald-500/40 hover:bg-card">
            <div className="grid size-9 shrink-0 place-items-center rounded-full border border-border/60 bg-background/60 text-muted-foreground">
              <PhoneCall className="size-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">
                {c.summary?.summary ?? `Call ${c.call_id.slice(-6)}`}
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                <span>{new Date(c.started_at * 1000).toLocaleString()}</span>
                {c.confirmation_number && (
                  <span className="font-mono text-emerald-300">
                    {c.confirmation_number}
                  </span>
                )}
              </div>
            </div>
            {c.outcome && (
              <Badge
                className={
                  OUTCOME_TONE[c.outcome] ?? "bg-muted text-muted-foreground"
                }
              >
                {c.outcome.replace(/_/g, " ")}
              </Badge>
            )}
            <ChevronRight className="size-4 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-foreground" />
          </Card>
        </Link>
      ))}
    </div>
  );
}
