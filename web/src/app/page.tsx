import { UploadPanel } from "@/components/upload/upload-panel";
import { ServiceStatus } from "@/components/upload/service-status";
import { Separator } from "@/components/ui/separator";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-sm">
              V
            </div>
            <div>
              <h1 className="text-base font-semibold leading-tight">VersionAI</h1>
              <p className="text-xs text-muted-foreground">Ingestion Portal</p>
            </div>
          </div>
          <ServiceStatus />
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <div className="mb-8">
            <h2 className="text-2xl font-bold tracking-tight">File Ingestion</h2>
            <p className="mt-1 text-muted-foreground">
              Upload files to the VersionAI pipeline for automated AI processing —
              transcription, frame extraction, OCR, and embeddings.
            </p>
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
