"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Globe,
  Lock,
  Search,
  ShieldOff,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { NavHeader } from "@/components/layout/nav-header";
import { Button } from "@/components/ui/button";
import {
  type SearchResult,
  getSuggestedUsers,
  getTrendingUsers,
  searchUsers,
} from "@/lib/social-api";

type Tab = "search" | "suggested" | "trending";

const ACCESS_ICON: Record<string, typeof Globe> = {
  public: Globe,
  followers_only: Lock,
  no_one: ShieldOff,
};

function UserCard({ user, onClick }: { user: SearchResult; onClick: () => void }) {
  const Icon = ACCESS_ICON[user.ai_access_level] ?? Globe;

  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-4 rounded-xl border bg-card p-4 text-left transition-all hover:shadow-md hover:border-primary/30"
    >
      <div className="h-12 w-12 shrink-0 rounded-full bg-muted flex items-center justify-center text-lg font-semibold text-muted-foreground overflow-hidden">
        {user.image_url ? (
          <img src={user.image_url} alt="" className="h-full w-full object-cover" />
        ) : (
          (user.username?.[0] ?? "?").toUpperCase()
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold truncate">
            {user.full_name || user.username || "Anonymous"}
          </p>
          {user.is_private && (
            <Lock className="h-3 w-3 text-muted-foreground shrink-0" />
          )}
        </div>
        {user.username && (
          <p className="text-xs text-muted-foreground truncate">@{user.username}</p>
        )}
        {user.bio && (
          <p className="mt-1 text-xs text-muted-foreground line-clamp-1">{user.bio}</p>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <span className="text-xs text-muted-foreground">
          {user.followers_count} followers
        </span>
        <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
          <Icon className="h-3 w-3" />
          {user.ai_access_level === "public"
            ? "Public AI"
            : user.ai_access_level === "followers_only"
              ? "Followers only"
              : "Private AI"}
        </span>
      </div>
    </button>
  );
}

export default function DiscoverPage() {
  const { user } = useAuth();
  const router = useRouter();

  const [tab, setTab] = useState<Tab>("suggested");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const loadSuggested = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSuggestedUsers();
      setResults(data.items);
    } catch {
      toast.error("Failed to load suggestions");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTrending = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTrendingUsers();
      setResults(data.items);
    } catch {
      toast.error("Failed to load trending");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await searchUsers(query.trim());
      setResults(data.items);
    } catch {
      toast.error("Search failed");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    if (tab === "suggested") loadSuggested();
    else if (tab === "trending") loadTrending();
    else setResults([]);
  }, [tab, loadSuggested, loadTrending]);

  const TABS: { key: Tab; label: string; icon: typeof Users }[] = [
    { key: "search", label: "Search", icon: Search },
    { key: "suggested", label: "Suggested", icon: Sparkles },
    { key: "trending", label: "Trending", icon: TrendingUp },
  ];

  return (
    <>
      <NavHeader />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <h1 className="text-2xl font-bold">Discover</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Find people and interact with their AI
        </p>

        {/* Tabs */}
        <div className="mt-6 flex border-b">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === key
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Search bar */}
        {tab === "search" && (
          <div className="mt-4 flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="Search by username or name..."
                className="w-full rounded-lg border bg-background py-2.5 pl-10 pr-4 text-sm outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <Button onClick={handleSearch} disabled={loading || !query.trim()}>
              Search
            </Button>
          </div>
        )}

        {/* Results */}
        <div className="mt-6 space-y-3">
          {loading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-20 animate-pulse rounded-xl border bg-muted" />
              ))}
            </div>
          ) : results.length === 0 ? (
            <p className="py-16 text-center text-sm text-muted-foreground">
              {tab === "search"
                ? query
                  ? "No users found"
                  : "Type a name or username to search"
                : "No users to show yet"}
            </p>
          ) : (
            results.map((u) => (
              <UserCard
                key={u.user_id}
                user={u}
                onClick={() => router.push(`/profile/${u.user_id}`)}
              />
            ))
          )}
        </div>
      </main>
    </>
  );
}
