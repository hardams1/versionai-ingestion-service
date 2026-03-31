import { UploadPanel } from "@/components/upload/upload-panel";
import { ServiceStatus } from "@/components/upload/service-status";
import { Separator } from "@/components/ui/separator";
import { NavHeader } from "@/components/layout/nav-header";

export default function IngestPage() {
  return (
    <div className="flex flex-1 flex-col">
      <NavHeader />

      <main className="flex-1">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <div className="mb-8 flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">File Ingestion</h2>
              <p className="mt-1 text-muted-foreground">
                Upload files to the VersionAI pipeline for automated AI processing —
                transcription, frame extraction, OCR, and embeddings.
              </p>
            </div>
            <ServiceStatus />
          </div>

          <UploadPanel />

          <Separator className="my-10" />

          <section className="grid gap-6 sm:grid-cols-3">
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">Video & Audio</h3>
              <p className="text-sm text-muted-foreground">
                Automatically transcribed with Whisper. Video also gets frame
                extraction via FFmpeg.
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">PDF & Documents</h3>
              <p className="text-sm text-muted-foreground">
                Processed through OCR and text embedding pipelines for
                semantic search and retrieval.
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">Text & CSV</h3>
              <p className="text-sm text-muted-foreground">
                Directly embedded for vector search, enabling fast similarity
                lookups across your data.
              </p>
            </div>
          </section>
        </div>
      </main>

      <footer className="border-t py-6">
        <div className="mx-auto max-w-4xl px-6 text-center text-xs text-muted-foreground">
          VersionAI Ingestion Service &middot; Files are validated, stored in S3, and queued for processing.
        </div>
      </footer>
    </div>
  );
}
