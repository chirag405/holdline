import { cn } from "@/lib/utils";

const MAP: Record<string, { label: string; dot: string; text: string }> = {
  idle: { label: "Idle", dot: "bg-muted-foreground", text: "text-muted-foreground" },
  connecting: { label: "Dialing", dot: "bg-amber-400 animate-pulse", text: "text-amber-300" },
  on_call: { label: "On the call", dot: "bg-emerald-400 animate-pulse", text: "text-emerald-300" },
  waiting_on_you: {
    label: "Waiting on you",
    dot: "bg-amber-400 animate-ping",
    text: "text-amber-300",
  },
  ended: { label: "Call ended", dot: "bg-muted-foreground", text: "text-muted-foreground" },
};

export function StatusPill({ status }: { status: string }) {
  const s = MAP[status] ?? MAP.idle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/60 px-3 py-1 text-xs font-medium backdrop-blur",
        s.text,
      )}
    >
      <span className={cn("size-2 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}
