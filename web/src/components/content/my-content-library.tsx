"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Download,
  Eye,
  FileText,
  Film,
  Folder,
  Headphones,
  FileType2,
  FileSpreadsheet,
  HardDrive,
  Mic2,
  Play,
  RefreshCw,
  ScanFace,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth/auth-provider";
import {
  type ContentItem,
  type ContentListResponse,
  type ContentSummaryResponse,
  type CategorySummary,
  type TextPreview,
  type VoiceProfileInfo,
  type AvatarInfo,
  fetchContentSummary,
  fetchContentByCategory,
  fetchTextPreview,
  fetchVoiceProfileInfo,
  fetchAvatarInfo,
  deleteContent,
  getThumbnailUrl,
  getFileUrl,
  getAuthToken,
  formatFileSize,
} from "@/lib/content-api";

// ---------------------------------------------------------------------------
// Category metadata
// ---------------------------------------------------------------------------

const CATEGORY_META: Record<
  string,
  { label: string; icon: typeof Film; color: string; bgColor: string }
> = {
  video: {
    label: "Videos",
    icon: Film,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-100 dark:bg-purple-900/30",
  },
  audio: {
    label: "Audio",
    icon: Headphones,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
  },
  pdf: {
    label: "PDFs",
    icon: FileType2,
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-100 dark:bg-red-900/30",
  },
  text: {
    label: "Text",
    icon: FileText,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-100 dark:bg-green-900/30",
  },
  document: {
    label: "Docs",
    icon: FileSpreadsheet,
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-100 dark:bg-orange-900/30",
  },
};

