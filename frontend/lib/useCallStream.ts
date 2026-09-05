"use client";

import { useEffect, useRef, useState } from "react";
import { apiBase, type StreamEvent, type PendingDecision } from "./api";

export interface LiveState {
  connected: boolean;
  callId: string | null;
  status: string; // connecting | on_call | waiting_on_you | ended | idle
  provider?: string;
  objective?: string;
  transcript: { role: string; text: string; ts: number }[];
  decision: (PendingDecision & { timeout_s: number; openedAt: number }) | null;
  lastResolved: { answer: string; timed_out: boolean } | null;
  ended: {
    outcome: string;
    confirmation_number: string | null;
    turns: number;
  } | null;
  events: StreamEvent[];
}

const EMPTY: LiveState = {
  connected: false,
  callId: null,
  status: "idle",
  transcript: [],
  decision: null,
  lastResolved: null,
  ended: null,
  events: [],
};

/** Subscribes to /stream and folds events into a live call view. */
export function useCallStream(): LiveState {
  const [state, setState] = useState<LiveState>(EMPTY);
  const seen = useRef(0);

  useEffect(() => {
    const es = new EventSource(`${apiBase}/stream?after=${seen.current}`);
    es.onopen = () => setState((s) => ({ ...s, connected: true }));
    es.onerror = () => setState((s) => ({ ...s, connected: false }));
    es.onmessage = (m) => {
      let e: StreamEvent;
      try {
        e = JSON.parse(m.data);
      } catch {
        return;
      }
      if (!e || typeof e.seq !== "number") return;
      seen.current = Math.max(seen.current, e.seq);
      setState((s) => fold(s, e));
    };
    return () => es.close();
  }, []);

  return state;
}

function fold(s: LiveState, e: StreamEvent): LiveState {
  const events = [...s.events.slice(-200), e];
  switch (e.kind) {
    case "call_started":
      return {
        ...EMPTY,
        connected: s.connected,
        events,
        callId: e.call_id,
        status: "on_call",
        provider: e.provider ?? undefined,
        objective: e.objective ?? undefined,
      };
    case "status":
      return { ...s, events, status: e.status };
    case "turn":
      return {
        ...s,
        events,
        transcript: [
          ...s.transcript,
          { role: e.role, text: e.text, ts: e.ts },
        ].slice(-300),
      };
    case "decision_open":
      return {
        ...s,
        events,
        status: "waiting_on_you",
        decision: {
          decision_id: e.decision_id,
          call_id: e.call_id,
          question: e.question,
          options: e.options,
          timeout_s: e.timeout_s,
          openedAt: Date.now(),
        },
        lastResolved: null,
      };
    case "decision_resolved":
      return {
        ...s,
        events,
        decision: null,
        lastResolved: { answer: e.answer, timed_out: e.timed_out },
        status: s.status === "waiting_on_you" ? "on_call" : s.status,
      };
    case "call_ended":
      return {
        ...s,
        events,
        status: "ended",
        decision: null,
        ended: {
          outcome: e.outcome,
          confirmation_number: e.confirmation_number,
          turns: e.turns,
        },
      };
    default:
      return { ...s, events };
  }
}
