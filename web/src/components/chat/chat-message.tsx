"use client";

import { useMemo } from "react";
import { User, Bot, Clock, Cpu, FileText } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

function MediaPlayer({ audio_base64, video_base64 }: { audio_base64?: string | null; video_base64?: string | null }) {
  const videoSrc = useMemo(
    () => (video_base64 ? `data:video/mp4;base64,${video_base64}` : null),
    [video_base64]
  );
  const audioSrc = useMemo(
    () => (audio_base64 ? `data:audio/mp3;base64,${audio_base64}` : null),
    [audio_base64]
  );

  if (!videoSrc && !audioSrc) return null;

  return (
    <div className="mt-3 space-y-3">
      {videoSrc && (
        <div className="overflow-hidden rounded-lg border bg-black">
          <video
            controls
            preload="metadata"
            className="w-full max-w-md"
            src={videoSrc}
          >
            Your browser does not support video playback.
          </video>
        </div>
      )}
      {audioSrc && !videoSrc && (
        <audio controls preload="metadata" className="w-full max-w-md" src={audioSrc}>
          Your browser does not support audio playback.
        </audio>
      )}
    </div>
  );
}

function Sources({ sources }: { sources: ChatMessageType["sources"] }) {
  if (!sources || sources.length === 0) return null;

  return (
    <details className="mt-3 group">
      <summary className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
        <FileText className="h-3 w-3" />
        {sources.length} source{sources.length !== 1 ? "s" : ""} used
      </summary>
      <div className="mt-2 space-y-2">
        {sources.map((source, i) => (
          <div key={i} className="rounded-md border bg-muted/50 px-3 py-2 text-xs">
            <p className="line-clamp-3 text-muted-foreground">{source.text}</p>
            <p className="mt-1 text-muted-foreground/60">
              Score: {source.score.toFixed(3)}
              {source.file_id && <> &middot; {source.file_id}</>}
            </p>
          </div>
        ))}
      </div>
    </details>
  );
}

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Bot className="h-4 w-4" />
        </div>
      )}

      <div className={`flex flex-col ${isUser ? "items-end" : ""} max-w-[80%] min-w-0`}>
        <div
          className={`rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted"
          }`}
        >
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>

        {!isUser && (
          <>
            <MediaPlayer
              audio_base64={message.audio_base64}
              video_base64={message.video_base64}
            />
            <Sources sources={message.sources} />
            {(message.latency_ms || message.model_used) && (
              <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                {message.latency_ms && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {(message.latency_ms / 1000).toFixed(1)}s
                  </span>
                )}
                {message.model_used && (
                  <span className="flex items-center gap-1">
                    <Cpu className="h-3 w-3" />
                    {message.model_used}
                  </span>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
          <User className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
