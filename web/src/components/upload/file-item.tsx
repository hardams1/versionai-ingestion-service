"use client";

import {
  Video,
  Music,
  FileText,
  File as FileIcon,
  CheckCircle2,
  XCircle,
  Loader2,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import type { FileUploadItem } from "@/lib/types";
import { formatFileSize } from "@/lib/validation";
import { cn } from "@/lib/utils";

interface FileItemProps {
  item: FileUploadItem;
  onRemove: (id: string) => void;
}

function FileTypeIcon({ type }: { type: string }) {
  const iconClass = "h-5 w-5";
  if (type.startsWith("video/")) return <Video className={cn(iconClass, "text-blue-500")} />;
  if (type.startsWith("audio/")) return <Music className={cn(iconClass, "text-purple-500")} />;
  if (type === "application/pdf") return <FileText className={cn(iconClass, "text-red-500")} />;
  if (type.startsWith("text/")) return <FileText className={cn(iconClass, "text-green-500")} />;
  return <FileIcon className={cn(iconClass, "text-amber-500")} />;
}

function StatusIndicator({ state }: { state: FileUploadItem["state"] }) {
  switch (state) {
    case "uploading":
      return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
    case "error":
      return <XCircle className="h-4 w-4 text-destructive" />;
    default:
      return null;
  }
}

export function FileItem({ item, onRemove }: FileItemProps) {
  const { file, state, progress, response, error } = item;

  return (
    <div
      className={cn(
        "group flex items-center gap-4 rounded-lg border p-4 transition-colors",
        state === "error" && "border-destructive/30 bg-destructive/5",
        state === "success" && "border-emerald-500/30 bg-emerald-500/5"
      )}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
        <FileTypeIcon type={file.type} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-medium">{file.name}</p>
          <StatusIndicator state={state} />
        </div>

        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-muted-foreground">
            {formatFileSize(file.size)}
          </span>

          {response && (
            <>
              <span className="text-xs text-muted-foreground">·</span>
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                {response.file_category}
              </Badge>
              {response.pipelines.map((p) => (
                <Badge
                  key={p}
                  variant="outline"
                  className="text-[10px] px-1.5 py-0"
                >
                  {p}
                </Badge>
              ))}
            </>
          )}
        </div>

        {state === "uploading" && (
          <Progress value={progress} className="mt-2 h-1.5" />
        )}

        {error && (
          <p className="mt-1 text-xs text-destructive">{error}</p>
        )}

        {response && (
          <p className="mt-1 text-xs text-muted-foreground font-mono">
            ID: {response.ingestion_id.slice(0, 8)}...
          </p>
        )}
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={() => onRemove(item.id)}
        disabled={state === "uploading"}
      >
        <Trash2 className="h-4 w-4 text-muted-foreground" />
      </Button>
    </div>
  );
}
