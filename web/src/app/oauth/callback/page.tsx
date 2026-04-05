"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { exchangeOAuthCode } from "@/lib/social-ingestion-api";

function OAuthCallbackInner() {
  const params = useSearchParams();
  const [status, setStatus] = useState<"processing" | "success" | "error">("processing");
  const [message, setMessage] = useState("Completing authorization...");
  const exchangedRef = useRef(false);

  useEffect(() => {
    if (exchangedRef.current) return;
    exchangedRef.current = true;

    const code = params.get("code");
    const state = params.get("state");
    const platform = params.get("platform");

    if (!code || !state) {
      setStatus("error");
      setMessage("Authorization failed — missing parameters. Please close this window and try again.");
      return;
    }

    exchangeOAuthCode(code, state, platform ?? "")
      .then((result) => {
        setStatus("success");
        setMessage(
          `${result.platform_username ? `@${result.platform_username} on ` : ""}${result.platform} connected successfully!`
        );

        if (window.opener) {
          window.opener.postMessage(
            { type: "versionai_oauth_complete", platform: result.platform, success: true },
            window.location.origin
          );
          setTimeout(() => window.close(), 1500);
        }
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Authorization failed. Please close this window and try again.");

        if (window.opener) {
          window.opener.postMessage(
            { type: "versionai_oauth_complete", success: false },
            window.location.origin
          );
        }
      });
  }, [params]);

  const isOpener = typeof window !== "undefined" && !!window.opener;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-xl border bg-card p-8 shadow-lg text-center space-y-4">
        {status === "processing" && (
          <>
            <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
            <h2 className="text-lg font-semibold">Connecting your account</h2>
          </>
        )}
        {status === "success" && (
          <>
            <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto" />
            <h2 className="text-lg font-semibold text-emerald-700 dark:text-emerald-400">Connected!</h2>
          </>
        )}
        {status === "error" && (
          <>
            <XCircle className="h-10 w-10 text-destructive mx-auto" />
            <h2 className="text-lg font-semibold text-destructive">Connection Failed</h2>
          </>
        )}
        <p className="text-sm text-muted-foreground">{message}</p>
        {status !== "processing" && (
          <p className="text-xs text-muted-foreground">
            {isOpener ? "This window will close automatically." : "You can close this tab and return to VersionAI."}
          </p>
        )}
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <OAuthCallbackInner />
    </Suspense>
  );
}
