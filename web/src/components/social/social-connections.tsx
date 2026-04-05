"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Link2,
  Link2Off,
  Loader2,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import {
  type AccountStatus,
  checkSocialIngestionHealth,
  deletePlatformData,
  disconnectPlatform,
  fetchConnectedAccounts,
  initOAuth,
  syncAll,
  syncPlatform,
} from "@/lib/social-ingestion-api";

const PLATFORM_META: Record<
  string,
  { label: string; color: string; icon: string }
> = {
  twitter: { label: "Twitter (X)", color: "bg-sky-500", icon: "𝕏" },
  facebook: { label: "Facebook", color: "bg-blue-600", icon: "f" },
  instagram: { label: "Instagram", color: "bg-gradient-to-br from-purple-500 to-pink-500", icon: "IG" },
  tiktok: { label: "TikTok", color: "bg-black", icon: "♪" },
  snapchat: { label: "Snapchat", color: "bg-yellow-400", icon: "👻" },
};

export function SocialConnections() {
  const { user, isLoading: authLoading } = useAuth();
  const [accounts, setAccounts] = useState<AccountStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [online, setOnline] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const loadAccounts = useCallback(async () => {
    try {
      const data = await fetchConnectedAccounts();
      setAccounts(data);
    } catch {
      /* service may be offline */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSocialIngestionHealth().then(setOnline);
  }, []);

  useEffect(() => {
    if (authLoading || !user || !online) {
      setLoading(false);
      return;
    }
    loadAccounts();
  }, [user, authLoading, online, loadAccounts]);

  const handleConnect = useCallback(async (platform: string) => {
    setConnecting(platform);
    try {
      const { authorization_url } = await initOAuth(platform);

      const w = 500, h = 700;
      const left = window.screenX + (window.outerWidth - w) / 2;
      const top = window.screenY + (window.outerHeight - h) / 2;
      const popup = window.open(
        authorization_url,
        `versionai_oauth_${platform}`,
        `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no,location=yes`
      );

      const onMessage = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return;
        if (event.data?.type === "versionai_oauth_complete") {
          window.removeEventListener("message", onMessage);
          setConnecting(null);
          if (event.data.success) {
            toast.success(`${PLATFORM_META[platform]?.label ?? platform} connected!`);
            loadAccounts();
          } else {
            toast.error("Authorization was not completed");
          }
        }
      };
      window.addEventListener("message", onMessage);

      const pollClosed = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(pollClosed);
          setTimeout(() => {
            window.removeEventListener("message", onMessage);
            setConnecting(null);
            loadAccounts();
          }, 500);
        }
      }, 500);

    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start authorization");
      setConnecting(null);
    }
  }, [loadAccounts]);

  const handleDisconnect = async (platform: string) => {
    try {
      await disconnectPlatform(platform);
      toast.success(`${PLATFORM_META[platform]?.label} disconnected`);
      await loadAccounts();
    } catch {
      toast.error("Failed to disconnect");
    }
  };

  const handleSync = async (platform: string) => {
    setSyncing(platform);
    try {
      const result = await syncPlatform(platform);
      toast.success(result.message);
      await loadAccounts();
    } catch {
      toast.error("Sync failed");
    } finally {
      setSyncing(null);
    }
  };

  const handleSyncAll = async () => {
    setSyncing("all");
    try {
      await syncAll();
      toast.success("Syncing all connected platforms...");
      setTimeout(loadAccounts, 3000);
    } catch {
      toast.error("Sync failed");
    } finally {
      setSyncing(null);
    }
  };

  const handleDelete = async (platform: string) => {
    try {
      const result = await deletePlatformData(platform);
      toast.success(`Deleted ${result.items_deleted} items from ${PLATFORM_META[platform]?.label}`);
      setConfirmDelete(null);
      await loadAccounts();
    } catch {
      toast.error("Failed to delete data");
    }
  };

  if (!online) return null;

  const connected = accounts.filter((a) => a.is_connected);

  return (
    <div className="space-y-4">
      {connected.length > 0 && (
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={handleSyncAll}
            disabled={syncing !== null}
          >
            {syncing === "all" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
            )}
            Sync All
          </Button>
        </div>
      )}

      <div className="space-y-2">
        {accounts.map((account) => {
          const meta = PLATFORM_META[account.platform] ?? {
            label: account.platform,
            color: "bg-gray-500",
            icon: "?",
          };

          return (
            <div
              key={account.platform}
              className="flex items-center gap-3 rounded-lg border px-4 py-3"
            >
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-white text-sm font-bold ${meta.color}`}
              >
                {meta.icon}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium">{meta.label}</p>
                  {account.is_connected && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 dark:bg-green-900/30 px-2 py-0.5 text-[10px] font-medium text-green-700 dark:text-green-300">
                      Connected
                    </span>
                  )}
                </div>
                {account.is_connected ? (
                  <div className="text-xs text-muted-foreground space-x-3">
                    {account.platform_username && (
                      <span>@{account.platform_username}</span>
                    )}
                    <span>{account.items_ingested} items</span>
                    {account.last_sync_at && (
                      <span>
                        Synced {new Date(account.last_sync_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">Not connected</p>
                )}
              </div>

              <div className="flex items-center gap-1 shrink-0">
                {account.is_connected ? (
                  <>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title="Sync now"
                      disabled={syncing !== null}
                      onClick={() => handleSync(account.platform)}
                    >
                      {syncing === account.platform ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title="Disconnect"
                      onClick={() => handleDisconnect(account.platform)}
                    >
                      <Link2Off className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title="Delete all data"
                      className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                      onClick={() => setConfirmDelete(account.platform)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </>
                ) : (
                  <Button
                    size="sm"
                    disabled={connecting !== null}
                    onClick={() => handleConnect(account.platform)}
                  >
                    {connecting === account.platform ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                    ) : (
                      <Link2 className="h-3.5 w-3.5 mr-1" />
                    )}
                    {connecting === account.platform ? "Authorizing..." : "Connect"}
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {loading && (
        <div className="flex justify-center py-6">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Delete Confirmation */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-xl border bg-card p-6 shadow-xl mx-4">
            <h4 className="text-lg font-semibold mb-2">Delete Data?</h4>
            <p className="text-sm text-muted-foreground mb-4">
              This will permanently delete all ingested data from{" "}
              {PLATFORM_META[confirmDelete]?.label} and disconnect the account.
              This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmDelete(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => handleDelete(confirmDelete)}
              >
                <Trash2 className="h-4 w-4 mr-1" /> Delete All Data
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
