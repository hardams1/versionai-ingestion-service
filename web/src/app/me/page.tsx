"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  Globe,
  Lock,
  Pencil,
  ShieldOff,
  UserCheck,
  UserX,
  Users,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { NavHeader } from "@/components/layout/nav-header";
import { Button } from "@/components/ui/button";
import {
  type SocialProfile,
  type FollowerItem,
  type FollowRequestItem,
  fetchMySocialProfile,
  getFollowers,
  getFollowing,
  getPendingRequests,
  handleFollowRequest,
  unfollowUser,
} from "@/lib/social-api";

const ACCESS_BADGES: Record<
  string,
  { label: string; icon: typeof Globe; className: string }
> = {
  public: {
    label: "Public AI",
    icon: Globe,
    className:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  },
  followers_only: {
    label: "Followers Only",
    icon: Lock,
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  },
  no_one: {
    label: "Private AI",
    icon: ShieldOff,
    className:
      "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  },
};

type Tab = "followers" | "following" | "requests";

export default function MyProfilePage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  const [profile, setProfile] = useState<SocialProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("followers");
  const [followers, setFollowers] = useState<FollowerItem[]>([]);
  const [following, setFollowing] = useState<FollowerItem[]>([]);
  const [requests, setRequests] = useState<FollowRequestItem[]>([]);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      const p = await fetchMySocialProfile();
      setProfile(p);
    } catch {
      toast.error("Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadConnections = useCallback(async () => {
    if (!user) return;
    try {
      const [frs, fing] = await Promise.all([
        getFollowers(user.user_id),
        getFollowing(user.user_id),
      ]);
      setFollowers(frs.items);
      setFollowing(fing.items);
    } catch {
      /* silently fail */
    }
  }, [user]);

  const loadRequests = useCallback(async () => {
    try {
      const data = await getPendingRequests();
      setRequests(data.items);
    } catch {
      /* silently fail */
    }
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    loadProfile();
    loadConnections();
    loadRequests();
  }, [user, authLoading, loadProfile, loadConnections, loadRequests]);

  const onAccept = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      await handleFollowRequest(requestId, "accept");
      toast.success("Request accepted");
      await Promise.all([loadRequests(), loadProfile(), loadConnections()]);
    } catch {
      toast.error("Failed to accept request");
    } finally {
      setActionLoading(null);
    }
  };

  const onReject = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      await handleFollowRequest(requestId, "reject");
      toast.success("Request rejected");
      await loadRequests();
    } catch {
      toast.error("Failed to reject request");
    } finally {
      setActionLoading(null);
    }
  };

  const onRemoveFollower = async (userId: string) => {
    setActionLoading(userId);
    try {
      await unfollowUser(userId);
      toast.success("Removed follower");
      await Promise.all([loadProfile(), loadConnections()]);
    } catch {
      toast.error("Failed to remove");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading || authLoading) {
    return (
      <>
        <NavHeader />
        <main className="mx-auto max-w-3xl px-6 py-12">
          <div className="animate-pulse space-y-6">
            <div className="flex items-start gap-6">
              <div className="h-24 w-24 rounded-full bg-muted" />
              <div className="flex-1 space-y-3">
                <div className="h-7 w-48 rounded bg-muted" />
                <div className="h-4 w-32 rounded bg-muted" />
                <div className="h-4 w-64 rounded bg-muted" />
              </div>
            </div>
            <div className="h-10 w-full rounded bg-muted" />
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 rounded-lg bg-muted" />
              ))}
            </div>
          </div>
        </main>
      </>
    );
  }

  if (!profile) {
    return (
      <>
        <NavHeader />
        <main className="mx-auto max-w-3xl px-6 py-12 text-center">
          <p className="text-muted-foreground">
            Could not load your profile. Try again later.
          </p>
        </main>
      </>
    );
  }

  const badge = ACCESS_BADGES[profile.ai_access_level] ?? ACCESS_BADGES.public;
  const BadgeIcon = badge.icon;

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "followers", label: "Followers", count: profile.followers_count },
    { key: "following", label: "Following", count: profile.following_count },
    { key: "requests", label: "Requests", count: requests.length },
  ];

  return (
    <>
      <NavHeader />
      <main className="mx-auto max-w-3xl px-6 py-8">
        {/* Profile header */}
        <div className="flex items-start gap-6">
          <div className="h-24 w-24 shrink-0 rounded-full bg-muted flex items-center justify-center text-3xl font-bold text-muted-foreground overflow-hidden">
            {profile.image_url ? (
              <img
                src={profile.image_url}
                alt=""
                className="h-full w-full object-cover"
              />
            ) : (
              (profile.username?.[0] ?? "?").toUpperCase()
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold truncate">
                {profile.full_name || profile.username || "Anonymous"}
              </h1>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.className}`}
              >
                <BadgeIcon className="h-3 w-3" />
                {badge.label}
              </span>
              {profile.is_private && (
                <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                  <Lock className="h-3 w-3" />
                  Private
                </span>
              )}
            </div>

            {profile.username && (
              <p className="text-sm text-muted-foreground mt-0.5">
                @{profile.username}
              </p>
            )}
            {profile.bio && (
              <p className="mt-2 text-sm leading-relaxed">{profile.bio}</p>
            )}

            {/* Stats */}
            <div className="mt-4 flex items-center gap-6 text-sm">
              <button
                onClick={() => setTab("followers")}
                className="hover:underline"
              >
                <span className="font-semibold">{profile.followers_count}</span>{" "}
                <span className="text-muted-foreground">Followers</span>
              </button>
              <button
                onClick={() => setTab("following")}
                className="hover:underline"
              >
                <span className="font-semibold">{profile.following_count}</span>{" "}
                <span className="text-muted-foreground">Following</span>
              </button>
              {requests.length > 0 && (
                <button
                  onClick={() => setTab("requests")}
                  className="hover:underline"
                >
                  <span className="font-semibold">{requests.length}</span>{" "}
                  <span className="text-muted-foreground">Pending</span>
                </button>
              )}
            </div>

            <div className="mt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push("/settings")}
              >
                <Pencil className="mr-1.5 h-4 w-4" /> Edit Profile
              </Button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="mt-10">
          <div className="flex border-b">
            {tabs.map((t) => (
              <button
                key={t.key}
                className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                  tab === t.key
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setTab(t.key)}
              >
                {t.label}
                {t.count > 0 && (
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    {t.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="mt-4 space-y-1">
            {/* Followers tab */}
            {tab === "followers" &&
              (followers.length === 0 ? (
                <EmptyState message="No followers yet" />
              ) : (
                followers.map((item) => (
                  <UserRow
                    key={item.user_id}
                    item={item}
                    onClick={() => router.push(`/profile/${item.user_id}`)}
                  />
                ))
              ))}

            {/* Following tab */}
            {tab === "following" &&
              (following.length === 0 ? (
                <EmptyState message="Not following anyone yet" />
              ) : (
                following.map((item) => (
                  <UserRow
                    key={item.user_id}
                    item={item}
                    onClick={() => router.push(`/profile/${item.user_id}`)}
                    trailing={
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title="Unfollow"
                        disabled={actionLoading === item.user_id}
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveFollower(item.user_id);
                        }}
                      >
                        <UserX className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    }
                  />
                ))
              ))}

            {/* Requests tab */}
            {tab === "requests" &&
              (requests.length === 0 ? (
                <EmptyState message="No pending follow requests" />
              ) : (
                requests.map((req) => (
                  <div
                    key={req.id}
                    className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-muted/50 transition-colors"
                  >
                    <button
                      onClick={() =>
                        router.push(`/profile/${req.requester_id}`)
                      }
                      className="flex items-center gap-3 flex-1 min-w-0 text-left"
                    >
                      <Avatar
                        imageUrl={req.image_url}
                        name={req.username}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">
                          {req.full_name || req.username || "Unknown"}
                        </p>
                        {req.username && (
                          <p className="text-xs text-muted-foreground truncate">
                            @{req.username}
                          </p>
                        )}
                      </div>
                    </button>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        className="text-green-600 hover:bg-green-100 dark:hover:bg-green-900/30"
                        disabled={actionLoading === req.id}
                        onClick={() => onAccept(req.id)}
                        title="Accept"
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        className="text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30"
                        disabled={actionLoading === req.id}
                        onClick={() => onReject(req.id)}
                        title="Reject"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))
              ))}
          </div>
        </div>
      </main>
    </>
  );
}

function Avatar({
  imageUrl,
  name,
  size = "sm",
}: {
  imageUrl?: string | null;
  name?: string | null;
  size?: "sm" | "lg";
}) {
  const dim = size === "lg" ? "h-24 w-24 text-3xl" : "h-9 w-9 text-sm";
  return (
    <div
      className={`${dim} shrink-0 rounded-full bg-muted flex items-center justify-center font-medium text-muted-foreground overflow-hidden`}
    >
      {imageUrl ? (
        <img
          src={imageUrl}
          alt=""
          className="h-full w-full rounded-full object-cover"
        />
      ) : (
        (name?.[0] ?? "?").toUpperCase()
      )}
    </div>
  );
}

function UserRow({
  item,
  onClick,
  trailing,
}: {
  item: FollowerItem;
  onClick: () => void;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-muted/50 transition-colors">
      <button
        onClick={onClick}
        className="flex items-center gap-3 flex-1 min-w-0 text-left"
      >
        <Avatar imageUrl={item.image_url} name={item.username} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate">
            {item.full_name || item.username || "Anonymous"}
          </p>
          {item.username && (
            <p className="text-xs text-muted-foreground truncate">
              @{item.username}
            </p>
          )}
        </div>
      </button>
      <div className="flex items-center gap-2 shrink-0">
        {item.is_mutual && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <UserCheck className="h-3 w-3" /> Mutual
          </span>
        )}
        {trailing}
      </div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <Users className="h-10 w-10 text-muted-foreground/40 mb-3" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
