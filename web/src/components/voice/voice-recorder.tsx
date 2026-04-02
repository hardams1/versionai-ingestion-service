"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Mic, MicOff, Square, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  uploadVoiceSample,
  type VoiceSampleResponse,
} from "@/lib/voice-training-api";

interface VoiceRecorderProps {
  onSampleUploaded?: (result: VoiceSampleResponse) => void;
  disabled?: boolean;
}

export function VoiceRecorder({
  onSampleUploaded,
  disabled,
}: VoiceRecorderProps) {
  const [recording, setRecording] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [duration, setDuration] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4";

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: mimeType });
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setAudioUrl(URL.createObjectURL(blob));
      };

      mediaRecorderRef.current = recorder;
      recorder.start(1000);
      setRecording(true);
      setDuration(0);
      setAudioUrl(null);

      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);
    } catch (err) {
      toast.error("Microphone access denied. Please allow access and try again.");
    }
  }, [audioUrl]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = undefined;
      }
    }
  }, [recording]);

  const uploadRecording = useCallback(async () => {
    if (chunksRef.current.length === 0) return;

    const mimeType =
      mediaRecorderRef.current?.mimeType ?? "audio/webm;codecs=opus";
    const blob = new Blob(chunksRef.current, { type: mimeType });

    setUploading(true);
    try {
      const ext = mimeType.includes("mp4") ? "mp4" : "webm";
      const result = await uploadVoiceSample(blob, `recording.${ext}`);
      toast.success(result.message);
      onSampleUploaded?.(result);
      chunksRef.current = [];
      setAudioUrl(null);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to upload sample"
      );
    } finally {
      setUploading(false);
    }
  }, [onSampleUploaded]);

  const handleFileUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      if (!file.type.startsWith("audio/")) {
        toast.error("Please select an audio file");
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        toast.error("Audio file must be under 50MB");
        return;
      }

      setUploading(true);
      try {
        const result = await uploadVoiceSample(file, file.name);
        toast.success(result.message);
        onSampleUploaded?.(result);
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Failed to upload sample"
        );
      } finally {
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [onSampleUploaded]
  );

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {recording ? (
          <Button
            variant="destructive"
            size="sm"
            onClick={stopRecording}
            disabled={disabled}
          >
            <Square className="h-4 w-4 mr-1" />
            Stop ({formatTime(duration)})
          </Button>
        ) : (
          <Button
            size="sm"
            onClick={startRecording}
            disabled={disabled || uploading}
          >
            <Mic className="h-4 w-4 mr-1" />
            Record
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || recording || uploading}
        >
          <Upload className="h-4 w-4 mr-1" />
          Upload File
        </Button>

        {recording && (
          <span className="flex items-center gap-1 text-sm text-red-500 animate-pulse">
            <MicOff className="h-3 w-3" />
            Recording...
          </span>
        )}
      </div>

      {audioUrl && !recording && (
        <div className="space-y-2">
          <audio src={audioUrl} controls className="w-full h-8" />
          <Button
            size="sm"
            onClick={uploadRecording}
            disabled={uploading}
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Upload className="h-4 w-4 mr-1" />
            )}
            {uploading ? "Uploading..." : "Upload This Recording"}
          </Button>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*"
        onChange={handleFileUpload}
        className="hidden"
      />
    </div>
  );
}
