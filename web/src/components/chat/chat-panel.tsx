"use client";

import { useCallback, useRef, useState, useEffect } from "react";
import {
  Send,
  Volume2,
  Video,
  Loader2,
  Radio,
  Wifi,
  WifiOff,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/components/chat/chat-message";
import { PipelineIndicator } from "@/components/chat/pipeline-indicator";
import {
  createOrchestratorSocket,
  orchestrate,
  sendChatMessage,
} from "@/lib/api";
import type {
  ChatMessage as ChatMessageType,
  PipelineStage,
  WSOutgoingMessage,
} from "@/lib/types";

type ConnectionMode = "orchestrator-ws" | "orchestrator-http" | "brain-direct";

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState("");
  const [userId, setUserId] = useState("demo-user");
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [includeAudio, setIncludeAudio] = useState(true);
  const [includeVideo, setIncludeVideo] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState<PipelineStage | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [mode, setMode] = useState<ConnectionMode>("orchestrator-http");
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pendingMsgRef = useRef<Partial<ChatMessageType>>({});
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, currentStage]);

  // --- WebSocket lifecycle (only when mode is orchestrator-ws) ---

  const cleanupWs = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    setWsConnected(false);
  }, []);

  const connectWs = useCallback(() => {
    cleanupWs();

    const ws = createOrchestratorSocket(
      (msg) => {
        if (mountedRef.current) handleWSMessage(msg);
      },
      () => {
        if (!mountedRef.current) return;
        setWsConnected(false);
        // exponential backoff: 2s, 4s, 8s, 16s — cap at 3 retries then give up
        if (retryCountRef.current < 3) {
          const delay = Math.min(2000 * 2 ** retryCountRef.current, 16000);
          retryCountRef.current += 1;
          retryTimerRef.current = setTimeout(() => {
            if (mountedRef.current) connectWs();
          }, delay);
        } else {
          // orchestrator unreachable — silently fall back to HTTP
          setMode("orchestrator-http");
        }
      },
      () => {
        if (mountedRef.current) setWsConnected(false);
      },
    );

    ws.onopen = () => {
      if (!mountedRef.current) return;
      retryCountRef.current = 0;
      setWsConnected(true);
    };

    wsRef.current = ws;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cleanupWs]);

  useEffect(() => {
    if (mode === "orchestrator-ws") {
      connectWs();
    } else {
      cleanupWs();
    }

    return cleanupWs;
  }, [mode, connectWs, cleanupWs]);

  // --- WebSocket message handler ---

  function handleWSMessage(msg: WSOutgoingMessage) {
    switch (msg.type) {
      case "ack":
        setCurrentStage("received");
        break;

      case "stage":
        setCurrentStage(msg.data.stage as PipelineStage);
        break;

      case "text": {
        const convId = msg.data.conversation_id as string | undefined;
        if (convId && !conversationId) setConversationId(convId);

        pendingMsgRef.current = {
          ...pendingMsgRef.current,
          content: msg.data.response as string,
          sources: msg.data.sources as ChatMessageType["sources"],
          model_used: msg.data.model_used as string,
        };
        setCurrentStage("brain");
        break;
      }

      case "audio":
        pendingMsgRef.current.audio_base64 = msg.data.audio_base64 as string;
        setCurrentStage("voice");
        break;

      case "video":
        pendingMsgRef.current.video_base64 = msg.data.video_base64 as string;
        setCurrentStage("video");
        break;

      case "complete": {
        const totalMs = msg.data.total_latency_ms as number;
        const partial = pendingMsgRef.current;
        const assistantMsg: ChatMessageType = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: partial.content ?? "",
          audio_base64: partial.audio_base64,
          video_base64: partial.video_base64,
          sources: partial.sources,
          model_used: partial.model_used,
          latency_ms: totalMs,
          timestamp: new Date(),
          stage: "complete",
        };
        setMessages((prev) => [...prev, assistantMsg]);
        pendingMsgRef.current = {};
        setCurrentStage(null);
        setIsLoading(false);
        break;
      }

      case "error": {
        const fatal = msg.data.fatal !== false;
        const detail = msg.data.detail as string;
        if (fatal) {
          toast.error(detail);
          setCurrentStage(null);
          setIsLoading(false);
          pendingMsgRef.current = {};
        } else {
          toast.warning(detail);
        }
        break;
      }

      default:
        break;
    }
  }

  // --- Send via WebSocket ---

  const handleSendWS = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      toast.warning("WebSocket not connected — using HTTP instead");
      handleSendHTTP();
      return;
    }

    const query = input.trim();
    if (!query || isLoading) return;

    const userMsg: ChatMessageType = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    setCurrentStage("received");

    ws.send(
      JSON.stringify({
        type: "query",
        user_id: userId,
        query,
        conversation_id: conversationId,
        include_audio: includeAudio,
        include_video: includeVideo,
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, userId, conversationId, includeAudio, includeVideo, isLoading]);

  // --- Send via HTTP (tries orchestrator first, falls back to Brain) ---

  const handleSendHTTP = useCallback(async () => {
    const query = input.trim();
    if (!query || isLoading) return;

    const userMsg: ChatMessageType = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    setCurrentStage("received");

    try {
      setCurrentStage("brain");

      if (mode === "brain-direct") {
        // Call Brain service directly
        const response = await sendChatMessage({
          user_id: userId,
          query,
          conversation_id: conversationId,
          include_sources: true,
          include_audio: includeAudio,
          include_video: includeVideo,
        });

        if (!conversationId) setConversationId(response.conversation_id);

        const assistantMsg: ChatMessageType = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: response.response,
          audio_base64: response.audio_base64,
          video_base64: response.video_base64,
          sources: response.sources,
          latency_ms: response.latency_ms,
          model_used: response.model_used,
          timestamp: new Date(),
          stage: "complete",
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } else {
        // Try orchestrator HTTP, fall back to Brain if unreachable
        try {
          const response = await orchestrate({
            user_id: userId,
            query,
            conversation_id: conversationId,
            include_audio: includeAudio,
            include_video: includeVideo,
          });

          if (!conversationId) setConversationId(response.conversation_id);

          const assistantMsg: ChatMessageType = {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: response.response_text,
            audio_base64: response.audio_base64,
            video_base64: response.video_base64,
            sources: response.sources,
            latency_ms: response.total_latency_ms,
            timestamp: new Date(),
            stage: "complete",
          };
          setMessages((prev) => [...prev, assistantMsg]);
        } catch {
          // Orchestrator unreachable — fall back to Brain directly
          toast.warning(
            "Orchestrator unavailable — sending directly to Brain service",
          );

          const response = await sendChatMessage({
            user_id: userId,
            query,
            conversation_id: conversationId,
            include_sources: true,
            include_audio: includeAudio,
            include_video: includeVideo,
          });

          if (!conversationId) setConversationId(response.conversation_id);

          const assistantMsg: ChatMessageType = {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: response.response,
            audio_base64: response.audio_base64,
            video_base64: response.video_base64,
            sources: response.sources,
            latency_ms: response.latency_ms,
            model_used: response.model_used,
            timestamp: new Date(),
            stage: "complete",
          };
          setMessages((prev) => [...prev, assistantMsg]);
        }
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to send message";
      toast.error(message);
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
    } finally {
      setIsLoading(false);
      setCurrentStage(null);
    }
  }, [
    input,
    userId,
    conversationId,
    includeAudio,
    includeVideo,
    isLoading,
    mode,
  ]);

  // --- Unified send ---

  const handleSend = useCallback(() => {
    if (
      mode === "orchestrator-ws" &&
      wsRef.current?.readyState === WebSocket.OPEN
    ) {
      handleSendWS();
    } else {
      handleSendHTTP();
    }
  }, [mode, handleSendWS, handleSendHTTP]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setConversationId(undefined);
    setCurrentStage(null);
    pendingMsgRef.current = {};
  }, []);

  const cycleMode = useCallback(() => {
    setMode((prev) => {
      if (prev === "orchestrator-ws") return "orchestrator-http";
      if (prev === "orchestrator-http") return "brain-direct";
      return "orchestrator-ws";
    });
  }, []);

  const modeLabel =
    mode === "orchestrator-ws"
      ? wsConnected
        ? "Live"
        : "Connecting"
      : mode === "orchestrator-http"
        ? "HTTP"
        : "Brain";

  const modeIcon =
    mode === "orchestrator-ws" ? (
      wsConnected ? (
        <Wifi className="h-3.5 w-3.5" />
      ) : (
        <Radio className="h-3.5 w-3.5 animate-pulse" />
      )
    ) : (
      <WifiOff className="h-3.5 w-3.5" />
    );

  const modeColor =
    mode === "orchestrator-ws"
      ? "bg-emerald-600 text-white"
      : mode === "orchestrator-http"
        ? "bg-blue-600 text-white"
        : "bg-muted text-muted-foreground hover:text-foreground";

  return (
    <div className="flex flex-1 flex-col">
      {/* Top bar */}
      <div className="border-b px-6 py-3">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <label
                htmlFor="user-id"
                className="text-xs text-muted-foreground"
              >
                User ID
              </label>
              <input
                id="user-id"
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="h-7 rounded-md border bg-background px-2 text-xs w-32 outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            <div className="h-4 w-px bg-border" />

            <button
              type="button"
              onClick={() => setIncludeAudio((v) => !v)}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                includeAudio
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              <Volume2 className="h-3.5 w-3.5" />
              Audio
            </button>

            <button
              type="button"
              onClick={() => setIncludeVideo((v) => !v)}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                includeVideo
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              <Video className="h-3.5 w-3.5" />
              Video
            </button>

            <div className="h-4 w-px bg-border" />

            <button
              type="button"
              onClick={cycleMode}
              title="Click to cycle: Live (WebSocket) → HTTP (Orchestrator) → Brain (direct)"
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors ${modeColor}`}
            >
              {modeIcon}
              {modeLabel}
            </button>
          </div>

          <Button variant="ghost" size="sm" onClick={handleNewChat}>
            New Chat
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 py-6">
          {messages.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted mb-4">
                <Radio className="h-5 w-5 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold">Ask VersionAI</h3>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                Ask questions about your ingested data. Responses flow through
                the orchestration pipeline: Brain, Voice, and Video Avatar.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {isLoading && (
                <div className="flex flex-col gap-2">
                  <PipelineIndicator stage={currentStage} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Input */}
      <div className="border-t bg-background p-4">
        <div className="mx-auto flex max-w-3xl items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your data..."
            rows={1}
            disabled={isLoading}
            className="flex-1 resize-none rounded-lg border bg-background px-4 py-2.5 text-sm outline-none focus:ring-1 focus:ring-ring disabled:opacity-50 min-h-[40px] max-h-[160px]"
            style={{ fieldSizing: "content" } as React.CSSProperties}
          />
          <Button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            size="lg"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <div className="mx-auto max-w-3xl mt-2">
          <p className="text-xs text-muted-foreground text-center">
            {mode === "orchestrator-ws"
              ? "Real-time streaming via Orchestrator"
              : mode === "orchestrator-http"
                ? "HTTP via Orchestrator (fallback to Brain)"
                : "Direct to Brain service"}{" "}
            &middot;{" "}
            {includeAudio && includeVideo
              ? "Text + Audio + Video"
              : includeAudio
                ? "Text + Audio"
                : includeVideo
                  ? "Text + Video (requires audio)"
                  : "Text only"}
          </p>
        </div>
      </div>
    </div>
  );
}
