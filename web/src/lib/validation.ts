import { z } from "zod";

const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500 MB

const ACCEPTED_EXTENSIONS = [
  ".mp4", ".mov", ".avi", ".webm", ".mkv",
  ".mp3", ".wav", ".ogg", ".flac", ".m4a",
  ".txt", ".csv", ".md",
  ".pdf",
  ".docx",
];

const DANGEROUS_EXTENSIONS = [
  ".exe", ".bat", ".cmd", ".sh", ".ps1", ".msi",
  ".dll", ".scr", ".com", ".vbs", ".js", ".jar",
];

function getExtension(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

export const fileSchema = z
  .instanceof(File)
  .refine((file) => file.size > 0, "File cannot be empty")
  .refine(
    (file) => file.size <= MAX_FILE_SIZE,
    `File must be smaller than ${MAX_FILE_SIZE / 1024 / 1024} MB`
  )
  .refine(
    (file) => !DANGEROUS_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext)),
    "This file type is not allowed for security reasons"
  )
  .refine(
    (file) => ACCEPTED_EXTENSIONS.includes(getExtension(file.name)),
    "This file format is not supported"
  );

export const uploadFormSchema = z.object({
  files: z.array(fileSchema).min(1, "Please select at least one file"),
});

export type UploadFormValues = z.infer<typeof uploadFormSchema>;

export const ACCEPT_MAP: Record<string, string[]> = {
  "video/*": [".mp4", ".mov", ".avi", ".webm", ".mkv"],
  "audio/*": [".mp3", ".wav", ".ogg", ".flac", ".m4a"],
  "text/plain": [".txt"],
  "text/csv": [".csv"],
  "text/markdown": [".md"],
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
};

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function getFileIcon(type: string): string {
  if (type.startsWith("video/")) return "video";
  if (type.startsWith("audio/")) return "audio";
  if (type === "application/pdf") return "pdf";
  if (type.includes("document")) return "document";
  return "text";
}
