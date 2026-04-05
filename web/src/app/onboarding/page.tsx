"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Loader2, Camera, Globe, Mic, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useAuth } from "@/components/auth/auth-provider";
import { apiSubmitOnboarding, apiUploadAvatar, saveAuth, getToken, type AuthUser } from "@/lib/auth";
import { VoiceRecorder } from "@/components/voice/voice-recorder";
import {
  SUPPORTED_LANGUAGES,
  fetchTrainingScript,
  updateLanguagePreference,
  type TrainingScript,
  type VoiceSampleResponse,
} from "@/lib/voice-training-api";

const STEPS = [
  { key: "basic", title: "Basic Info", description: "Tell us about yourself" },
  { key: "personality", title: "Personality", description: "How would you describe yourself?" },
  { key: "communication", title: "Communication", description: "How do you communicate?" },
  { key: "experience", title: "Life Experience", description: "Your background and stories" },
  { key: "beliefs", title: "Beliefs & Preferences", description: "Your worldview" },
  { key: "voice", title: "Voice & Language", description: "Record your voice so your AI sounds like you" },
  { key: "review", title: "Review & Submit", description: "Confirm your profile" },
] as const;

interface FormData {
  full_name: string;
  age: string;
  gender: string;
  location: string;
  personality_description: string;
  introvert_extrovert: string;
  core_values: string;
  formality: string;
  uses_humor: boolean;
  emotional_response_style: string;
  key_life_events: string;
  career_background: string;
  education: string;
  views_money: string;
  views_relationships: string;
  views_success: string;
  philosophical_beliefs: string;
  energy: string;
  response_length: string;
}

const initialFormData: FormData = {
  full_name: "",
  age: "",
  gender: "",
  location: "",
  personality_description: "",
  introvert_extrovert: "",
  core_values: "",
  formality: "",
  uses_humor: false,
  emotional_response_style: "",
  key_life_events: "",
  career_background: "",
  education: "",
  views_money: "",
  views_relationships: "",
  views_success: "",
  philosophical_beliefs: "",
  energy: "",
  response_length: "",
};

function InputField({ label, id, value, onChange, placeholder, type = "text", error }: {
  label: string; id: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; error?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label} <span className="text-destructive">*</span>
      </label>
      <input
        id={id} type={type} value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`flex h-9 w-full rounded-md border bg-background px-3 py-1.5 text-sm shadow-xs outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/30 transition-colors ${
          error ? "border-destructive focus:border-destructive focus:ring-destructive/30" : "border-input focus:border-ring"
        }`}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function TextAreaField({ label, id, value, onChange, placeholder, rows = 3, error }: {
  label: string; id: string; value: string; onChange: (v: string) => void;
  placeholder?: string; rows?: number; error?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label} <span className="text-destructive">*</span>
      </label>
      <textarea
        id={id} value={value} rows={rows}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`flex w-full rounded-md border bg-background px-3 py-2 text-sm shadow-xs outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/30 resize-y transition-colors ${
          error ? "border-destructive focus:border-destructive focus:ring-destructive/30" : "border-input focus:border-ring"
        }`}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function SelectField({ label, id, value, onChange, options, error }: {
  label: string; id: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; error?: string;
}) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={id} className="text-sm font-medium">
          {label} <span className="text-destructive">*</span>
        </label>
      )}
      <select
        id={id} value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`flex h-9 w-full rounded-md border bg-background px-3 py-1.5 text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring/30 transition-colors ${
          error ? "border-destructive focus:border-destructive focus:ring-destructive/30" : "border-input focus:border-ring"
        }`}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

type FieldRule = { field: keyof FormData; label: string };

