import { useState, useRef, useEffect, type ChangeEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { uploadRecording, listEvents } from "@/lib/api";
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
  { code: "en", label: "English", country: "GB", flag: "🇬🇧" },
  { code: "hi", label: "Hindi (हिंदी)", country: "IN", flag: "🇮🇳" },
  { code: "es", label: "Spanish", country: "ES", flag: "🇪🇸" },
  { code: "fr", label: "French", country: "FR", flag: "🇫🇷" },
  { code: "de", label: "German", country: "DE", flag: "🇩🇪" },
  { code: "ja", label: "Japanese", country: "JP", flag: "🇯🇵" },
  { code: "pt", label: "Portuguese", country: "BR", flag: "🇧🇷" },
];

export function DashboardUploadCard() {
  const token = useAuthStore((s) => s.accessToken);
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [searchParams, setSearchParams] = useSearchParams();
  const eventIdParam = searchParams.get("event_id") || "";

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
  const [selectedEventId, setSelectedEventId] = useState<string>(eventIdParam);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (eventIdParam) {
      setSelectedEventId(eventIdParam);
    }
  }, [eventIdParam]);

  const { data: events = [] } = useQuery({
    queryKey: ["my_events"],
    queryFn: () => listEvents(token as string),
    enabled: !!token,
  });

  const selectedEvent = events.find((ev) => ev.id === selectedEventId);

  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadRecording(token as string, file, {
        consent,
        languages: selectedLanguages.join(","),
        types: selectedTypes.join(","),
        event_id: selectedEventId || undefined,
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
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6 md:p-8 shadow-xl backdrop-blur-xl relative overflow-hidden space-y-6">
      {/* Decorative ambient gradients */}
      <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-amber-500/10 blur-3xl" />
      <div className="pointer-events-none absolute -left-20 -bottom-20 h-72 w-72 rounded-full bg-orange-500/10 blur-3xl" />

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*,video/*,.txt,.md"
        className="hidden"
        onChange={handleFileSelect}
      />

      <div className="relative z-10 space-y-6">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-400">AI Content Studio</span>
              <span className="rounded-full bg-amber-500/20 border border-amber-500/30 px-2.5 py-0.5 text-[10px] font-bold text-amber-300 uppercase">
                Multi-Agent + Multilingual
              </span>
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-bold text-white mt-1">
              Ingest Recording &amp; <em className="not-italic text-amber-300">Configure Posts</em>
            </h2>
            <p className="mt-1 text-xs text-slate-400 max-w-2xl">
              Select which post types to synthesize, choose multilingual translation targets, and ingest your recording into the EventAI pipeline.
            </p>
          </div>

          <button
            type="button"
            onClick={loadSampleRecording}
            className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 hover:scale-105 transition-all shadow-sm"
          >
            <span>⚡ Try Sample Recording Demo</span>
          </button>
        </div>

        {/* Target Event Linking Bar */}
        <div className="rounded-xl border border-white/10 bg-slate-950/60 p-4">
          {selectedEvent ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🎪</span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-amber-300">Linked Event:</span>
                    <span className="text-xs font-semibold text-white">{selectedEvent.name}</span>
                    <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300 uppercase">
                      {selectedEvent.type}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    All 6 generated AI posts and full speech transcript will be attached to this event's hub.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  setSelectedEventId("");
                  setSearchParams({});
                }}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                ✕ Detach / Change Event
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold text-slate-300">Target Event:</span>
                <select
                  value={selectedEventId}
                  onChange={(e) => setSelectedEventId(e.target.value)}
                  className="rounded-xl border border-white/10 bg-slate-900 px-3.5 py-2 text-xs text-slate-200 focus:border-amber-500 focus:outline-none"
                >
                  <option value="">General Session (No Specific Event Linked)</option>
                  {events.map((ev) => (
                    <option key={ev.id} value={ev.id}>
                      {ev.name} ({ev.type})
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={() => navigate("/catalog/all")}
                className="text-xs text-amber-400 hover:text-amber-300 hover:underline flex items-center gap-1 font-semibold"
              >
                <span>➕ Create New Event</span>
              </button>
            </div>
          )}
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
          className={`rounded-2xl border-2 border-dashed p-6 text-center transition-all ${
            isDragging
              ? "border-amber-500 bg-amber-500/10"
              : selectedFile
              ? "border-amber-500/50 bg-slate-950/60"
              : "border-white/15 bg-slate-950/40 hover:border-amber-500/40 hover:bg-amber-500/5 cursor-pointer"
          }`}
        >
          {selectedFile ? (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3 text-left">
                <span className="text-3xl">🎙️</span>
                <div>
                  <p className="font-semibold text-sm text-amber-300">{selectedFile.name}</p>
                  <p className="text-xs text-slate-400">
                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type || "Event Recording Source"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  className="rounded-xl border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
                >
                  Change File
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFile(null);
                  }}
                  className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-1.5 text-xs text-rose-300 hover:bg-rose-500/20 transition-colors"
                >
                  Remove
                </button>
              </div>
            </div>
          ) : (
            <div className="py-4">
              <span className="text-4xl block mb-3">📁</span>
              <p className="text-sm font-semibold text-slate-200">
                Drag and drop your event audio or video here, or{" "}
                <span className="text-amber-400 underline">browse files</span>
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Supported formats: MP4, MOV, WEBM, MP3, WAV, M4A, or TXT transcript (up to 500 MB)
              </p>
            </div>
          )}
        </div>

        {/* Post Generation Targets */}
        <div className="border-t border-white/10 pt-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-amber-400">1. Post Generation Targets</span>
              <p className="text-xs text-slate-400">Choose what kind of posts you want the AI pipeline to compose:</p>
            </div>
            <button
              type="button"
              onClick={selectAllTypes}
              className="text-xs font-semibold text-amber-300 hover:underline"
            >
              Select All (6 Formats)
            </button>
          </div>

          {/* Top Row: 6 Colored Post Type Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {POST_TYPES.map((pt) => {
              const isSelected = selectedTypes.includes(pt.id);
              return (
                <button
                  key={pt.id}
                  type="button"
                  onClick={() => toggleType(pt.id)}
                  className={`group relative flex flex-col items-center justify-between rounded-xl border p-3.5 text-center transition-all cursor-pointer ${
                    isSelected
                      ? pt.activeClass
                      : "border-white/10 bg-slate-950/60 text-slate-400 opacity-60 hover:opacity-100 hover:border-white/20"
                  }`}
                >
                  {/* Selection Checkmark */}
                  <div className="w-full flex justify-end mb-2">
                    <span
                      className={`h-4 w-4 rounded-full flex items-center justify-center text-[10px] ${
                        isSelected ? "bg-white/20 text-white font-bold" : "border border-white/20"
                      }`}
                    >
                      {isSelected ? "✓" : ""}
                    </span>
                  </div>

                  {/* Icon with Subtle Background */}
                  <div className="h-10 w-10 rounded-xl flex items-center justify-center text-2xl mb-2 bg-white/[0.05] border border-white/5 group-hover:scale-110 transition-transform">
                    {pt.icon}
                  </div>

                  {/* Label & Description */}
                  <div>
                    <h4 className="text-xs font-bold tracking-wide text-white">
                      {pt.title}
                    </h4>
                    <p className="mt-1 text-[10px] leading-tight opacity-75 hidden sm:block">
                      {pt.subtitle}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Visual Converging Flow Arrows */}
          <div className="relative my-3 flex justify-center items-center">
            <div className="h-5 w-px bg-gradient-to-b from-white/20 to-teal-500/50" />
            <span className="mx-3 text-[10px] font-mono font-bold text-teal-300 uppercase tracking-widest bg-slate-950 px-3 py-1 rounded-full border border-teal-500/30">
              ↓ Synthesized into Multilingual Formats ↓
            </span>
            <div className="h-5 w-px bg-gradient-to-b from-white/20 to-teal-500/50" />
          </div>

          {/* Multilingual Translation Banner */}
          <div className="rounded-2xl border border-teal-500/30 bg-gradient-to-r from-teal-950/40 via-slate-900/90 to-teal-950/40 p-4 shadow-lg backdrop-blur-xl">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2.5">
                <div className="h-7 w-7 rounded-lg bg-teal-500/20 border border-teal-500/30 flex items-center justify-center text-sm">
                  🌐
                </div>
                <div>
                  <h3 className="text-xs font-bold tracking-wider text-teal-400 uppercase flex items-center gap-2">
                    <span>Multilingual Translation</span>
                    <span className="text-[10px] font-normal normal-case text-teal-200/70">
                      (Powered by Gemini LLM Pass)
                    </span>
                  </h3>
                  <p className="text-[11px] text-teal-100/70">
                    Each approved post above will be translated into your selected target languages automatically:
                  </p>
                </div>
              </div>

              <div className="text-[10px] font-mono font-bold text-teal-300 bg-teal-500/10 px-2.5 py-1 rounded-full border border-teal-500/30">
                {selectedLanguages.length} Active {selectedLanguages.length === 1 ? "Language" : "Languages"}
              </div>
            </div>

            {/* Language Selection Pills */}
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
              {AVAILABLE_LANGUAGES.map((lang) => {
                const active = selectedLanguages.includes(lang.code);
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => toggleLanguage(lang.code)}
                    className={`flex items-center justify-center gap-1.5 rounded-xl px-2 py-2 text-xs font-medium transition-all ${
                      active
                        ? "border border-teal-400 bg-teal-500/20 text-white shadow-[0_0_12px_rgba(20,184,166,0.35)] ring-1 ring-teal-400/50"
                        : "border border-white/10 bg-slate-950/60 text-slate-400 hover:border-teal-500/40 hover:text-white hover:bg-slate-900"
                    }`}
                  >
                    <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">{lang.country}</span>
                    <span className="text-[11px] font-semibold truncate">{lang.label}</span>
                    {active && <span className="text-[10px] font-bold text-teal-300">✓</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Visual Output Connector */}
          <div className="relative my-3 flex justify-center items-center">
            <div className="h-5 w-px bg-gradient-to-b from-teal-500/50 to-amber-500/50" />
            <span className="mx-3 text-[10px] font-mono font-bold text-amber-300 uppercase tracking-widest bg-slate-950 px-3 py-1 rounded-full border border-amber-500/30">
              ↓ Delivered To Content Hub ↓
            </span>
            <div className="h-5 w-px bg-gradient-to-b from-teal-500/50 to-amber-500/50" />
          </div>

          {/* User Dashboard Destination Card */}
          <div className="rounded-xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-slate-900/60 to-amber-500/10 p-4 flex flex-wrap items-center justify-between gap-3 shadow-sm">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🖥️</span>
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-300">
                  Dashboard &amp; Studio Workspace
                </h4>
                <p className="text-[11px] text-slate-400">
                  Interactive content studio: <span className="text-amber-300 font-semibold">view</span>, in-line edit, <span className="text-amber-300 font-semibold">download</span> (Markdown, TXT, JSON), and <span className="text-amber-300 font-semibold">share</span>.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
              <span className="text-emerald-400">✓ Human Review Gate</span>
              <span className="text-emerald-400">✓ Grounding Verification</span>
            </div>
          </div>
        </div>

        {/* Consent Checkbox */}
        <div className="border-t border-white/10 pt-4 flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="accent-amber-500 h-4 w-4 rounded"
            />
            <span>
              Confirm participant consent for recording ingestion, speech-to-text, and AI synthesis
            </span>
          </label>

          {error && (
            <div className="text-xs text-rose-400 font-semibold">
              ⚠️ {error}
            </div>
          )}
        </div>

        {/* Submit Execution Button */}
        <div className="flex items-center justify-end pt-2">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={upload.isPending}
            className="inline-flex items-center gap-2 rounded-full border border-amber-500/40 bg-gradient-to-r from-amber-500 to-orange-600 px-8 py-3 text-sm font-bold text-white shadow-lg shadow-orange-500/20 transition-all hover:scale-105 hover:shadow-orange-500/30 disabled:opacity-50"
          >
            {upload.isPending ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
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
