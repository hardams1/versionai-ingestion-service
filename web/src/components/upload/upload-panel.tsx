"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Upload, RotateCcw, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import { Dropzone } from "./dropzone";
import { FileItem } from "./file-item";

import { uploadFile } from "@/lib/api";
import { fileSchema, formatFileSize } from "@/lib/validation";
import type { FileUploadItem } from "@/lib/types";

export function UploadPanel() {
  const [files, setFiles] = useState<FileUploadItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const addFiles = useCallback((newFiles: File[]) => {
    const items: FileUploadItem[] = newFiles.map((file) => ({
      id: `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
      state: "idle" as const,
      progress: 0,
    }));

    const validated = items.map((item) => {
      const result = fileSchema.safeParse(item.file);
      if (!result.success) {
        return {
          ...item,
          state: "error" as const,
          error: result.error.issues[0]?.message ?? "Validation failed",
        };
      }
      return item;
    });

    setFiles((prev) => [...prev, ...validated]);
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const uploadAll = useCallback(async () => {
    const pending = files.filter((f) => f.state === "idle");
    if (pending.length === 0) {
      toast.info("No files to upload");
      return;
    }

    setIsUploading(true);

    const updateItem = (id: string, patch: Partial<FileUploadItem>) =>
      setFiles((prev) =>
        prev.map((f) => (f.id === id ? { ...f, ...patch } : f))
      );

    let successCount = 0;
    let errorCount = 0;

    for (const item of pending) {
      updateItem(item.id, { state: "uploading", progress: 0 });

      try {
        const response = await uploadFile(item.file, (progress) => {
          updateItem(item.id, { progress });
        });
        updateItem(item.id, { state: "success", progress: 100, response });
        successCount++;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Upload failed";
        updateItem(item.id, { state: "error", error: message });
        errorCount++;
      }
    }

    setIsUploading(false);

    if (successCount > 0) {
      toast.success(`${successCount} file${successCount > 1 ? "s" : ""} uploaded successfully`);
    }
    if (errorCount > 0) {
      toast.error(`${errorCount} file${errorCount > 1 ? "s" : ""} failed to upload`);
    }
  }, [files]);

  const clearAll = useCallback(() => {
    setFiles([]);
  }, []);

  const clearCompleted = useCallback(() => {
    setFiles((prev) => prev.filter((f) => f.state !== "success"));
  }, []);

  const pendingCount = files.filter((f) => f.state === "idle").length;
  const successCount = files.filter((f) => f.state === "success").length;
  const totalSize = files
    .filter((f) => f.state === "idle")
    .reduce((acc, f) => acc + f.file.size, 0);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl">
          <Upload className="h-5 w-5" />
          Upload Files
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Upload video, audio, text, or PDF files for AI processing
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
        <Dropzone onFilesSelected={addFiles} disabled={isUploading} />

        {files.length > 0 && (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>{files.length} file{files.length !== 1 ? "s" : ""} selected</span>
                {pendingCount > 0 && (
                  <span>{formatFileSize(totalSize)} pending</span>
                )}
                {successCount > 0 && (
                  <span className="text-emerald-600 flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    {successCount} uploaded
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                {successCount > 0 && (
                  <Button variant="ghost" size="sm" onClick={clearCompleted}>
                    Clear completed
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearAll}
                  disabled={isUploading}
                >
                  <RotateCcw className="mr-1 h-3 w-3" />
                  Clear all
                </Button>
              </div>
            </div>

            <Separator />

            <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {files.map((item) => (
                <FileItem key={item.id} item={item} onRemove={removeFile} />
              ))}
            </div>

            <Button
              className="w-full"
              size="lg"
              onClick={uploadAll}
              disabled={isUploading || pendingCount === 0}
            >
              {isUploading ? (
                <>
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Upload {pendingCount} file{pendingCount !== 1 ? "s" : ""}
                </>
              )}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
