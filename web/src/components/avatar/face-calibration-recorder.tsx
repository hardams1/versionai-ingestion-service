"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  Eye,
  Loader2,
  MessageCircle,
  Mic,
  Minus,
  ScanFace,
  SmilePlus,
  Square,
  Trash2,
  Upload,
  Video,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth/auth-provider";
import {
  deleteCalibration,
  fetchCalibrationSequence,
  fetchCalibrationStatus,
  uploadCalibrationVideo,
  type CalibrationPrompt,
  type CalibrationSequence,
  type CalibrationStatus,
} from "@/lib/face-calibration-api";

const ICON_MAP: Record<string, React.ElementType> = {
  eye: Eye,
  "arrow-left": ArrowLeft,
  "arrow-right": ArrowRight,
  "arrow-up": ArrowUp,
  "arrow-down": ArrowDown,
  smile: SmilePlus,
  zap: Zap,
  minus: Minus,
  mic: Mic,
  "message-circle": MessageCircle,
  face: ScanFace,
};

interface FaceCalibrationRecorderProps {
  onCalibrationComplete?: () => void;
}

type RecordingPhase = "idle" | "countdown" | "recording" | "review" | "uploading";

export function FaceCalibrationRecorder({
  onCalibrationComplete,
}: FaceCalibrationRecorderProps) {
  const { user } = useAuth();
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const [phase, setPhase] = useState<RecordingPhase>("idle");
  const [sequence, setSequence] = useState<CalibrationSequence | null>(null);
  const [status, setStatus] = useState<CalibrationStatus | null>(null);
  const [currentPromptIndex, setCurrentPromptIndex] = useState(0);
  const [promptTimeLeft, setPromptTimeLeft] = useState(0);
  const [totalDuration, setTotalDuration] = useState(0);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [faceDetected, setFaceDetected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    async function load() {
      try {
        const [seq, stat] = await Promise.all([
          fetchCalibrationSequence(),
          fetchCalibrationStatus(user!.user_id),
        ]);
        if (!cancelled) {
          setSequence(seq);
          setStatus(stat);
        }
      } catch {
        // service may not be running
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      stopCamera();
    };
  }, []);

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: true,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setFaceDetected(true);
      return true;
    } catch {
      toast.error("Camera access denied. Please allow camera and microphone access.");
      return false;
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  const startRecording = useCallback(async () => {
    if (!sequence) return;

    const cameraReady = await startCamera();
    if (!cameraReady) return;

    setPhase("countdown");
    setCurrentPromptIndex(0);
    setTotalDuration(0);

    await new Promise((resolve) => setTimeout(resolve, 3000));

    const stream = streamRef.current;
    if (!stream) return;

    const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
      ? "video/webm;codecs=vp9,opus"
      : MediaRecorder.isTypeSupported("video/webm")
        ? "video/webm"
        : "video/mp4";

    const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 2_500_000 });
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: mimeType });
      setRecordedBlob(blob);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
      setPhase("review");
      stopCamera();
    };

    mediaRecorderRef.current = recorder;
    recorder.start(1000);
    setPhase("recording");

    let promptIdx = 0;
    let secondsInPrompt = 0;
    setCurrentPromptIndex(0);
    setPromptTimeLeft(sequence.prompts[0]?.duration_seconds ?? 0);

    timerRef.current = setInterval(() => {
      setTotalDuration((d) => d + 1);
      secondsInPrompt += 1;

      const currentPrompt = sequence.prompts[promptIdx];
      if (currentPrompt && secondsInPrompt >= currentPrompt.duration_seconds) {
        promptIdx += 1;
        secondsInPrompt = 0;
        if (promptIdx < sequence.prompts.length) {
          setCurrentPromptIndex(promptIdx);
          setPromptTimeLeft(sequence.prompts[promptIdx].duration_seconds);
        } else {
          if (timerRef.current) clearInterval(timerRef.current);
          recorder.stop();
          return;
        }
      }
      setPromptTimeLeft(
        (sequence.prompts[promptIdx]?.duration_seconds ?? 0) - secondsInPrompt
      );
    }, 1000);
  }, [sequence, startCamera, stopCamera, previewUrl]);

  const stopRecordingEarly = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = undefined;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const discardRecording = useCallback(() => {
    setRecordedBlob(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setPhase("idle");
    setTotalDuration(0);
    setCurrentPromptIndex(0);
  }, [previewUrl]);

  const uploadRecording = useCallback(async () => {
    if (!recordedBlob || !user) return;

    setPhase("uploading");
    try {
      const result = await uploadCalibrationVideo(user.user_id, recordedBlob);
      toast.success(result.message);
      setStatus({
        user_id: user.user_id,
        face_scan_status: "processing",
        calibration_video_path: result.video_path,
        face_model_path: null,
        blendshape_profile_path: null,
        has_calibration_video: false,
      });

      pollStatus();
      setRecordedBlob(null);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
      setPhase("idle");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
      setPhase("review");
    }
  }, [recordedBlob, user, previewUrl]);

  const pollStatus = useCallback(async () => {
    if (!user) return;
    const maxAttempts = 30;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      try {
        const stat = await fetchCalibrationStatus(user.user_id);
        setStatus(stat);
        if (stat.face_scan_status === "ready") {
          toast.success("Face calibration complete! Your avatar now uses your real facial data.");
          onCalibrationComplete?.();
          return;
        }
        if (stat.face_scan_status === "failed") {
          toast.error("Face reconstruction failed. Please try recording again.");
          return;
        }
      } catch {
        break;
      }
    }
  }, [user, onCalibrationComplete]);

  const handleDelete = useCallback(async () => {
    if (!user) return;
    setDeleting(true);
    try {
      await deleteCalibration(user.user_id);
      setStatus({
        user_id: user.user_id,
        face_scan_status: "none",
        calibration_video_path: null,
        face_model_path: null,
        blendshape_profile_path: null,
        has_calibration_video: false,
      });
      toast.success("Calibration data deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }, [user]);

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const currentPrompt: CalibrationPrompt | undefined =
    sequence?.prompts[currentPromptIndex];

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading calibration...
      </div>
    );
  }

  if (status?.face_scan_status === "ready") {
    return (
      <div className="space-y-3">
        <div className="rounded-md border border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20 dark:border-emerald-800 p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <span className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
              Face scan complete
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Your facial data has been processed. Video responses now use your real
            expressions, head motion, and lip movements for human-realistic output.
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setStatus((s) =>
                s ? { ...s, face_scan_status: "none", has_calibration_video: false } : s
              );
            }}
          >
            <Video className="h-4 w-4 mr-1" />
            Re-record
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDelete}
            disabled={deleting}
            className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
          >
            {deleting ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Trash2 className="h-4 w-4 mr-1" />
            )}
            Delete Scan Data
          </Button>
        </div>
      </div>
    );
  }

  if (status?.face_scan_status === "processing") {
    return (
      <div className="space-y-3">
        <div className="rounded-md border border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800 p-4">
          <div className="flex items-center gap-2 mb-1">
            <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" />
            <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
              Processing face scan...
            </span>
          </div>
          <p className="text-xs text-blue-600 dark:text-blue-400">
            Extracting 3D facial geometry, expression blendshapes, and lip-sync calibration.
            This usually takes 1-2 minutes.
          </p>
        </div>
      </div>
    );
  }

  if (status?.face_scan_status === "failed") {
    return (
      <div className="space-y-3">
        <div className="rounded-md border border-red-200 bg-red-50 dark:bg-red-950/20 dark:border-red-800 p-4">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
            <span className="text-sm font-medium text-red-700 dark:text-red-300">
              Face scan failed
            </span>
          </div>
          <p className="text-xs text-red-600 dark:text-red-400">
            The reconstruction could not complete. Try recording again with better lighting and
            ensure your face is clearly visible throughout.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() =>
            setStatus((s) =>
              s ? { ...s, face_scan_status: "none" } : s
            )
          }
        >
          <Video className="h-4 w-4 mr-1" />
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Camera preview / recording area */}
      <div className="relative aspect-video w-full overflow-hidden rounded-lg border bg-black">
        {phase === "idle" && !previewUrl && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-white/60 gap-3">
            <ScanFace className="h-12 w-12" />
            <p className="text-sm">Click &quot;Start Face Scan&quot; to begin</p>
          </div>
        )}

        <video
          ref={videoRef}
          className={`h-full w-full object-cover ${phase === "recording" || phase === "countdown" ? "" : "hidden"}`}
          muted
          playsInline
        />

        {/* Countdown overlay */}
        {phase === "countdown" && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60">
            <div className="text-center">
              <p className="text-white text-lg font-medium mb-2">Get ready...</p>
              <p className="text-white/70 text-sm">Position your face in the center</p>
              <p className="text-white/70 text-sm">Ensure good, even lighting</p>
            </div>
          </div>
        )}

        {/* Recording prompt overlay */}
        {phase === "recording" && currentPrompt && (
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-4">
            <div className="flex items-center gap-3">
              {(() => {
                const Icon = ICON_MAP[currentPrompt.icon] || ScanFace;
                return <Icon className="h-6 w-6 text-white shrink-0" />;
              })()}
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm font-medium leading-tight">
                  {currentPrompt.instruction}
                </p>
                <p className="text-white/60 text-xs mt-0.5">
                  {promptTimeLeft}s remaining &middot; Step{" "}
                  {currentPromptIndex + 1}/{sequence?.prompts.length}
                </p>
              </div>
            </div>
            {/* Progress bar */}
            <div className="mt-2 h-1 bg-white/20 rounded-full overflow-hidden">
              <div
                className="h-full bg-white/80 transition-all duration-1000"
                style={{
                  width: `${((currentPromptIndex + 1) / (sequence?.prompts.length ?? 1)) * 100}%`,
                }}
              />
            </div>
          </div>
        )}

        {/* Recording indicator */}
        {phase === "recording" && (
          <div className="absolute top-3 right-3 flex items-center gap-2 bg-red-600 text-white px-2.5 py-1 rounded-full text-xs font-medium">
            <span className="h-2 w-2 rounded-full bg-white animate-pulse" />
            REC {formatTime(totalDuration)}
          </div>
        )}

        {/* Preview */}
        {phase === "review" && previewUrl && (
          <video
            src={previewUrl}
            className="h-full w-full object-cover"
            controls
            playsInline
          />
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3">
        {phase === "idle" && (
          <Button size="sm" onClick={startRecording}>
            <ScanFace className="h-4 w-4 mr-1" />
            Start Face Scan
          </Button>
        )}

        {phase === "recording" && (
          <Button
            variant="destructive"
            size="sm"
            onClick={stopRecordingEarly}
          >
            <Square className="h-4 w-4 mr-1" />
            Stop ({formatTime(totalDuration)})
          </Button>
        )}

        {phase === "review" && (
          <>
            <Button size="sm" onClick={uploadRecording}>
              <Upload className="h-4 w-4 mr-1" />
              Upload & Process
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={discardRecording}
            >
              Discard & Re-record
            </Button>
          </>
        )}

        {phase === "uploading" && (
          <Button size="sm" disabled>
            <Loader2 className="h-4 w-4 animate-spin mr-1" />
            Uploading...
          </Button>
        )}
      </div>

      {/* Guidance text */}
      {phase === "idle" && (
        <div className="rounded-md border border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800 p-3">
          <p className="text-xs font-medium text-blue-800 dark:text-blue-300 mb-1">
            Tips for best face scan quality:
          </p>
          <ul className="text-xs text-blue-700 dark:text-blue-400 space-y-0.5 list-disc list-inside">
            <li>Use even, front-facing lighting (avoid harsh shadows)</li>
            <li>Ensure your full face is visible with no obstructions</li>
            <li>Follow the on-screen prompts for head movements and expressions</li>
            <li>The scan takes about 80 seconds with guided prompts</li>
            <li>Speak naturally during the reading sections for lip-sync calibration</li>
          </ul>
        </div>
      )}
    </div>
  );
}