function getCategoryMeta(category: string) {
  return (
    CATEGORY_META[category] ?? {
      label: category,
      icon: Folder,
      color: "text-gray-600 dark:text-gray-400",
      bgColor: "bg-gray-100 dark:bg-gray-900/30",
    }
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function MyContentLibrary() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<ContentSummaryResponse | null>(null);
  const [voiceProfile, setVoiceProfile] = useState<VoiceProfileInfo | null>(null);
  const [avatarInfo, setAvatarInfo] = useState<AvatarInfo | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [items, setItems] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [gridLoading, setGridLoading] = useState(false);
  const [previewItem, setPreviewItem] = useState<ContentItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ContentItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    try {
      const [contentData, voiceData, avatarData] = await Promise.all([
        fetchContentSummary(),
        fetchVoiceProfileInfo(),
        user ? fetchAvatarInfo(user.user_id) : Promise.resolve(null),
      ]);
      setSummary(contentData);
      setVoiceProfile(voiceData);
      setAvatarInfo(avatarData);

      if (contentData.categories.length > 0 && !activeCategory) {
        const first = contentData.categories[0].category;
        setActiveCategory(first);
        await loadCategory(first);
      }
    } catch {
      toast.error("Failed to load your content");
    } finally {
      setLoading(false);
    }
  }, [user]);

  const loadCategory = useCallback(async (cat: string) => {
    setGridLoading(true);
    try {
      const data = await fetchContentByCategory(cat);
      setItems(data.items);
    } catch {
      toast.error("Failed to load files");
    } finally {
      setGridLoading(false);
    }
  }, []);

  const switchCategory = useCallback(
    async (cat: string) => {
      setActiveCategory(cat);
      await loadCategory(cat);
    },
    [loadCategory]
  );

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteContent(deleteTarget.ingestion_id);
      toast.success(`Deleted "${deleteTarget.filename}"`);
      setItems((prev) =>
        prev.filter((i) => i.ingestion_id !== deleteTarget.ingestion_id)
      );
      setSummary((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          total_files: prev.total_files - 1,
          total_size_bytes: prev.total_size_bytes - deleteTarget.size_bytes,
          categories: prev.categories.map((c) =>
            c.category === deleteTarget.category
              ? {
                  ...c,
                  count: c.count - 1,
                  total_size_bytes: c.total_size_bytes - deleteTarget.size_bytes,
                }
              : c
          ).filter((c) => c.count > 0),
        };
      });
    } catch {
      toast.error("Failed to delete file");
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <HardDrive className="h-5 w-5 text-muted-foreground" />
          <h3 className="text-lg font-semibold">My Content</h3>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="aspect-square animate-pulse rounded-lg bg-muted"
            />
          ))}
        </div>
      </div>
    );
  }

  const categories = summary?.categories ?? [];
  const hasVoice = voiceProfile && voiceProfile.total_samples > 0;
  const hasAvatar = avatarInfo != null;
  const isEmpty = categories.length === 0 && !hasVoice && !hasAvatar;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HardDrive className="h-5 w-5 text-muted-foreground" />
          <h3 className="text-lg font-semibold">My Content</h3>
          {summary && summary.total_files > 0 && (
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">
              {summary.total_files} files &middot;{" "}
              {formatFileSize(summary.total_size_bytes)}
            </span>
          )}
        </div>
        <button
          onClick={loadSummary}
          className="rounded-md p-2 text-muted-foreground hover:bg-muted transition-colors"
          title="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Training data badges */}
      {(hasVoice || hasAvatar) && (
        <div className="flex flex-wrap gap-2">
          {hasVoice && (
            <div className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs">
              <Mic2 className="h-3 w-3 text-indigo-500" />
              <span>
                {voiceProfile.total_samples} voice samples &middot;{" "}
                {Math.round(voiceProfile.total_duration_seconds)}s
              </span>
              <span
                className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                  voiceProfile.cloning_status === "ready"
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                    : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300"
                }`}
              >
                {voiceProfile.cloning_status}
              </span>
            </div>
          )}
          {hasAvatar && (
            <div className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs">
              <ScanFace className="h-3 w-3 text-pink-500" />
              <span>Face calibration</span>
              <span
                className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                  avatarInfo.has_calibration_video
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {avatarInfo.has_calibration_video ? "recorded" : avatarInfo.face_scan_status || "none"}
              </span>
            </div>
          )}
        </div>
      )}

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16">
          <Folder className="h-12 w-12 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">
            No content uploaded yet
          </p>
          <p className="mt-1 text-xs text-muted-foreground/60">
            Upload videos, audio, PDFs, or text from the Ingest page
          </p>
        </div>
      ) : (
        <>
          {/* Category tabs - Instagram style */}
          <div className="flex gap-1 border-b overflow-x-auto pb-px">
            {categories.map((cat) => {
              const meta = getCategoryMeta(cat.category);
              const Icon = meta.icon;
              const isActive = activeCategory === cat.category;
              return (
                <button
                  key={cat.category}
                  onClick={() => switchCategory(cat.category)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium uppercase tracking-wider border-b-2 -mb-px transition-colors whitespace-nowrap ${
                    isActive
                      ? "border-foreground text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {meta.label}
                  <span className="text-[10px] opacity-60">{cat.count}</span>
                </button>
              );
            })}
          </div>

          {/* Content grid */}
          {gridLoading ? (
            <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-4 md:grid-cols-5">
              {Array.from({ length: 10 }).map((_, i) => (
                <div
                  key={i}
                  className="aspect-square animate-pulse rounded-md bg-muted"
                />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Folder className="h-8 w-8 text-muted-foreground/30 mb-2" />
              <p className="text-xs text-muted-foreground">
                No files in this category
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-4 md:grid-cols-5">
              {items.map((item) => (
                <GridTile
                  key={item.ingestion_id}
                  item={item}
                  onPreview={() => setPreviewItem(item)}
                  onDelete={() => setDeleteTarget(item)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Preview modal */}
      {previewItem && (
        <PreviewModal
          item={previewItem}
          onClose={() => setPreviewItem(null)}
          onDelete={() => {
            setPreviewItem(null);
            setDeleteTarget(previewItem);
          }}
        />
      )}

      {/* Delete confirmation dialog */}
      {deleteTarget && (
        <DeleteDialog
          item={deleteTarget}
          deleting={deleting}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Grid tile (Instagram-style square)
// ---------------------------------------------------------------------------

function GridTile({
  item,
  onPreview,
  onDelete,
}: {
  item: ContentItem;
  onPreview: () => void;
  onDelete: () => void;
}) {
  const meta = getCategoryMeta(item.category);
  const Icon = meta.icon;
  const token = getAuthToken();
  const thumbUrl = item.has_thumbnail
    ? `${getThumbnailUrl(item.ingestion_id)}${token ? `?_token=${token}` : ""}`
    : null;

  return (
    <div className="group relative aspect-square overflow-hidden rounded-md bg-muted cursor-pointer">
      {/* Thumbnail / icon fallback */}
      {thumbUrl ? (
        <img
          src={thumbUrl}
          alt={item.filename}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center gap-1 p-2">
          <Icon className={`h-8 w-8 ${meta.color} opacity-60`} />
          <p className="text-[10px] text-center text-muted-foreground truncate max-w-full px-1">
            {item.filename}
          </p>
          <span className="rounded bg-muted-foreground/10 px-1.5 py-0.5 text-[9px] font-mono uppercase text-muted-foreground">
            {item.extension}
          </span>
        </div>
      )}

      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-colors flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPreview();
          }}
          className="rounded-full bg-white/90 p-2 text-gray-800 hover:bg-white transition-colors shadow-sm"
          title="Preview"
        >
          <Eye className="h-4 w-4" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="rounded-full bg-white/90 p-2 text-red-600 hover:bg-white transition-colors shadow-sm"
          title="Delete"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {/* Category badge */}
      {item.category === "video" && (
        <div className="absolute bottom-1 right-1 rounded bg-black/60 px-1 py-0.5 flex items-center gap-0.5">
          <Play className="h-2.5 w-2.5 text-white fill-white" />
          <span className="text-[9px] text-white font-medium">
            {formatFileSize(item.size_bytes)}
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Preview modal
// ---------------------------------------------------------------------------

function PreviewModal({
  item,
  onClose,
  onDelete,
}: {
  item: ContentItem;
  onClose: () => void;
  onDelete: () => void;
}) {
  const [textContent, setTextContent] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const token = getAuthToken();
  const fileUrl = getFileUrl(item.ingestion_id);
  const authFileUrl = token
    ? `${fileUrl}?_token=${token}`
    : fileUrl;

  useEffect(() => {
    if (["text", "document"].includes(item.category) || item.extension === "csv" || item.extension === "md") {
      setLoadingPreview(true);
      fetchTextPreview(item.ingestion_id)
        .then((data) => setTextContent(data.preview_text))
        .catch(() => setTextContent("(Unable to load preview)"))
        .finally(() => setLoadingPreview(false));
    }
  }, [item]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const renderContent = () => {
    if (item.category === "video") {
      return (
        <video
          controls
          autoPlay
          className="max-h-[70vh] max-w-full rounded-lg"
          src={authFileUrl}
        >
          Your browser does not support video playback.
        </video>
      );
    }
    if (item.category === "audio") {
      return (
        <div className="flex flex-col items-center gap-4 p-8">
          <Headphones className="h-16 w-16 text-blue-500 opacity-40" />
          <p className="text-sm font-medium">{item.filename}</p>
          <audio controls src={authFileUrl} className="w-full max-w-md" />
        </div>
      );
    }
    if (item.category === "pdf") {
      return (
        <iframe
          src={authFileUrl}
          className="h-[70vh] w-full max-w-3xl rounded-lg bg-white"
          title={item.filename}
        />
      );
    }
    if (textContent !== null || loadingPreview) {
      return (
        <div className="w-full max-w-2xl rounded-lg border bg-card p-6 max-h-[70vh] overflow-y-auto">
          {loadingPreview ? (
            <div className="animate-pulse space-y-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-4 rounded bg-muted" />
              ))}
            </div>
          ) : (
            <pre className="whitespace-pre-wrap text-sm font-mono leading-relaxed text-foreground">
              {textContent}
            </pre>
          )}
        </div>
      );
    }
    return (
      <div className="flex flex-col items-center gap-3 p-8">
        <FileText className="h-16 w-16 text-muted-foreground opacity-40" />
        <p className="text-sm">Preview not available for this file type</p>
      </div>
    );
  };

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="relative flex flex-col items-center gap-3 max-w-[90vw]">
        {/* Top bar */}
        <div className="flex w-full items-center justify-between rounded-t-lg bg-card/90 backdrop-blur-sm px-4 py-2.5 border-b">
          <div className="flex items-center gap-2 min-w-0">
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono uppercase">
              {item.extension}
            </span>
            <p className="text-sm font-medium truncate">{item.filename}</p>
            <span className="text-xs text-muted-foreground">
              {formatFileSize(item.size_bytes)}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0 ml-2">
            <a
              href={authFileUrl}
              download={item.filename}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted transition-colors"
              title="Download"
            >
              <Download className="h-4 w-4" />
            </a>
            <button
              onClick={onDelete}
              className="rounded-md p-1.5 text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </button>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted transition-colors"
              title="Close (Esc)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        {renderContent()}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Delete confirmation dialog
// ---------------------------------------------------------------------------

function DeleteDialog({
  item,
  deleting,
  onConfirm,
  onCancel,
}: {
  item: ContentItem;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onCancel]);

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === overlayRef.current) onCancel();
      }}
    >
      <div className="w-full max-w-sm rounded-xl bg-card border shadow-xl p-6 space-y-4">
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-red-100 dark:bg-red-900/30 p-2.5 shrink-0">
            <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <h3 className="text-base font-semibold">Delete file?</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Are you sure you want to permanently delete{" "}
              <span className="font-medium text-foreground">
                &quot;{item.filename}&quot;
              </span>
              ? This action cannot be undone.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={deleting}
            className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            {deleting ? (
              <>
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Deleting...
              </>
            ) : (
              <>
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
