"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { User, Bot, Clock, Cpu, FileText } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

function detectAudioMime(b64: string): string {
  if (b64.startsWith("UklGR")) return "audio/wav";
  if (b64.startsWith("//u") || b64.startsWith("SUQ")) return "audio/mpeg";
  if (b64.startsWith("T2dn")) return "audio/ogg";
  return "audio/mpeg";
}

function b64ToBlob(b64: string, mime: string): string {
  const binStr = atob(b64);
  const len = binStr.length;
  const CHUNK = 65536;
  const chunks: Uint8Array[] = [];
  for (let offset = 0; offset < len; offset += CHUNK) {
    const end = Math.min(offset + CHUNK, len);
    const arr = new Uint8Array(end - offset);
    for (let i = offset; i < end; i++) arr[i - offset] = binStr.charCodeAt(i);
    chunks.push(arr);
  }
  const totalLen = chunks.reduce((s, c) => s + c.length, 0);
  const merged = new Uint8Array(totalLen);
  let pos = 0;
  for (const c of chunks) {
    merged.set(c, pos);
    pos += c.length;
  }
  return URL.createObjectURL(new Blob([merged], { type: mime }));
}

function MediaPlayer({ audio_base64, video_base64 }: { audio_base64?: string | null; video_base64?: string | null }) {
  const [videoSrc, setVideoSrc] = useState<string | null>(null);
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let vUrl: string | null = null;
    let aUrl: string | null = null;
    setVideoError(null);

    if (video_base64) {
      try {
        vUrl = b64ToBlob(video_base64, "video/mp4");
        setVideoSrc(vUrl);
      } catch {
        setVideoSrc(null);
        setVideoError("Failed to decode video");
      }
    } else {
      setVideoSrc(null);
    }

    if (audio_base64 && !video_base64) {
      try {
        aUrl = b64ToBlob(audio_base64, detectAudioMime(audio_base64));
        setAudioSrc(aUrl);
      } catch {
        setAudioSrc(null);
      }
    } else {
      setAudioSrc(null);
    }

    return () => {
      if (vUrl) URL.revokeObjectURL(vUrl);
      if (aUrl) URL.revokeObjectURL(aUrl);
    };
  }, [video_base64, audio_base64]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !videoSrc) return;
    el.load();
  }, [videoSrc]);

  if (!videoSrc && !audioSrc && !videoError) return null;

  return (
    <div className="mt-3 space-y-3">
      {videoError && (
        <p className="text-xs text-destructive">{videoError}</p>
      )}
      {videoSrc && (
        <div className="overflow-hidden rounded-lg border bg-black">
          <video
            ref={videoRef}
            controls
            playsInline
            preload="auto"
            className="w-full max-w-md"
            src={videoSrc}
            onError={() => setVideoError("Video playback failed — codec may not be supported")}
          >
            Your browser does not support video playback.
          </video>
        </div>
      )}
      {audioSrc && !videoSrc && (
        <audio controls preload="auto" className="w-full max-w-md" src={audioSrc}>
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
