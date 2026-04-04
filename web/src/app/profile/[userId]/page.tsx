"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Globe,
  Lock,
  ShieldOff,
  UserCheck,
  UserPlus,
  UserX,
  Users,
  Clock,
  MessageSquare,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { NavHeader } from "@/components/layout/nav-header";
import { Button } from "@/components/ui/button";
import {
  type SocialProfile,
  type FollowerItem,
  fetchSocialProfile,
  followUser,
  unfollowUser,
  getFollowers,
  getFollowing,
} from "@/lib/social-api";

const ACCESS_BADGES: Record<string, { label: string; icon: typeof Globe; className: string }> = {
  public: { label: "Public AI", icon: Globe, className: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" },
  followers_only: { label: "Followers Only", icon: Lock, className: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300" },
  no_one: { label: "Private AI", icon: ShieldOff, className: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300" },
};

export default function ProfilePage() {
  const params = useParams();
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();
  const userId = params.userId as string;

  const [profile, setProfile] = useState<SocialProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [tab, setTab] = useState<"followers" | "following">("followers");
  const [followers, setFollowers] = useState<FollowerItem[]>([]);
  const [following, setFollowing] = useState<FollowerItem[]>([]);

  const isOwnProfile = user?.user_id === userId;

  const loadProfile = useCallback(async () => {
    try {
      const p = await fetchSocialProfile(userId);
      setProfile(p);
    } catch {
      toast.error("Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const loadConnections = useCallback(async () => {
    try {
      const [frs, fing] = await Promise.all([
        getFollowers(userId),
        getFollowing(userId),
      ]);
      setFollowers(frs.items);
      setFollowing(fing.items);
    } catch {
      /* ignore */
    }
  }, [userId]);

  useEffect(() => {
    if (authLoading || !user) return;
    loadProfile();
    loadConnections();
  }, [user, authLoading, loadProfile, loadConnections]);

  const handleFollow = async () => {
    if (!profile) return;
    setActionLoading(true);
    try {
      const res = await followUser(userId);
      toast.success(res.message);
      await loadProfile();
    } catch {
      toast.error("Follow failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleUnfollow = async () => {
    if (!profile) return;
    setActionLoading(true);
    try {
      const res = await unfollowUser(userId);
      toast.success(res.message);
      await loadProfile();
    } catch {
      toast.error("Unfollow failed");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <>
        <NavHeader />
        <main className="mx-auto max-w-3xl px-6 py-12">
          <div className="animate-pulse space-y-4">
            <div className="h-24 w-24 rounded-full bg-muted" />
            <div className="h-6 w-48 rounded bg-muted" />
            <div className="h-4 w-64 rounded bg-muted" />
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
          <p className="text-muted-foreground">User not found</p>
          <Button variant="ghost" className="mt-4" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Go back
          </Button>
        </main>
      </>
    );
  }

  const badge = ACCESS_BADGES[profile.ai_access_level] ?? ACCESS_BADGES.public;
  const BadgeIcon = badge.icon;

  return (
    <>
      <NavHeader />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <Button variant="ghost" size="sm" onClick={() => router.back()} className="mb-6">
          <ArrowLeft className="mr-1.5 h-4 w-4" /> Back
        </Button>

        {/* Profile header */}
        <div className="flex items-start gap-6">
          <div className="h-20 w-20 shrink-0 rounded-full bg-muted flex items-center justify-center text-2xl font-bold text-muted-foreground overflow-hidden">
            {profile.image_url ? (
              <img src={profile.image_url} alt="" className="h-full w-full object-cover" />
            ) : (
              (profile.username?.[0] ?? "?").toUpperCase()
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold truncate">
                {profile.full_name || profile.username || "Anonymous"}
              </h1>
              <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.className}`}>
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
              <p className="text-sm text-muted-foreground mt-0.5">@{profile.username}</p>
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
              {profile.is_mutual && (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Users className="h-3 w-3" /> Mutual
                </span>
              )}
            </div>

            {/* Action buttons */}
            <div className="mt-4 flex items-center gap-3">
              {!isOwnProfile && (
                <>
                  {profile.is_following ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleUnfollow}
                      disabled={actionLoading}
                    >
                      <UserX className="mr-1.5 h-4 w-4" /> Unfollow
                    </Button>
                  ) : profile.follow_request_pending ? (
                    <Button variant="outline" size="sm" disabled>
                      <Clock className="mr-1.5 h-4 w-4" /> Requested
                    </Button>
                  ) : (
                    <Button size="sm" onClick={handleFollow} disabled={actionLoading}>
                      <UserPlus className="mr-1.5 h-4 w-4" /> Follow
                    </Button>
                  )}

                  {profile.ai_access_level !== "no_one" &&
                    (profile.ai_access_level === "public" || profile.is_following) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => router.push(`/chat?target=${userId}`)}
                    >
                      <MessageSquare className="mr-1.5 h-4 w-4" /> Chat with AI
                    </Button>
                  )}
                </>
              )}

              {isOwnProfile && (
                <Button variant="outline" size="sm" onClick={() => router.push("/settings")}>
                  Edit Profile
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Followers / Following tabs */}
        <div className="mt-10">
          <div className="flex border-b">
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === "followers"
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setTab("followers")}
            >
              Followers
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === "following"
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setTab("following")}
            >
              Following
            </button>
          </div>

          <div className="mt-4 space-y-2">
            {(tab === "followers" ? followers : following).length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No {tab} yet
              </p>
            ) : (
              (tab === "followers" ? followers : following).map((item) => (
                <button
                  key={item.user_id}
                  onClick={() => router.push(`/profile/${item.user_id}`)}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-muted/50 transition-colors"
                >
                  <div className="h-9 w-9 shrink-0 rounded-full bg-muted flex items-center justify-center text-sm font-medium text-muted-foreground">
                    {item.image_url ? (
                      <img src={item.image_url} alt="" className="h-full w-full rounded-full object-cover" />
                    ) : (
                      (item.username?.[0] ?? "?").toUpperCase()
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">
                      {item.full_name || item.username || "Anonymous"}
                    </p>
                    {item.username && (
                      <p className="text-xs text-muted-foreground truncate">@{item.username}</p>
                    )}
                  </div>
                  {item.is_mutual && (
                    <span className="shrink-0 text-xs text-muted-foreground flex items-center gap-1">
                      <UserCheck className="h-3 w-3" /> Mutual
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      </main>
    </>
  );
}