const STEP_REQUIRED_FIELDS: Record<number, FieldRule[]> = {
  0: [
    { field: "full_name", label: "Full Name" },
    { field: "age", label: "Age" },
    { field: "gender", label: "Gender" },
    { field: "location", label: "Location" },
  ],
  1: [
    { field: "personality_description", label: "Personality description" },
    { field: "introvert_extrovert", label: "Introvert/Extrovert preference" },
    { field: "core_values", label: "Core values" },
  ],
  2: [
    { field: "formality", label: "Communication formality" },
    { field: "emotional_response_style", label: "Emotional response style" },
  ],
  3: [
    { field: "key_life_events", label: "Key life events" },
    { field: "career_background", label: "Career background" },
    { field: "education", label: "Education" },
  ],
  4: [
    { field: "views_money", label: "Views on money" },
    { field: "views_relationships", label: "Views on relationships" },
    { field: "views_success", label: "Views on success" },
    { field: "philosophical_beliefs", label: "Philosophical or religious beliefs" },
  ],
  6: [
    { field: "energy", label: "Voice energy" },
    { field: "response_length", label: "Response length preference" },
  ],
};

export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormData>(initialFormData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [avatarBase64, setAvatarBase64] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { user } = useAuth();
  const router = useRouter();

  const [selectedLanguage, setSelectedLanguage] = useState("en");
  const [trainingScript, setTrainingScript] = useState<TrainingScript | null>(null);
  const [voiceSamples, setVoiceSamples] = useState(0);
  const [totalDuration, setTotalDuration] = useState(0);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (step === 5) {
      fetchTrainingScript(selectedLanguage)
        .then(setTrainingScript)
        .catch(() => {});
    }
  }, [step, selectedLanguage]);

  const handlePhotoSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please select a valid image file (JPEG or PNG)");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      toast.error("Image must be under 20MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setAvatarPreview(dataUrl);
      const b64 = dataUrl.split(",")[1];
      setAvatarBase64(b64);
      setFieldErrors((prev) => { const n = { ...prev }; delete n.__photo; return n; });
    };
    reader.readAsDataURL(file);
  }, []);

  const clearPhoto = useCallback(() => {
    setAvatarPreview(null);
    setAvatarBase64(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const update = useCallback(
    <K extends keyof FormData>(key: K, value: FormData[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }));
      setFieldErrors((prev) => {
        if (!prev[key]) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      });
    },
    []
  );

  const validateStep = useCallback(
    (s: number): Record<string, string> => {
      const errors: Record<string, string> = {};
      const rules = STEP_REQUIRED_FIELDS[s];
      if (rules) {
        for (const { field, label } of rules) {
          const v = form[field];
          if (typeof v === "string" && v.trim() === "") {
            errors[field] = `${label} is required`;
          }
        }
      }
      if (s === 0 && !avatarBase64) {
        errors.__photo = "Photo is required for your AI video avatar";
      }
      if (s === 0 && form.age.trim() !== "") {
        const n = parseInt(form.age, 10);
        if (isNaN(n) || n < 1 || n > 150) {
          errors.age = "Please enter a valid age between 1 and 150";
        }
      }
      return errors;
    },
    [form, avatarBase64]
  );

  const tryAdvance = useCallback(() => {
    const errors = validateStep(step);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      const firstMsg = Object.values(errors)[0];
      toast.error(firstMsg);
      return false;
    }
    setFieldErrors({});
    return true;
  }, [step, validateStep]);

  async function handleSubmit() {
    setIsSubmitting(true);
    try {
      const parsedAge = form.age ? parseInt(form.age, 10) : null;
      const payload = {
        basic_info: {
          full_name: form.full_name.trim(),
          age: parsedAge !== null && !isNaN(parsedAge) ? parsedAge : null,
          gender: form.gender || null,
          location: form.location || null,
        },
        personality: {
          description: form.personality_description,
          introvert_extrovert: form.introvert_extrovert,
          core_values: form.core_values,
        },
        communication_style: {
          formality: form.formality,
          uses_humor: form.uses_humor,
          emotional_response_style: form.emotional_response_style,
        },
        life_experience: {
          key_life_events: form.key_life_events,
          career_background: form.career_background,
          education: form.education,
        },
        beliefs: {
          views_money: form.views_money,
          views_relationships: form.views_relationships,
          views_success: form.views_success,
          philosophical_beliefs: form.philosophical_beliefs,
        },
        voice_tone: {
          energy: form.energy,
          response_length: form.response_length,
        },
      };

      await apiSubmitOnboarding(payload);

      if (avatarBase64 && user) {
        try {
          await apiUploadAvatar(user.user_id, avatarBase64, form.full_name || undefined);
        } catch (avatarErr) {
          console.warn("Avatar upload failed (non-fatal):", avatarErr);
        }
      }

      try {
        await updateLanguagePreference(selectedLanguage, [selectedLanguage]);
      } catch {
        console.warn("Language preference save failed (non-fatal)");
      }

      if (user) {
        const updated: AuthUser = { ...user, onboarding_completed: true };
        const token = getToken();
        if (token) saveAuth(token, updated);
      }

      toast.success("Profile complete! Your AI is now personalized.");
      router.push("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  const currentStep = STEPS[step];
  const isLastStep = step === STEPS.length - 1;
  const progress = ((step + 1) / STEPS.length) * 100;

  return (
    <div className="flex min-h-full flex-1 items-center justify-center px-6 py-10">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <div className="mb-4">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
              <span>Step {step + 1} of {STEPS.length}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300 rounded-full"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
          <CardTitle className="text-xl">{currentStep.title}</CardTitle>
          <CardDescription>{currentStep.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4 min-h-[240px]">
            {step === 0 && (
              <>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">
                    Your Photo (used for AI video avatar) <span className="text-destructive">*</span>
                  </label>
                  <div className="flex items-center gap-4">
                    {avatarPreview ? (
                      <div className="relative">
                        <img
                          src={avatarPreview}
                          alt="Avatar preview"
                          className="h-20 w-20 rounded-full object-cover border-2 border-primary"
                        />
                        <button
                          type="button"
                          onClick={clearPhoto}
                          className="absolute -top-1 -right-1 rounded-full bg-destructive p-0.5 text-destructive-foreground"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className={`flex h-20 w-20 items-center justify-center rounded-full border-2 border-dashed transition-colors ${
                          fieldErrors.__photo
                            ? "border-destructive hover:border-destructive/70"
                            : "border-muted-foreground/30 hover:border-primary"
                        }`}
                      >
                        <Camera className={`h-6 w-6 ${fieldErrors.__photo ? "text-destructive" : "text-muted-foreground"}`} />
                      </button>
                    )}
                    <div className="flex-1 text-sm text-muted-foreground">
                      {avatarPreview ? (
                        <p>Photo uploaded! This will be your AI video avatar.</p>
                      ) : (
                        <p>Upload a clear photo of your face. This will be used to generate video responses that look like you.</p>
                      )}
                    </div>
                  </div>
                  {fieldErrors.__photo && <p className="text-xs text-destructive">{fieldErrors.__photo}</p>}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png"
                    onChange={handlePhotoSelect}
                    className="hidden"
                  />
                </div>
                <InputField label="Full Name" id="full_name" value={form.full_name} onChange={(v) => update("full_name", v)} placeholder="John Doe" error={fieldErrors.full_name} />
                <InputField label="Age" id="age" value={form.age} onChange={(v) => update("age", v)} placeholder="28" type="number" error={fieldErrors.age} />
                <SelectField label="Gender" id="gender" value={form.gender} onChange={(v) => update("gender", v)} error={fieldErrors.gender} options={[
                  { value: "", label: "Select…" },
                  { value: "male", label: "Male" },
                  { value: "female", label: "Female" },
                  { value: "non-binary", label: "Non-binary" },
                  { value: "other", label: "Other" },
                  { value: "prefer-not-to-say", label: "Prefer not to say" },
                ]} />
                <InputField label="Location" id="location" value={form.location} onChange={(v) => update("location", v)} placeholder="New York, USA" error={fieldErrors.location} />
              </>
            )}

            {step === 1 && (
              <>
                <TextAreaField label="How would you describe your personality?" id="personality_description" value={form.personality_description} onChange={(v) => update("personality_description", v)} placeholder="I'm an outgoing, curious person who loves learning new things…" rows={4} error={fieldErrors.personality_description} />
                <SelectField label="Are you more introverted or extroverted?" id="introvert_extrovert" value={form.introvert_extrovert} onChange={(v) => update("introvert_extrovert", v)} error={fieldErrors.introvert_extrovert} options={[
                  { value: "", label: "Select…" },
                  { value: "introvert", label: "Introvert" },
                  { value: "extrovert", label: "Extrovert" },
                  { value: "ambivert", label: "Ambivert (mix of both)" },
                ]} />
                <TextAreaField label="What are your core values?" id="core_values" value={form.core_values} onChange={(v) => update("core_values", v)} placeholder="Honesty, creativity, family, growth…" rows={3} error={fieldErrors.core_values} />
              </>
            )}

            {step === 2 && (
              <>
                <SelectField label="Do you prefer formal or casual communication?" id="formality" value={form.formality} onChange={(v) => update("formality", v)} error={fieldErrors.formality} options={[
                  { value: "", label: "Select…" },
                  { value: "formal", label: "Formal" },
                  { value: "casual", label: "Casual" },
                  { value: "mixed", label: "Depends on the situation" },
                ]} />
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Do you use humor often?</label>
                  <div className="flex items-center gap-3">
                    <button type="button" onClick={() => update("uses_humor", true)}
                      className={`rounded-md border px-4 py-1.5 text-sm transition-colors ${form.uses_humor ? "border-primary bg-primary/10 text-foreground" : "border-input text-muted-foreground hover:border-foreground/30"}`}>
                      Yes
                    </button>
                    <button type="button" onClick={() => update("uses_humor", false)}
                      className={`rounded-md border px-4 py-1.5 text-sm transition-colors ${!form.uses_humor ? "border-primary bg-primary/10 text-foreground" : "border-input text-muted-foreground hover:border-foreground/30"}`}>
                      Not really
                    </button>
                  </div>
                </div>
                <TextAreaField label="How do you typically respond to emotional situations?" id="emotional_response_style" value={form.emotional_response_style} onChange={(v) => update("emotional_response_style", v)} placeholder="I tend to stay calm and think things through, but I'm empathetic…" rows={3} error={fieldErrors.emotional_response_style} />
              </>
            )}

            {step === 3 && (
              <>
                <TextAreaField label="Key life events or stories" id="key_life_events" value={form.key_life_events} onChange={(v) => update("key_life_events", v)} placeholder="Share any important moments, stories, or experiences that shaped who you are…" rows={5} error={fieldErrors.key_life_events} />
                <TextAreaField label="Career background" id="career_background" value={form.career_background} onChange={(v) => update("career_background", v)} placeholder="Software engineer for 10 years, started a startup…" rows={3} error={fieldErrors.career_background} />
                <TextAreaField label="Education" id="education" value={form.education} onChange={(v) => update("education", v)} placeholder="BS in Computer Science from MIT…" rows={2} error={fieldErrors.education} />
              </>
            )}

            {step === 4 && (
              <>
                <TextAreaField label="Views on money" id="views_money" value={form.views_money} onChange={(v) => update("views_money", v)} placeholder="Money is a tool, not a goal…" rows={2} error={fieldErrors.views_money} />
                <TextAreaField label="Views on relationships" id="views_relationships" value={form.views_relationships} onChange={(v) => update("views_relationships", v)} placeholder="I believe in deep, authentic connections…" rows={2} error={fieldErrors.views_relationships} />
                <TextAreaField label="Views on success" id="views_success" value={form.views_success} onChange={(v) => update("views_success", v)} placeholder="Success is about fulfillment, not just achievements…" rows={2} error={fieldErrors.views_success} />
                <TextAreaField label="Philosophical or religious beliefs" id="philosophical_beliefs" value={form.philosophical_beliefs} onChange={(v) => update("philosophical_beliefs", v)} placeholder="I'm a stoic at heart…" rows={2} error={fieldErrors.philosophical_beliefs} />
              </>
            )}

            {step === 5 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-1">
                  <Globe className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium">Preferred Language</span>
                </div>
                <SelectField label="" id="language" value={selectedLanguage} onChange={(v) => setSelectedLanguage(v)} options={
                  Object.entries(SUPPORTED_LANGUAGES).map(([code, name]) => ({ value: code, label: name }))
                } />

                <div className="border-t pt-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Mic className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium">Record Your Voice</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Record the full 2-minute training script below for the best voice clone.
                    Use a quiet room and speak naturally, 6-8 inches from your mic.
                  </p>

                  <VoiceRecorder
                    onSampleUploaded={(result: VoiceSampleResponse) => {
                      setVoiceSamples((n) => n + 1);
                      setTotalDuration((d) => d + result.duration_seconds);
                    }}
                  />

                  {voiceSamples > 0 && (
                    <div className="rounded-md border border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20 dark:border-emerald-800 p-3 text-sm">
                      <span className="font-medium text-emerald-700 dark:text-emerald-400">
                        {voiceSamples} sample{voiceSamples > 1 ? "s" : ""} uploaded
                      </span>
                      <span className="text-muted-foreground"> ({Math.round(totalDuration)}s total)</span>
                    </div>
                  )}
                </div>

                {trainingScript && (
                  <div className="border-t pt-4 space-y-3">
                    <p className="text-sm font-medium">
                      Training Script ({trainingScript.language_name}) — ~{trainingScript.estimated_duration_minutes} minutes
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Read this entire script aloud while recording for the best voice clone.
                    </p>
                    <div className="max-h-64 overflow-y-auto space-y-4 rounded-md border bg-muted/30 p-4">
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

                <p className="text-xs text-muted-foreground">
                  You can skip this step and record your voice later in Settings.
                </p>
              </div>
            )}

            {step === 6 && (
              <div className="space-y-4">
                <div className="mb-2">
                  <SelectField label="Voice energy" id="energy" value={form.energy} onChange={(v) => update("energy", v)} error={fieldErrors.energy} options={[
                    { value: "", label: "Select…" },
                    { value: "calm", label: "Calm & composed" },
                    { value: "energetic", label: "Energetic & enthusiastic" },
                    { value: "assertive", label: "Assertive & direct" },
                    { value: "warm", label: "Warm & nurturing" },
                  ]} />
                </div>
                <div className="mb-4">
                  <SelectField label="Response length preference" id="response_length" value={form.response_length} onChange={(v) => update("response_length", v)} error={fieldErrors.response_length} options={[
                    { value: "", label: "Select…" },
                    { value: "short", label: "Short & concise" },
                    { value: "medium", label: "Medium — balanced" },
                    { value: "detailed", label: "Detailed & thorough" },
                  ]} />
                </div>

                <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
                  <h4 className="font-medium text-sm">Profile Summary</h4>
                  <div className="text-sm text-muted-foreground space-y-1">
                    {avatarPreview && (
                      <div className="flex items-center gap-2 mb-2">
                        <img src={avatarPreview} alt="Avatar" className="h-10 w-10 rounded-full object-cover" />
                        <span className="text-foreground font-medium">Avatar photo uploaded</span>
                      </div>
                    )}
                    <p><span className="text-foreground font-medium">Name:</span> {form.full_name || "—"}</p>
                    {form.age && <p><span className="text-foreground font-medium">Age:</span> {form.age}</p>}
                    {form.location && <p><span className="text-foreground font-medium">Location:</span> {form.location}</p>}
                    {form.personality_description && <p><span className="text-foreground font-medium">Personality:</span> {form.personality_description.slice(0, 80)}…</p>}
                    {form.formality && <p><span className="text-foreground font-medium">Style:</span> {form.formality}, humor: {form.uses_humor ? "yes" : "no"}</p>}
                    {form.energy && <p><span className="text-foreground font-medium">Voice:</span> {form.energy}, {form.response_length || "medium"} responses</p>}
                    <p><span className="text-foreground font-medium">Language:</span> {SUPPORTED_LANGUAGES[selectedLanguage] || selectedLanguage}</p>
                    {voiceSamples > 0 && (
                      <p><span className="text-foreground font-medium">Voice samples:</span> {voiceSamples} ({Math.round(totalDuration)}s)</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              onClick={() => { setFieldErrors({}); setStep((s) => Math.max(0, s - 1)); }}
              disabled={step === 0}
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>

            {isLastStep ? (
              <Button
                size="sm"
                onClick={() => { if (tryAdvance()) handleSubmit(); }}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" />
                    Complete Setup
                  </>
                )}
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => { if (tryAdvance()) setStep((s) => Math.min(STEPS.length - 1, s + 1)); }}
              >
                Next
                <ArrowRight className="h-4 w-4" />
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
