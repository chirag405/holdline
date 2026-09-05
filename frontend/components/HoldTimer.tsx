"use client";

import { useEffect, useState } from "react";
import { SlidingNumber } from "@/components/ui/sliding-number";

/** mm:ss since `startedAt` (ms). Freezes when `running` is false. */
export function HoldTimer({
  startedAt,
  running,
}: {
  startedAt: number | null;
  running: boolean;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running || !startedAt) return;
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, [running, startedAt]);

  const elapsed = startedAt ? Math.max(0, Math.floor((now - startedAt) / 1000)) : 0;
  const mm = Math.floor(elapsed / 60);
  const ss = elapsed % 60;

  return (
    <div className="flex items-center gap-0.5 font-mono text-2xl tabular-nums text-foreground/90">
      <SlidingNumber value={mm} padStart />
      <span className="opacity-40">:</span>
      <SlidingNumber value={ss} padStart />
    </div>
  );
}
