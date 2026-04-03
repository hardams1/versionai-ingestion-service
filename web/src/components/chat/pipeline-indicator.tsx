"use client";

import { Brain, Mic, Volume2, Video, Loader2, CheckCircle2 } from "lucide-react";
import type { PipelineStage } from "@/lib/types";

const STAGES: {
  key: PipelineStage;
  label: string;
  icon: typeof Brain;
}[] = [
  { key: "transcription", label: "Transcribing", icon: Mic },
  { key: "brain", label: "Thinking", icon: Brain },
  { key: "voice", label: "Generating audio", icon: Volume2 },
  { key: "video", label: "Rendering video", icon: Video },
];

function stageIndex(stage: PipelineStage | null): number {
  if (!stage) return -1;
  if (stage === "received") return -1;
  return STAGES.findIndex((s) => s.key === stage);
}

export function PipelineIndicator({
  stage,
}: {
  stage: PipelineStage | null;
}) {
  if (!stage) return null;

  const activeIdx = stageIndex(stage);

  return (
    <div className="flex items-center gap-4 rounded-xl border bg-muted/50 px-4 py-3">
      {STAGES.map((s, i) => {
        const Icon = s.icon;
        const isActive = i === activeIdx;
        const isDone = i < activeIdx;
        const isPending = i > activeIdx;

        return (
          <div
            key={s.key}
            className={`flex items-center gap-1.5 text-xs font-medium transition-colors ${
              isActive
                ? "text-foreground"
                : isDone
                  ? "text-emerald-600"
                  : "text-muted-foreground/50"
            }`}
          >
            {isDone ? (
              <CheckCircle2 className="h-3.5 w-3.5" />
            ) : isActive ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Icon className="h-3.5 w-3.5" />
            )}
            {s.label}
            {i < STAGES.length - 1 && (
              <span
                className={`ml-2 h-px w-6 ${isDone ? "bg-emerald-600" : "bg-border"}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
