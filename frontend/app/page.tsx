import { History } from "@/components/History";
import { LivePanel } from "@/components/LivePanel";
import { NewCall } from "@/components/NewCall";
import { AuroraBackground } from "@/components/ui/aurora-background";

export default function Page() {
  return (
    <div className="flex flex-1 flex-col">
      <AuroraBackground className="h-64 min-h-0 justify-end pb-8" showRadialGradient>
        <div className="relative z-10 w-full max-w-6xl px-6 duration-700 animate-in fade-in slide-in-from-bottom-2">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300/90">
            Holdline
          </div>
          <h1 className="mt-2 max-w-3xl text-3xl font-semibold text-white sm:text-4xl">
            The agent that holds the line so you don&apos;t have to.
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-white/70">
            Hand it a phone call you&apos;ve been dreading. It works the menu, waits
            on hold, talks to the rep — and only pings you when there&apos;s a real
            decision to make.
          </p>
        </div>
      </AuroraBackground>

      <main className="mx-auto -mt-6 w-full max-w-6xl flex-1 space-y-8 px-6 pb-16">
        <div className="grid gap-5 lg:grid-cols-[24rem_1fr]">
          <NewCall />
          <LivePanel />
        </div>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Recent calls
          </h2>
          <History />
        </section>
      </main>
    </div>
  );
}
