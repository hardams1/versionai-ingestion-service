import Link from "next/link";
import { Upload, MessageSquare, Radio } from "lucide-react";
import { NavHeader } from "@/components/layout/nav-header";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <NavHeader />

      <main className="flex-1 flex items-center justify-center">
        <div className="mx-auto max-w-3xl px-6 py-16 text-center">
          <div className="mb-3 flex justify-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground font-bold text-2xl">
              V
            </div>
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Welcome to VersionAI
          </h1>
          <p className="mt-3 text-lg text-muted-foreground max-w-xl mx-auto">
            Upload your data, ask questions, and get real-time AI-powered
            responses with generated audio and video.
          </p>

          <div className="mt-10 grid gap-5 sm:grid-cols-3">
            <Link
              href="/ingest"
              className="group flex flex-col items-center gap-3 rounded-xl border p-6 transition-colors hover:bg-muted/50"
            >
              <Upload className="h-8 w-8 text-muted-foreground group-hover:text-foreground transition-colors" />
              <div>
                <h3 className="font-semibold">Ingest Data</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Upload video, audio, text, and PDF files for AI processing.
                </p>
              </div>
            </Link>

            <Link
              href="/chat"
              className="group flex flex-col items-center gap-3 rounded-xl border p-6 transition-colors hover:bg-muted/50"
            >
              <MessageSquare className="h-8 w-8 text-muted-foreground group-hover:text-foreground transition-colors" />
              <div>
                <h3 className="font-semibold">Ask VersionAI</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Ask questions and receive text, audio, and video responses.
                </p>
              </div>
            </Link>

            <div className="flex flex-col items-center gap-3 rounded-xl border p-6 opacity-80">
              <Radio className="h-8 w-8 text-muted-foreground" />
              <div>
                <h3 className="font-semibold">6 Microservices</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Ingestion, Processing, Brain, Voice, Video Avatar, and
                  Real-Time Orchestrator.
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t py-6">
        <div className="mx-auto max-w-5xl px-6 text-center text-xs text-muted-foreground">
          VersionAI &middot; Ingestion &middot; Processing &middot; AI Brain
          &middot; Voice &middot; Video Avatar &middot; RT Orchestrator
        </div>
      </footer>
    </div>
  );
}
