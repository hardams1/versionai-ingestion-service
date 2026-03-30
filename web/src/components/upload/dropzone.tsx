"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileUp } from "lucide-react";
import { ACCEPT_MAP } from "@/lib/validation";
import { cn } from "@/lib/utils";

interface DropzoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

export function Dropzone({ onFilesSelected, disabled }: DropzoneProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFilesSelected(acceptedFiles);
      }
    },
    [onFilesSelected]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } =
    useDropzone({
      onDrop,
      accept: ACCEPT_MAP,
      disabled,
      multiple: true,
      maxSize: 500 * 1024 * 1024,
    });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "relative flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-12 transition-all duration-200 cursor-pointer",
        "hover:border-primary/50 hover:bg-muted/50",
        isDragActive && !isDragReject && "border-primary bg-primary/5 scale-[1.01]",
        isDragReject && "border-destructive bg-destructive/5",
        disabled && "opacity-50 cursor-not-allowed pointer-events-none"
      )}
    >
      <input {...getInputProps()} />

      <div
        className={cn(
          "flex h-16 w-16 items-center justify-center rounded-full transition-colors",
          isDragActive ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
        )}
      >
        {isDragActive ? (
          <FileUp className="h-8 w-8 animate-bounce" />
        ) : (
          <Upload className="h-8 w-8" />
        )}
      </div>

      <div className="text-center">
        <p className="text-lg font-medium">
          {isDragActive
            ? isDragReject
              ? "Some files are not supported"
              : "Drop your files here"
            : "Drag & drop files here"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          or <span className="text-primary font-medium underline underline-offset-4">browse from your computer</span>
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-2 mt-2">
        {["MP4", "MOV", "MP3", "WAV", "PDF", "TXT", "CSV", "DOCX"].map(
          (ext) => (
            <span
              key={ext}
              className="rounded-md bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground"
            >
              .{ext.toLowerCase()}
            </span>
          )
        )}
      </div>

      <p className="text-xs text-muted-foreground">Max file size: 500 MB</p>
    </div>
  );
}
