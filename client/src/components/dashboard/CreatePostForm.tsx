import { useState, useRef, type ChangeEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { createPost, uploadRecording, type EventPublic } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

type CreatePostFormProps = {
  events?: EventPublic[];
  defaultEventId?: string;
  onSuccess?: () => void;
  onCancel?: () => void;
};

const POST_FORMATS = [
  { id: "blog", label: "Technical Blog", icon: "📰", desc: "Markdown blog post with key concepts" },
  { id: "newsletter", label: "Newsletter", icon: "📬", desc: "Email broadcast for community attendees" },
  { id: "linkedin", label: "LinkedIn Post", icon: "💼", desc: "Professional insights with hashtags" },
  { id: "ig_caption", label: "Instagram Post", icon: "📸", desc: "Engaging visual caption with hooks" },
  { id: "summary", label: "Executive Summary", icon: "📊", desc: "High-level TL;DR & actionable bullets" },
  { id: "flyer", label: "Event Flyer", icon: "🎨", desc: "Visual promo poster draft" },
];

const AVAILABLE_LANGUAGES = [
  { code: "en", label: "English", country: "GB" },
  { code: "hi", label: "Hindi (हिंदी)", country: "IN" },
  { code: "es", label: "Spanish", country: "ES" },
  { code: "fr", label: "French", country: "FR" },
  { code: "de", label: "German", country: "DE" },
  { code: "ja", label: "Japanese", country: "JP" },
  { code: "pt", label: "Portuguese", country: "BR" },
];

export function CreatePostForm({
  events = [],
  defaultEventId = "",
  onSuccess,
  onCancel,
}: CreatePostFormProps) {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeTab, setActiveTab] = useState<"ai_recording" | "manual">("ai_recording");

  // Manual form state
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [eventId, setEventId] = useState(defaultEventId);
  const [postType, setPostType] = useState("discussion");

  // AI Workflow state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [consent, setConsent] = useState(true);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([
    "blog",
    "newsletter",
    "linkedin",
    "ig_caption",
    "summary",
    "flyer",
  ]);
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>(["en", "hi"]);
  const [aiError, setAiError] = useState<string | null>(null);

  // Manual Post Mutation
  const manualMutation = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("Not authenticated");
      return createPost(token, {
        title,
        body,
        type: postType,
        event_id: eventId || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["community-content"] });
      queryClient.invalidateQueries({ queryKey: ["event-content"] });
      setTitle("");
      setBody("");
      onSuccess?.();
    },
  });

  // AI Recording Pipeline Mutation
  const aiUploadMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!token) throw new Error("Not authenticated");
      return uploadRecording(token, file, {
        consent,
        languages: selectedLanguages.join(","),
        types: selectedTypes.join(","),
        event_id: eventId || undefined,
      });
    },
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      onSuccess?.();
      navigate(`/jobs/${job.id}`);
    },
    onError: (err: Error) => setAiError(err.message),
  });

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim()) return;
    manualMutation.mutate();
  };

  const handleAiSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setAiError("Please select an audio or video recording file first.");
      return;
    }
    if (selectedTypes.length === 0) {
      setAiError("Please select at least one output content format.");
      return;
    }
    setAiError(null);
    aiUploadMutation.mutate(selectedFile);
  };

  const toggleType = (typeId: string) => {
    setSelectedTypes((prev) =>
      prev.includes(typeId)
        ? prev.length > 1
          ? prev.filter((t) => t !== typeId)
          : prev
        : [...prev, typeId]
    );
  };

  const toggleLanguage = (code: string) => {
    setSelectedLanguages((prev) =>
      prev.includes(code)
        ? prev.length > 1
          ? prev.filter((c) => c !== code)
          : prev
        : [...prev, code]
    );
  };

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setAiError(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      setSelectedFile(file);
      setAiError(null);
    }
  };

  return (
    <div className="space-y-4 rounded-3xl border border-white/15 bg-slate-900/90 p-6 md:p-8 shadow-2xl backdrop-blur-2xl transition-all">
      {/* Header with Mode Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <span>✨</span> Create &amp; Generate Community Content
          </h3>
          <p className="text-xs text-slate-400">
            Upload a talk recording for full automated AI drafting, or write a direct discussion post.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-xl bg-slate-950 p-1 border border-white/10">
            <button
              type="button"
              onClick={() => setActiveTab("ai_recording")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                activeTab === "ai_recording"
                  ? "bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              🎙️ AI Pipeline Workflow
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("manual")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                activeTab === "manual"
                  ? "bg-gradient-to-r from-amber-500 to-orange-600 text-white shadow"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              ✍️ Direct Post
            </button>
          </div>

          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-xl border border-white/10 p-2 text-xs text-slate-400 hover:bg-white/5 hover:text-white"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* MODE 1: FULL AI RECORDING WORKFLOW */}
      {/* ------------------------------------------------------------- */}
      {activeTab === "ai_recording" && (
        <form onSubmit={handleAiSubmit} className="space-y-6 animate-fadeIn">
          {aiError && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
              ⚠️ {aiError}
            </div>
          )}

          {/* Step 1: Event Association */}
          <div>
            <label className="mb-1.5 block text-xs font-bold text-slate-300 uppercase tracking-wider">
              1. Tag Target Event Catalog (Optional)
            </label>
            <select
              value={eventId}
              onChange={(e) => setEventId(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-2.5 text-xs text-slate-200 focus:border-amber-500 focus:outline-none"
            >
              <option value="">No Event (Standalone Workspace Session)</option>
              {events.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  {ev.name} • {ev.type.toUpperCase()} ({ev.city || "Online"})
                </option>
              ))}
            </select>
          </div>

          {/* Step 2: Drag and Drop File Upload */}
          <div>
            <label className="mb-1.5 block text-xs font-bold text-slate-300 uppercase tracking-wider">
              2. Upload Event Audio or Video Recording
            </label>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center cursor-pointer transition-all ${
                isDragging
                  ? "border-amber-500 bg-amber-500/10"
                  : selectedFile
                  ? "border-emerald-500/60 bg-emerald-950/20"
                  : "border-white/15 bg-slate-950/40 hover:border-amber-500/40 hover:bg-slate-950/70"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*,video/*"
                onChange={handleFileSelect}
                className="hidden"
              />

              {selectedFile ? (
                <div className="flex items-center gap-3">
                  <span className="text-3xl">🎵</span>
                  <div className="text-left">
                    <p className="text-xs font-bold text-white">{selectedFile.name}</p>
                    <p className="text-[10px] text-emerald-400">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready to transcribe &amp; draft
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <span className="text-3xl mb-2">📥</span>
                  <p className="text-xs font-semibold text-white">Click or drag event recording here</p>
                  <p className="text-[10px] text-slate-400 mt-1">Supports MP3, MP4, WAV, M4A, WebM (up to 500MB)</p>
                </>
              )}
            </div>
          </div>

          {/* Step 3: Multi-Format Deliverable Selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                3. Choose AI Output Formats ({selectedTypes.length}/6 selected)
              </label>
              <button
                type="button"
                onClick={() => setSelectedTypes(POST_FORMATS.map((p) => p.id))}
                className="text-[10px] text-amber-400 hover:underline"
              >
                Select All
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2.5">
              {POST_FORMATS.map((format) => {
                const active = selectedTypes.includes(format.id);
                return (
                  <button
                    key={format.id}
                    type="button"
                    onClick={() => toggleType(format.id)}
                    className={`flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                      active
                        ? "border-amber-500/60 bg-amber-500/15 text-white shadow-md shadow-amber-500/10"
                        : "border-white/10 bg-slate-950/40 text-slate-400 hover:border-white/20"
                    }`}
                  >
                    <span className="text-lg mb-1">{format.icon}</span>
                    <span className="text-xs font-bold truncate w-full">{format.label}</span>
                    <span className="text-[10px] text-slate-400 line-clamp-2 mt-0.5 leading-tight">
                      {format.desc}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Step 4: Multilingual Translation */}
          <div className="rounded-2xl border border-teal-500/30 bg-teal-950/20 p-4">
            <div className="flex items-center justify-between gap-3 mb-2.5">
              <div className="flex items-center gap-2">
                <span className="text-sm">🌐</span>
                <span className="text-xs font-bold uppercase tracking-wider text-teal-400">
                  Multilingual Translation Pass
                </span>
              </div>
              <span className="text-[10px] font-mono text-teal-300">
                {selectedLanguages.length} Active Languages
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
              {AVAILABLE_LANGUAGES.map((lang) => {
                const active = selectedLanguages.includes(lang.code);
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => toggleLanguage(lang.code)}
                    className={`flex items-center justify-center gap-1.5 rounded-xl px-2 py-1.5 text-xs font-medium transition-all ${
                      active
                        ? "border border-teal-400 bg-teal-500/20 text-white shadow ring-1 ring-teal-400/40"
                        : "border border-white/10 bg-slate-950/60 text-slate-400 hover:border-teal-500/40 hover:text-white"
                    }`}
                  >
                    <span className="text-[9px] font-bold text-slate-400">{lang.country}</span>
                    <span className="text-[11px] font-semibold truncate">{lang.label}</span>
                    {active && <span className="text-[10px] text-teal-300">✓</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Consent Checkbox */}
          <label className="flex items-start gap-2.5 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5 rounded border-white/20 bg-slate-950 text-amber-500 focus:ring-amber-500"
            />
            <span>
              I confirm this recording complies with attendee privacy and can be processed by the AI pipeline.
            </span>
          </label>

          {/* Submit Action */}
          <div className="flex items-center justify-between pt-2 border-t border-white/10">
            <span className="text-[11px] text-slate-400">
              Session will be saved under account: <strong className="text-slate-200">{user?.email}</strong>
            </span>

            <button
              type="submit"
              disabled={aiUploadMutation.isPending || !selectedFile}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-6 py-2.5 text-xs font-bold text-white shadow-xl shadow-orange-500/25 hover:scale-105 transition-all disabled:opacity-50"
            >
              {aiUploadMutation.isPending ? (
                <>
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Uploading &amp; Launching Pipeline...</span>
                </>
              ) : (
                <span>🚀 Launch AI Pipeline &amp; Generate All Posts</span>
              )}
            </button>
          </div>
        </form>
      )}

      {/* ------------------------------------------------------------- */}
      {/* MODE 2: DIRECT MANUAL COMMUNITY POST */}
      {/* ------------------------------------------------------------- */}
      {activeTab === "manual" && (
        <form onSubmit={handleManualSubmit} className="space-y-4 animate-fadeIn">
          {manualMutation.error && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
              {(manualMutation.error as Error).message}
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-300">Post Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Key takeaways from the opening keynote..."
              required
              className="w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-300">Tag Event (Optional)</label>
              <select
                value={eventId}
                onChange={(e) => setEventId(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-amber-500/50 focus:outline-none"
              >
                <option value="">General Community Discussion</option>
                {events.map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.name} ({ev.type})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-300">Category</label>
              <select
                value={postType}
                onChange={(e) => setPostType(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-amber-500/50 focus:outline-none"
              >
                <option value="discussion">💬 Discussion / Feedback</option>
                <option value="summary">📝 Session Summary</option>
                <option value="question">❓ Question for Speaker</option>
                <option value="announcement">📢 Announcement</option>
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-300">Post Content</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={4}
              placeholder="Share your thoughts, session notes, or ideas with the community..."
              required
              className="w-full rounded-xl border border-white/10 bg-slate-950 p-3 text-sm text-white placeholder-slate-500 focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
            />
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-[11px] text-slate-500">
              Posting as: <strong className="text-slate-300">{user?.email}</strong>
            </span>

            <button
              type="submit"
              disabled={manualMutation.isPending || !title.trim() || !body.trim()}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-2 text-xs font-bold text-white shadow-lg shadow-orange-500/20 transition-all hover:scale-105 disabled:opacity-50"
            >
              {manualMutation.isPending ? "Publishing..." : "Publish Post 🚀"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
