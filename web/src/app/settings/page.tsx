"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Camera,
  Check,
  Loader2,
  MessageSquare,
  Mic,
  Monitor,
  Save,
  Sparkles,
  Video,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { useAuth } from "@/components/auth/auth-provider";
import {
  fetchProfile,
  fetchSettings,
  updateProfile,
  updateSettings,
  uploadProfileImage,
  type UserProfile,
  type UserSettings,
} from "@/lib/settings-api";

const OUTPUT_MODES = [
  {
    value: "chat" as const,
    label: "Chat",
    description: "Text-based responses only",
    icon: MessageSquare,
  },
  {
    value: "voice" as const,
    label: "Voice",
    description: "Text + AI spoken audio",
    icon: Mic,
  },
  {
    value: "video" as const,
    label: "Video",
    description: "Text + voice + avatar video",
    icon: Video,
  },
  {
    value: "immersive" as const,
    label: "Immersive",
    description: "Full multimodal experience",
    icon: Monitor,
  },
];

const RESPONSE_LENGTHS = [
  { value: "short", label: "Short" },
  { value: "medium", label: "Medium" },
  { value: "long", label: "Long" },
];

const CREATIVITY_LEVELS = [
  { value: "low", label: "Conservative" },
  { value: "medium", label: "Balanced" },
  { value: "high", label: "Creative" },
];

