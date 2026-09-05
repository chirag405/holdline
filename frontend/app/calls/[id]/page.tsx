"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, PhoneOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Transcript } from "@/components/Transcript";
import { api, type Call } from "@/lib/api";

export default function CallDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [call, setCall] = useState<Call | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.call(id).then(setCall).catch((e) => setErr(String(e)));
  }, [id]);

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back
      </Link>

      {err && <p className="mt-6 text-sm text-red-300">{err}</p>}
      {!call && !err && <p className="mt-6 text-sm text-muted-foreground">Loading…</p>}

      {call && (
        <div className="mt-4 space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-semibold">
              Call {call.call_id.slice(-6)}
            </h1>
            {call.outcome && (
              <Badge className="capitalize">{call.outcome.replace(/_/g, " ")}</Badge>
            )}
            <span className="text-xs text-muted-foreground">
              {new Date(call.started_at * 1000).toLocaleString()}
            </span>
          </div>

          {call.summary && (
            <Card className="border-border/60 bg-card/70 p-4 backdrop-blur">
              <div className="flex items-start gap-3">
                {call.confirmation_number ? (
                  <CheckCircle2 className="mt-0.5 size-5 text-emerald-400" />
                ) : (
                  <PhoneOff className="mt-0.5 size-5 text-muted-foreground" />
                )}
                <div className="space-y-2">
                  <p className="text-sm">{call.summary.summary}</p>
                  {call.confirmation_number && (
                    <p className="font-mono text-sm text-emerald-300">
                      confirmation {call.confirmation_number}
                    </p>
                  )}
                  {call.summary.follow_up_draft && (
                    <>
                      <Separator className="my-2" />
                      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Follow-up draft
                        {call.summary.follow_up_date
                          ? ` · by ${call.summary.follow_up_date}`
                          : ""}
                      </div>
                      <p className="whitespace-pre-wrap text-sm text-foreground/80">
                        {call.summary.follow_up_draft}
                      </p>
                    </>
                  )}
                </div>
              </div>
            </Card>
          )}

          <Card className="h-[32rem] border-border/60 bg-card/70 p-3 backdrop-blur">
            <Transcript
              turns={call.transcript.map((t) => ({
                role: t.role,
                text: t.text,
                ts: t.ts ?? 0,
              }))}
            />
          </Card>
        </div>
      )}
    </main>
  );
}
