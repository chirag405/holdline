"use client";

import { Bot, Headset, Info } from "lucide-react";
import {
  ChatContainerContent,
  ChatContainerRoot,
  ChatContainerScrollAnchor,
} from "@/components/ui/chat-container";
import { Message, MessageContent } from "@/components/ui/message";
import { cn } from "@/lib/utils";

export interface Turn {
  role: string;
  text: string;
  ts?: number;
}

const ROLES: Record<
  string,
  { who: string; icon: typeof Bot; align: "left" | "right"; tone: string }
> = {
  agent: { who: "Holdline", icon: Bot, align: "right", tone: "text-emerald-300" },
  assistant: { who: "Holdline", icon: Bot, align: "right", tone: "text-emerald-300" },
  other: { who: "Representative", icon: Headset, align: "left", tone: "text-sky-300" },
  user: { who: "Representative", icon: Headset, align: "left", tone: "text-sky-300" },
  system: { who: "System", icon: Info, align: "left", tone: "text-muted-foreground" },
};

export function Transcript({ turns }: { turns: Turn[] }) {
  if (turns.length === 0) {
    return (
      <div className="grid h-full place-items-center text-sm text-muted-foreground">
        Waiting for the first words on the line…
      </div>
    );
  }
  return (
    <ChatContainerRoot className="h-full">
      <ChatContainerContent className="space-y-4 p-1">
        {turns.map((t, i) => {
          const r = ROLES[t.role] ?? ROLES.system;
          const Icon = r.icon;
          const mine = r.align === "right";
          return (
            <Message
              key={i}
              className={cn("items-end gap-2", mine && "flex-row-reverse")}
            >
              <div
                className={cn(
                  "mb-1 grid size-7 shrink-0 place-items-center rounded-full border border-border/60 bg-card",
                  r.tone,
                )}
              >
                <Icon className="size-3.5" />
              </div>
              <div className={cn("max-w-[78%]", mine && "text-right")}>
                <div className={cn("mb-1 text-[11px] font-medium", r.tone)}>{r.who}</div>
                <MessageContent
                  markdown={false}
                  className={cn(
                    "rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
                    mine
                      ? "bg-emerald-500/10 text-emerald-50 ring-1 ring-emerald-500/20"
                      : "bg-card text-foreground ring-1 ring-border/60",
                  )}
                >
                  {t.text}
                </MessageContent>
              </div>
            </Message>
          );
        })}
        <ChatContainerScrollAnchor />
      </ChatContainerContent>
    </ChatContainerRoot>
  );
}