const PERSONALITY_LEVELS = [
  { value: "subtle", label: "Subtle" },
  { value: "balanced", label: "Balanced" },
  { value: "strong", label: "Strong" },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [bio, setBio] = useState("");

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    async function load() {
      try {
        const [p, s] = await Promise.all([fetchProfile(), fetchSettings()]);
        if (cancelled) return;
        setProfile(p);
        setSettings(s);
        setFullName(p.full_name || "");
        setEmail(p.email || "");
        setBio(p.bio || "");
        if (p.image_url) setImagePreview(p.image_url);
      } catch (err) {
        if (!cancelled) toast.error("Failed to load settings");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [user]);

  const handleImageUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      toast.error("Please select a valid image file");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      toast.error("Image must be under 20MB");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);

    setUploading(true);
    try {
      const result = await uploadProfileImage(file);
      setImagePreview(result.image_url);
      setProfile((p) => p ? { ...p, image_url: result.image_url, avatar_synced: result.avatar_synced } : p);
      toast.success(
        result.avatar_synced
          ? "Photo uploaded and synced to your AI avatar!"
          : "Photo uploaded! Avatar will use this image for videos."
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const handleSaveProfile = useCallback(async () => {
    setSaving(true);
    try {
      const updated = await updateProfile({ full_name: fullName, email, bio });
      setProfile(updated);
      toast.success("Profile saved");
    } catch {
      toast.error("Failed to save profile");
    } finally {
      setSaving(false);
    }
  }, [fullName, email, bio]);

  const handleModeChange = useCallback(async (mode: UserSettings["output_mode"]) => {
    setSettings((s) => s ? { ...s, output_mode: mode } : s);
    try {
      await updateSettings({ output_mode: mode });
      toast.success(`Output mode set to ${mode}`);
    } catch {
      toast.error("Failed to update mode");
    }
  }, []);

  const handleSettingChange = useCallback(async (key: string, value: string) => {
    setSettings((s) => s ? { ...s, [key]: value } : s);
    try {
      await updateSettings({ [key]: value } as Partial<UserSettings>);
    } catch {
      toast.error("Failed to save setting");
    }
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push("/")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-sm text-muted-foreground">Manage your profile and AI output preferences</p>
        </div>
      </div>

      {/* Profile Image */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Profile Image</CardTitle>
          <CardDescription>
            Your photo is used as the face for AI video responses
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            <div className="relative">
              {imagePreview ? (
                <img
                  src={imagePreview}
                  alt="Profile"
                  className="h-24 w-24 rounded-full object-cover border-2 border-primary"
                />
              ) : (
                <div className="flex h-24 w-24 items-center justify-center rounded-full border-2 border-dashed border-muted-foreground/30 bg-muted">
                  <Camera className="h-8 w-8 text-muted-foreground" />
                </div>
              )}
              {uploading && (
                <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50">
                  <Loader2 className="h-6 w-6 animate-spin text-white" />
                </div>
              )}
            </div>
            <div className="flex-1 space-y-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                <Camera className="h-4 w-4 mr-1" />
                {imagePreview ? "Change Photo" : "Upload Photo"}
              </Button>
              <p className="text-xs text-muted-foreground">
                JPG, PNG, or WebP. Max 20MB. Will be compressed and used for video avatar.
              </p>
              {profile?.avatar_synced && (
                <p className="text-xs text-emerald-600 flex items-center gap-1">
                  <Check className="h-3 w-3" /> Synced to AI avatar
                </p>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleImageUpload}
              className="hidden"
            />
          </div>
        </CardContent>
      </Card>

      {/* Profile Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Profile Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Full Name</label>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-xs outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="Your name"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-xs outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="you@example.com"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Bio</label>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              rows={3}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs outline-none focus:border-ring focus:ring-2 focus:ring-ring/30 resize-y"
              placeholder="Tell us about yourself..."
            />
          </div>
          <Button size="sm" onClick={handleSaveProfile} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            Save Profile
          </Button>
        </CardContent>
      </Card>

      {/* Output Mode */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">AI Output Mode</CardTitle>
          <CardDescription>
            Choose how your AI responds. This controls what the orchestrator produces.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3">
            {OUTPUT_MODES.map((mode) => {
              const Icon = mode.icon;
              const active = settings?.output_mode === mode.value;
              return (
                <button
                  key={mode.value}
                  onClick={() => handleModeChange(mode.value)}
                  className={`flex flex-col items-start gap-1.5 rounded-lg border p-3 text-left transition-all ${
                    active
                      ? "border-primary bg-primary/5 ring-2 ring-primary/30"
                      : "border-input hover:border-foreground/30"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Icon className={`h-4 w-4 ${active ? "text-primary" : "text-muted-foreground"}`} />
                    <span className={`text-sm font-medium ${active ? "text-primary" : ""}`}>
                      {mode.label}
                    </span>
                    {active && <Check className="h-3 w-3 text-primary ml-auto" />}
                  </div>
                  <p className="text-xs text-muted-foreground">{mode.description}</p>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">AI Preferences</CardTitle>
          <CardDescription>Fine-tune how your AI generates responses</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <label className="text-sm font-medium">Response Length</label>
            <div className="flex gap-2">
              {RESPONSE_LENGTHS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleSettingChange("response_length", opt.value)}
                  className={`rounded-md border px-4 py-1.5 text-sm transition-colors ${
                    settings?.response_length === opt.value
                      ? "border-primary bg-primary/10 text-foreground font-medium"
                      : "border-input text-muted-foreground hover:border-foreground/30"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Creativity Level</label>
            <div className="flex gap-2">
              {CREATIVITY_LEVELS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleSettingChange("creativity_level", opt.value)}
                  className={`rounded-md border px-4 py-1.5 text-sm transition-colors ${
                    settings?.creativity_level === opt.value
                      ? "border-primary bg-primary/10 text-foreground font-medium"
                      : "border-input text-muted-foreground hover:border-foreground/30"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Personality Intensity</label>
            <p className="text-xs text-muted-foreground">How strongly the AI embodies your personality</p>
            <div className="flex gap-2">
              {PERSONALITY_LEVELS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleSettingChange("personality_intensity", opt.value)}
                  className={`rounded-md border px-4 py-1.5 text-sm transition-colors ${
                    settings?.personality_intensity === opt.value
                      ? "border-primary bg-primary/10 text-foreground font-medium"
                      : "border-input text-muted-foreground hover:border-foreground/30"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
