"use client";

import { useEffect, useState } from "react";
import { Loader2, Phone, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, type AppConfig, type CallBrief } from "@/lib/api";

const SAMPLE =
  "Cancel my Iron Peak Fitness gym membership, effective at the end of the billing period. Get a cancellation confirmation number. Don't accept a pause, downgrade, or discount to stay.";

export function NewCall() {
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [request, setRequest] = useState(SAMPLE);
  const [account, setAccount] = useState("IPF-99123");
  const [to, setTo] = useState("");
  const [brief, setBrief] = useState<(CallBrief & { task_id: string }) | null>(null);
  const [busy, setBusy] = useState<"" | "planning" | "calling">("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .config()
      .then((c) => {
        setCfg(c);
        if (c.practice_ivr_number) setTo(c.practice_ivr_number);
      })
      .catch(() => {});
  }, []);

  async function plan() {
    setBusy("planning");
    setError(null);
    try {
      const r = await api.plan(request, account ? { account_number: account } : {});
      setBrief({ ...r.brief, task_id: r.task_id });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }

  async function call() {
    if (!brief) return;
    setBusy("calling");
    setError(null);
    try {
      await api.placeCall({ to, task_id: brief.task_id });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }

  return (
    <Card className="border-border/60 bg-card/70 p-5 backdrop-blur">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="size-4 text-emerald-400" />
        Hand Holdline a call to make
      </div>

      <div className="space-y-3">
        <div>
          <Label className="text-xs text-muted-foreground">What do you need done?</Label>
          <Textarea
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            rows={4}
            className="mt-1 resize-none bg-background/60"
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label className="text-xs text-muted-foreground">Account # (optional)</Label>
            <Input
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              className="mt-1 bg-background/60 font-mono"
            />
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">Number to call</Label>
            <Input
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="+1…"
              className="mt-1 bg-background/60 font-mono"
            />
          </div>
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </p>
      )}

      {!brief ? (
        <Button
          onClick={plan}
          disabled={busy === "planning" || !request.trim()}
          className="mt-4 w-full"
        >
          {busy === "planning" ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Planning…
            </>
          ) : (
            "Plan the call"
          )}
        </Button>
      ) : (
        <div className="mt-4 space-y-3">
          <BriefView brief={brief} />
          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => setBrief(null)}
              disabled={busy === "calling"}
            >
              Edit
            </Button>
            <Button
              className="flex-1 bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
              onClick={call}
              disabled={busy === "calling" || !to}
            >
              {busy === "calling" ? (
                <>
                  <Loader2 className="size-4 animate-spin" /> Dialing…
                </>
              ) : (
                <>
                  <Phone className="size-4" /> Place the call
                </>
              )}
            </Button>
          </div>
          {cfg && !cfg.has_twilio && (
            <p className="text-xs text-amber-300/80">
              Twilio isn&apos;t configured on the backend — planning works, the call
              won&apos;t place.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function BriefView({ brief }: { brief: CallBrief }) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/50 p-3 text-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Call brief
      </div>
      <p className="mt-1 font-medium">{brief.objective}</p>
      <p className="text-xs text-muted-foreground">to {brief.provider_name}</p>
      {brief.boundaries.must_escalate.length > 0 && (
        <div className="mt-2">
          <div className="text-xs text-amber-300">Will ask you before agreeing to:</div>
          <ul className="mt-0.5 list-disc pl-4 text-xs text-muted-foreground">
            {brief.boundaries.must_escalate.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
