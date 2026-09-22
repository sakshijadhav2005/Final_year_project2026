import { useState, useRef, type ChangeEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { uploadRecording } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

// The 6 post formats exactly as specified in the architectural flowchart
const POST_TYPES = [
  {
    id: "blog",
    title: "Blog",
    subtitle: "Long-form article with section headers",
    icon: "📄",
    color: "blue",
    activeClass: "border-blue-500 bg-blue-500/15 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.25)]",
    badgeClass: "bg-blue-500/20 text-blue-300",
    glowClass: "from-blue-500/20",
  },
  {
    id: "newsletter",
    title: "Newsletter",
    subtitle: "Email briefing with punchy highlights",
    icon: "✉️",
    color: "green",
    activeClass: "border-emerald-500 bg-emerald-500/15 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.25)]",
    badgeClass: "bg-emerald-500/20 text-emerald-300",
    glowClass: "from-emerald-500/20",
  },
  {
    id: "linkedin",
    title: "LinkedIn Post",
    subtitle: "Professional hook, takeaways & hashtags",
    icon: "💼",
    color: "purple",
    activeClass: "border-purple-500 bg-purple-500/15 text-purple-400 shadow-[0_0_15px_rgba(168,85,247,0.25)]",
    badgeClass: "bg-purple-500/20 text-purple-300",
    glowClass: "from-purple-500/20",
  },
  {
    id: "ig_caption",
    title: "Instagram Caption",
    subtitle: "Engaging social copy, emojis & tags",
    icon: "📸",
    color: "orange",
    activeClass: "border-amber-500 bg-amber-500/15 text-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.25)]",
    badgeClass: "bg-amber-500/20 text-amber-300",
    glowClass: "from-amber-500/20",
  },
  {
    id: "summary",
    title: "Event Summary",
    subtitle: "Executive overview & action items",
    icon: "📅",
    color: "pink",
    activeClass: "border-pink-500 bg-pink-500/15 text-pink-400 shadow-[0_0_15px_rgba(236,72,153,0.25)]",
    badgeClass: "bg-pink-500/20 text-pink-300",
    glowClass: "from-pink-500/20",
  },
  {
    id: "flyer",
    title: "Flyer",
    subtitle: "Visual poster copy & key slogans",
    icon: "📢",
    color: "teal",
    activeClass: "border-teal-500 bg-teal-500/15 text-teal-400 shadow-[0_0_15px_rgba(20,184,166,0.25)]",
    badgeClass: "bg-teal-500/20 text-teal-300",
    glowClass: "from-teal-500/20",
  },
];

const AVAILABLE_LANGUAGES = [
  { code: "en", label: "English", flag: "🇬🇧" },
  { code: "hi", label: "Hindi (हिंदी)", flag: "🇮🇳" },
  { code: "es", label: "Spanish (Español)", flag: "🇪🇸" },
  { code: "fr", label: "French (Français)", flag: "🇫🇷" },
  { code: "de", label: "German (Deutsch)", flag: "🇩🇪" },
  { code: "ja", label: "Japanese (日本語)", flag: "🇯🇵" },
  { code: "pt", label: "Portuguese (Português)", flag: "🇧🇷" },
];

export function DashboardUploadCard() {
  const token = useAuthStore((s) => s.accessToken);
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

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
  const [error, setError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadRecording(token as string, file, {
        consent,
        languages: selectedLanguages.join(","),
        types: selectedTypes.join(","),
      }),
    onSuccess: (job) => {
      navigate(`/jobs/${job.id}`);
    },
    onError: (err: Error) => setError(err.message),
  });

  function handleFileSelect(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
    }
  }

  function toggleType(typeId: string) {
    setSelectedTypes((prev) =>
      prev.includes(typeId)
        ? prev.length > 1
          ? prev.filter((t) => t !== typeId)
          : prev
        : [...prev, typeId],
    );
  }

  function selectAllTypes() {
    setSelectedTypes(POST_TYPES.map((p) => p.id));
  }

  function toggleLanguage(code: string) {
    setSelectedLanguages((prev) =>
      prev.includes(code)
        ? prev.length > 1
          ? prev.filter((c) => c !== code)
          : prev
        : [...prev, code],
    );
  }

  function handleSubmit() {
    if (!token) {
      navigate("/login");
      return;
    }
    if (!selectedFile) {
      fileInputRef.current?.click();
      return;
    }
    if (!consent) {
      setError("Please confirm participant consent before proceeding.");
      return;
    }
    if (selectedTypes.length === 0) {
      setError("Please select at least one post type to generate.");
      return;
    }
    upload.mutate(selectedFile);
  }

  function loadSampleRecording() {
    fetch("/data/samples/clean_event_session.txt")
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.text();
      })
      .then((txt) => {
        const f = new File([txt], "sample_ai_keynote_session.txt", { type: "text/plain" });
        setSelectedFile(f);
        setError(null);
      })
      .catch(() => {
        const fallback =
          "Welcome to the EventAI annual tech keynote. Today we are launching intelligent agents that transform event audio into blogs, newsletters, and social posts. Transcription quality is high and our multi-agent pipeline analyzes topics, speakers, and quotes in real time.";
        const f = new File([fallback], "sample_ai_keynote_session.txt", { type: "text/plain" });
        setSelectedFile(f);
        setError(null);
      });
  }

  return (
    <div className="glass p-21 sm:p-34 border-gold/30 relative overflow-hidden space-y-21">
      {/* Decorative ambient gradients */}
      <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-gold/10 blur-3xl" />
      <div className="pointer-events-none absolute -left-20 -bottom-20 h-72 w-72 rounded-full bg-teal/10 blur-3xl" />

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*,video/*,.txt,.md"
        className="hidden"
        onChange={handleFileSelect}
      />

      <div className="relative z-10">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-13 mb-21 border-b border-[#D8B478]/15 pb-13">
          <div>
            <div className="flex items-center gap-8">
              <span className="text-xs font-semibold uppercase tracking-wider text-gold">AI Content Studio</span>
              <span className="rounded-full bg-teal/15 border border-teal/30 px-8 py-0.5 text-[10px] font-semibold text-teal uppercase">
                Multi-Agent + Multilingual
              </span>
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-normal italic text-ink-light dark:text-ink-dark mt-4">
              Ingest Recording &amp; <em className="not-italic text-gold-soft">Configure Posts</em>
            </h2>
            <p className="mt-4 text-xs text-ink-dim max-w-2xl">
              Select which post types to synthesize, choose multilingual translation targets, and ingest your recording into the EventAI pipeline.
            </p>
          </div>

          <button
            type="button"
            onClick={loadSampleRecording}
            className="rounded-full border border-gold/40 bg-gold/10 px-13 py-6 text-xs font-medium text-gold-soft hover:bg-gold/20 hover:scale-105 transition-all shadow-sm"
          >
            ⚡ Try Sample Recording Demo
          </button>
        </div>

        {/* Media Upload Drag & Drop Target */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => !selectedFile && fileInputRef.current?.click()}
          className={`rounded-card border-2 border-dashed p-21 text-center transition-all ${
            isDragging
              ? "border-gold bg-gold/10"
              : selectedFile
              ? "border-gold/50 bg-white/[0.03]"
              : "border-white/15 bg-white/[0.02] hover:border-gold/40 cursor-pointer"
          }`}
        >
          {selectedFile ? (
            <div className="flex flex-wrap items-center justify-between gap-13">
              <div className="flex items-center gap-13 text-left">
                <span className="text-3xl">🎙️</span>
                <div>
                  <p className="font-medium text-sm text-gold-soft">{selectedFile.name}</p>
                  <p className="text-xs text-ink-dim">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type || "Event Recording Source"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-8">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  className="rounded-full border border-white/10 px-13 py-4 text-xs text-ink-dim hover:text-white"
                >
                  Change File
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFile(null);
                  }}
                  className="rounded-full border border-danger/30 bg-danger/10 px-13 py-4 text-xs text-danger hover:bg-danger/20"
                >
                  Remove
                </button>
              </div>
            </div>
          ) : (
            <div className="py-13">
              <span className="text-3xl block mb-8">📁</span>
              <p className="text-sm font-medium text-ink-light dark:text-ink-dark">
                Drag and drop your event audio or video here, or{" "}
                <span className="text-gold-soft underline">browse files</span>
              </p>
              <p className="mt-4 text-xs text-ink-dim">
                Supported formats: MP4, MOV, WEBM, MP3, WAV, M4A, or TXT transcript (up to 500 MB)
              </p>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* ARCHITECTURAL FLOW VISUALIZER (Matching User Diagram) */}
        {/* ========================================================================= */}
        <div className="mt-26 pt-21 border-t border-[#D8B478]/15">
          <div className="flex flex-wrap items-center justify-between gap-8 mb-13">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-gold">1. Post Generation Targets</span>
              <p className="text-xs text-ink-dim">Choose what kind of posts you want the AI pipeline to compose:</p>
            </div>
            <button
              type="button"
              onClick={selectAllTypes}
              className="text-[11px] font-medium text-gold-soft hover:underline"
            >
              Select All (6 Formats)
            </button>
          </div>

          {/* Top Row: 6 Colored Post Type Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-10">
            {POST_TYPES.map((pt) => {
              const isSelected = selectedTypes.includes(pt.id);
              return (
                <button
                  key={pt.id}
                  type="button"
                  onClick={() => toggleType(pt.id)}
                  className={`group relative flex flex-col items-center justify-between rounded-xl border p-13 text-center transition-all cursor-pointer ${
                    isSelected
                      ? pt.activeClass
                      : "border-white/10 bg-white/[0.02] text-ink-dim opacity-60 hover:opacity-100 hover:border-white/20"
                  }`}
                >
                  {/* Selection Checkmark */}
                  <div className="w-full flex justify-end mb-4">
                    <span
                      className={`h-4 w-4 rounded-full flex items-center justify-center text-[10px] ${
                        isSelected ? "bg-white/20 text-white" : "border border-white/20"
                      }`}
                    >
                      {isSelected ? "✓" : ""}
                    </span>
                  </div>

                  {/* Icon with Subtle Background */}
                  <div className="h-12 w-12 rounded-xl flex items-center justify-center text-2xl mb-8 bg-white/[0.05] border border-white/5 group-hover:scale-110 transition-transform">
                    {pt.icon}
                  </div>

                  {/* Label & Description */}
                  <div>
                    <h4 className="text-xs font-semibold tracking-wide text-ink-light dark:text-ink-dark">
                      {pt.title}
                    </h4>
                    <p className="mt-4 text-[10px] leading-tight opacity-75 hidden sm:block">
                      {pt.subtitle}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Visual Converging Flow Arrows */}
          <div className="relative my-13 flex justify-center items-center">
            <div className="h-6 w-px bg-gradient-to-b from-white/20 to-teal/50" />
            <span className="mx-8 text-[11px] font-mono text-teal uppercase tracking-widest bg-black/40 px-13 py-2 rounded-full border border-teal/30 shadow-[0_0_10px_rgba(20,184,166,0.2)]">
              ↓ Synthesized into Multilingual Formats ↓
            </span>
            <div className="h-6 w-px bg-gradient-to-b from-white/20 to-teal/50" />
          </div>

          {/* ===================================================================== */}
          {/* MULTILINGUAL TRANSLATION BANNER (Matching User Diagram) */}
          {/* ===================================================================== */}
          <div className="rounded-xl border border-teal/40 bg-gradient-to-r from-teal/15 via-[#164E63]/25 to-teal/15 p-16 shadow-[0_0_25px_rgba(20,184,166,0.15)]">
            <div className="flex flex-wrap items-center justify-between gap-13 mb-13">
              <div className="flex items-center gap-10">
                <div className="h-9 w-9 rounded-lg bg-teal/25 border border-teal/40 flex items-center justify-center text-lg">
                  🌐
                </div>
                <div>
                  <h3 className="font-sans text-sm font-bold tracking-wider text-teal uppercase flex items-center gap-8">
                    Multilingual Translation
                    <span className="text-[10px] font-normal normal-case opacity-75 text-teal-200">
                      (Powered by Gemini LLM Translation Pass)
                    </span>
                  </h3>
                  <p className="text-[11px] text-teal-100/80">
                    Each approved post above will be translated into your selected target languages automatically:
                  </p>
                </div>
              </div>

              <div className="text-[11px] font-mono text-teal-300">
                {selectedLanguages.length} Active {selectedLanguages.length === 1 ? "Language" : "Languages"}
              </div>
            </div>

            {/* Language Selection Pills */}
            <div className="flex flex-wrap gap-8">
              {AVAILABLE_LANGUAGES.map((lang) => {
                const active = selectedLanguages.includes(lang.code);
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => toggleLanguage(lang.code)}
                    className={`flex items-center gap-6 rounded-full px-13 py-6 text-xs font-medium transition-all ${
                      active
                        ? "border border-teal bg-teal/25 text-white shadow-[0_0_10px_rgba(20,184,166,0.3)] scale-105"
                        : "border border-white/10 bg-black/20 text-ink-dim hover:border-teal/40 hover:text-white"
                    }`}
                  >
                    <span>{lang.flag}</span>
                    <span>{lang.label}</span>
                    {active && <span className="text-[10px] text-teal">✓</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Visual Output Connector */}
          <div className="relative my-13 flex justify-center items-center">
            <div className="h-6 w-px bg-gradient-to-b from-teal/50 to-gold/50" />
            <span className="mx-8 text-[11px] font-mono text-gold-soft uppercase tracking-widest bg-black/40 px-13 py-2 rounded-full border border-gold/30">
              ↓ Delivered To ↓
            </span>
            <div className="h-6 w-px bg-gradient-to-b from-teal/50 to-gold/50" />
          </div>

          {/* ===================================================================== */}
          {/* USER DASHBOARD DESTINATION CARD (Matching User Diagram) */}
          {/* ===================================================================== */}
          <div className="rounded-xl border border-gold/40 bg-gradient-to-r from-gold/10 via-[#2A241E]/30 to-gold/10 p-13 flex flex-wrap items-center justify-between gap-13 shadow-sm">
            <div className="flex items-center gap-10">
              <span className="text-2xl">🖥️</span>
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-gold-soft">
                  User Dashboard Workspace
                </h4>
                <p className="text-[11px] text-ink-dim">
                  Interactive content studio: <span className="text-gold-soft">view</span>, in-line edit, <span className="text-gold-soft">download</span> (Markdown, TXT, JSON), and <span className="text-gold-soft">share</span>.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-13 text-xs text-ink-dim font-mono">
              <span>✓ Human Review Gate</span>
              <span>✓ Grounding Anti-Hallucination</span>
            </div>
          </div>
        </div>

        {/* Consent Checkbox */}
        <div className="mt-21 border-t border-[#D8B478]/15 pt-13 flex flex-wrap items-center justify-between gap-13">
          <label className="flex items-center gap-8 text-xs text-ink-dim cursor-pointer">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="accent-gold h-4 w-4 rounded"
            />
            <span>
              Confirm participant consent for recording ingestion, speech-to-text, and AI synthesis
            </span>
          </label>

          {error && (
            <div className="text-xs text-danger font-medium">
              ⚠️ {error}
            </div>
          )}
        </div>

        {/* Submit Execution Button */}
        <div className="mt-13 flex items-center justify-end">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={upload.isPending}
            className="inline-flex items-center gap-13 rounded-full border border-gold/50 bg-gradient-to-r from-gold/30 via-lavender/25 to-teal/20 px-34 py-13 font-sans text-sm font-semibold tracking-wide text-gold-soft shadow-[0_10px_28px_rgba(216,180,120,0.2)] transition-all hover:scale-105 hover:border-gold disabled:opacity-50"
          >
            {upload.isPending ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-gold-soft border-t-transparent" />
                <span>Ingesting Recording &amp; Generating Posts…</span>
              </>
            ) : selectedFile ? (
              <>
                <span>Generate {selectedTypes.length} Posts in {selectedLanguages.length} Languages</span>
                <span>→</span>
              </>
            ) : (
              <>
                <span>Select Recording File to Begin</span>
                <span>→</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
