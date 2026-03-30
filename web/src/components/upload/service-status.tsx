"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, XCircle } from "lucide-react";
import { checkHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ServiceStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function check() {
      try {
        const data = await checkHealth();
        if (mounted) {
          setHealth(data);
          setError(false);
        }
      } catch {
        if (mounted) setError(true);
      }
    }

    check();
    const interval = setInterval(check, 30_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const isOnline = health && !error;

  return (
    <div className="flex items-center gap-2 text-sm">
      <Activity className="h-4 w-4 text-muted-foreground" />
      <span className="text-muted-foreground">Ingestion API:</span>
      {isOnline ? (
        <span className="flex items-center gap-1 text-emerald-600">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Online
          <span className="text-muted-foreground ml-1">v{health.version}</span>
        </span>
      ) : (
        <span className={cn("flex items-center gap-1", error ? "text-destructive" : "text-muted-foreground")}>
          {error ? (
            <>
              <XCircle className="h-3.5 w-3.5" />
              Offline
            </>
          ) : (
            "Checking..."
          )}
        </span>
      )}
    </div>
  );
}
