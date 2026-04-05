"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Camera,
  Check,
  Globe,
  Loader2,
  MessageSquare,
  Mic,
  Monitor,
  Save,
  ScanFace,
  Share2,
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
import {
  fetchMySocialProfile,
  updateSocialProfile,
  type SocialProfile,
} from "@/lib/social-api";
import { FaceCalibrationRecorder } from "@/components/avatar/face-calibration-recorder";
import { SocialConnections } from "@/components/social/social-connections";
import { VoiceRecorder } from "@/components/voice/voice-recorder";
import {
  SUPPORTED_LANGUAGES,
  cloneVoice,
  fetchTrainingScript,
  fetchVoiceProfile,
  retrainVoice,
  updateLanguagePreference,
  type TrainingScript,
  type VoiceProfile,
  type VoiceSampleResponse,
} from "@/lib/voice-training-api";

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

  const [socialProfile, setSocialProfile] = useState<SocialProfile | null>(null);
  const [isPrivate, setIsPrivate] = useState(false);
  const [aiAccessLevel, setAiAccessLevel] = useState<"public" | "followers_only" | "no_one">("public");
  const [savingSocial, setSavingSocial] = useState(false);

  const [voiceProfile, setVoiceProfile] = useState<VoiceProfile | null>(null);
  const [cloning, setCloning] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [trainingScript, setTrainingScript] = useState<TrainingScript | null>(null);

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

        try {
          const sp = await fetchMySocialProfile();
          if (!cancelled) {
            setSocialProfile(sp);
            setIsPrivate(sp.is_private);
            setAiAccessLevel(sp.ai_access_level);
          }
        } catch {
          // social graph service may not be running
        }

        try {
          const vp = await fetchVoiceProfile();
          if (!cancelled) setVoiceProfile(vp);
          const script = await fetchTrainingScript(vp?.primary_language ?? "en");
          if (!cancelled) setTrainingScript(script);
        } catch {
          // voice training service may not be running
        }
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

      {/* Privacy & AI Access Control */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Privacy & AI Access</CardTitle>
          <CardDescription>
            Control who can follow you and interact with your AI clone.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Private account toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Private Account</p>
              <p className="text-xs text-muted-foreground">
                When enabled, new followers must be approved by you
              </p>
            </div>
            <button
              role="switch"
              aria-checked={isPrivate}
              onClick={() => setIsPrivate(!isPrivate)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                isPrivate ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform duration-200 ${
                  isPrivate ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* AI Access Level */}
          <div>
            <label className="block text-sm font-medium mb-1.5">
              AI Access Level
            </label>
            <p className="text-xs text-muted-foreground mb-2">
              Who can interact with your AI clone
            </p>
            <select
              value={aiAccessLevel}
              onChange={(e) => setAiAccessLevel(e.target.value as typeof aiAccessLevel)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="public">Public — Anyone can interact</option>
              <option value="followers_only">Followers Only — Must follow you first</option>
              <option value="no_one">No One — AI interactions disabled</option>
            </select>
          </div>

          <Button
            size="sm"
            disabled={savingSocial}
            onClick={async () => {
              setSavingSocial(true);
              try {
                const updated = await updateSocialProfile({
                  is_private: isPrivate,
                  ai_access_level: aiAccessLevel,
                });
                setSocialProfile(updated);
                toast.success("Privacy settings saved");
              } catch {
                toast.error("Failed to save privacy settings");
              } finally {
                setSavingSocial(false);
              }
            }}
          >
            {savingSocial ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save Privacy Settings
          </Button>
        </CardContent>
      </Card>

      {/* Social Media Connections */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Share2 className="h-5 w-5" />
            Social Media Connections
          </CardTitle>
          <CardDescription>
            Connect your social accounts to import your content, writing style, and interests.
            This data improves your AI&apos;s personality and knowledge.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SocialConnections />
        </CardContent>
      </Card>

      {/* Face Calibration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <ScanFace className="h-5 w-5" />
            Face Calibration
          </CardTitle>
          <CardDescription>
            Record a short face scan video so the AI avatar uses your real facial expressions,
            head movements, and lip-sync. This transforms video responses from a static photo
            to a human-realistic talking head.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FaceCalibrationRecorder />
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

      {/* Voice Training */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Mic className="h-5 w-5" />
            Voice Identity
          </CardTitle>
          <CardDescription>
            Record the full 2-minute training script below so the AI sounds exactly like you.
            Use a quiet room, speak 6-8 inches from your microphone, and maintain a natural pace.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {voiceProfile && voiceProfile.cloning_status === "ready" ? (
            <div className="space-y-3">
              <div className="rounded-md border border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20 dark:border-emerald-800 p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                  <span className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
                    Voice cloned successfully
                  </span>
                </div>
                <div className="text-xs text-muted-foreground space-y-0.5">
                  {voiceProfile.voice_name && <p>Voice: {voiceProfile.voice_name}</p>}
                  <p>{voiceProfile.total_samples} sample{voiceProfile.total_samples !== 1 ? "s" : ""}, {Math.round(voiceProfile.total_duration_seconds)}s total</p>
                  {voiceProfile.voice_service_synced && <p className="text-emerald-600 dark:text-emerald-400">Synced to AI voice engine</p>}
                </div>
              </div>

              <div className="rounded-md border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 p-3">
                <p className="text-xs text-amber-800 dark:text-amber-300 font-medium mb-1">
                  Not satisfied with the voice quality?
                </p>
                <p className="text-xs text-amber-700 dark:text-amber-400 mb-2">
                  For a better match, retrain with the full 2-minute script in a quiet environment.
                  Speak naturally at a consistent volume, 6-8 inches from the mic.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    setRetraining(true);
                    try {
                      const result = await retrainVoice();
                      setVoiceProfile((vp) => vp ? {
                        ...vp,
                        elevenlabs_voice_id: null,
                        voice_name: null,
                        cloning_status: "pending",
                        total_samples: 0,
                        total_duration_seconds: 0,
                        voice_service_synced: false,
                      } : vp);
                      toast.success(result.message);
                    } catch (err) {
                      toast.error(err instanceof Error ? err.message : "Retrain failed");
                    } finally {
                      setRetraining(false);
                    }
                  }}
                  disabled={retraining}
                >
                  {retraining ? (
                    <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Resetting...</>
                  ) : (
                    <><Sparkles className="h-4 w-4 mr-1" /> Retrain My Voice</>
                  )}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {voiceProfile && voiceProfile.total_samples > 0 && (
                <div className="rounded-md border bg-muted/30 p-3 text-sm">
                  <span className="font-medium">{voiceProfile.total_samples} sample{voiceProfile.total_samples !== 1 ? "s" : ""}</span>
                  <span className="text-muted-foreground"> ({Math.round(voiceProfile.total_duration_seconds)}s total)</span>
                  {voiceProfile.total_duration_seconds < 90 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                      Need at least 90s for voice cloning ({Math.round(90 - voiceProfile.total_duration_seconds)}s more).
                      Read the full script below for best accuracy.
                    </p>
                  )}
                </div>
              )}

              <div className="rounded-md border border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800 p-3">
                <p className="text-xs font-medium text-blue-800 dark:text-blue-300 mb-1">Tips for best voice quality:</p>
                <ul className="text-xs text-blue-700 dark:text-blue-400 space-y-0.5 list-disc list-inside">
                  <li>Use a quiet room with no background noise</li>
                  <li>Stay 6-8 inches from your microphone</li>
                  <li>Speak at your natural pace — don&apos;t rush</li>
                  <li>Read the entire 2-minute script below in one recording</li>
                  <li>Keep a consistent volume throughout</li>
                </ul>
              </div>
            </div>
          )}

          {(!voiceProfile || voiceProfile.cloning_status !== "ready") && (
            <>
              <VoiceRecorder
                onSampleUploaded={(result: VoiceSampleResponse) => {
                  setVoiceProfile((vp) =>
                    vp
                      ? {
                          ...vp,
                          total_samples: vp.total_samples + 1,
                          total_duration_seconds: vp.total_duration_seconds + result.duration_seconds,
                        }
                      : {
                          user_id: user?.user_id ?? "",
                          elevenlabs_voice_id: null,
                          voice_name: null,
                          cloning_status: "pending",
                          primary_language: "en",
                          preferred_languages: [],
                          total_samples: 1,
                          total_duration_seconds: result.duration_seconds,
                          avg_pitch_hz: null,
                          speaking_rate_wpm: null,
                          voice_service_synced: false,
                        }
                  );
                  toast.success(result.message);
                }}
              />

              {voiceProfile && voiceProfile.total_duration_seconds >= 90 && voiceProfile.cloning_status !== "ready" && (
                <Button
                  size="sm"
                  onClick={async () => {
                    setCloning(true);
                    try {
                      const result = await cloneVoice(fullName || undefined);
                      setVoiceProfile((vp) => vp ? { ...vp, ...result, voice_service_synced: true } : vp);
                      toast.success(result.message);
                    } catch (err) {
                      toast.error(err instanceof Error ? err.message : "Cloning failed");
                    } finally {
                      setCloning(false);
                    }
                  }}
                  disabled={cloning}
                >
                  {cloning ? (
                    <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Cloning voice...</>
                  ) : (
                    <><Sparkles className="h-4 w-4 mr-1" /> Clone My Voice</>
                  )}
                </Button>
              )}
            </>
          )}

          {trainingScript && (!voiceProfile || voiceProfile.cloning_status !== "ready") && (
            <div className="border-t pt-4 space-y-3">
              <p className="text-sm font-medium">
                Voice Training Script ({trainingScript.language_name}) — ~{trainingScript.estimated_duration_minutes} minutes
              </p>
              <p className="text-xs text-muted-foreground">
                Read this entire script aloud while recording. This covers all the sounds
                needed for a high-quality voice clone.
              </p>
              <div className="max-h-80 overflow-y-auto space-y-4 rounded-md border bg-muted/30 p-4">
                {trainingScript.sections.map((section) => (
                  <div key={section.title} className="space-y-2">
                    <p className="text-sm font-semibold text-foreground">{section.title}</p>
                    <p className="text-xs text-muted-foreground italic">{section.instruction}</p>
                    {section.prompts.map((prompt, i) => (
                      <p key={i} className="text-sm leading-relaxed text-foreground/90 pl-3 border-l-2 border-primary/30">
                        {prompt}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Language Preference */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Language Preference
          </CardTitle>
          <CardDescription>
            Choose your preferred language. The AI will detect your input language and respond accordingly.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Primary Language</label>
              <select
                value={voiceProfile?.primary_language ?? "en"}
                onChange={async (e) => {
                  const lang = e.target.value;
                  setVoiceProfile((vp) => vp ? { ...vp, primary_language: lang } : vp);
                  try {
                    await updateLanguagePreference(lang, [lang]);
                    toast.success(`Language set to ${SUPPORTED_LANGUAGES[lang] || lang}`);
                  } catch {
                    toast.error("Failed to update language");
                  }
                }}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-xs outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
              >
                {Object.entries(SUPPORTED_LANGUAGES).map(([code, name]) => (
                  <option key={code} value={code}>{name}</option>
                ))}
              </select>
            </div>
            <p className="text-xs text-muted-foreground">
              Supports 12 languages including Yoruba and Nigerian Pidgin.
              Input in any language is auto-detected and translated.
            </p>
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
