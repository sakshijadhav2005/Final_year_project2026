import { useState, useRef, useEffect, type ChangeEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { uploadRecording, listMyEvents } from "@/lib/api";
import { NeuSwitch } from "@/components/ui/NeuSwitch";
import { useAuthStore } from "@/store/auth";

// The 6 post formats exactly as specified in the architectural flowchart
const POST_TYPES = [
  {
    id: "blog",
    title: "Blog",
    subtitle: "Long-form article with section headers",
    icon: "📄",
    color: "blue",
    activeClass: "border-amber-400/60 bg-amber-400/[0.06] text-amber-300",
    badgeClass: "bg-amber-400/15 text-amber-300",
    glowClass: "",
  },
  {
    id: "newsletter",
    title: "Newsletter",
    subtitle: "Email briefing with punchy highlights",
    icon: "✉️",
    color: "green",
    activeClass: "border-amber-400/60 bg-amber-400/[0.06] text-amber-300",
    badgeClass: "bg-amber-400/15 text-amber-300",
    glowClass: "",
  },
  {
    id: "linkedin",
    title: "LinkedIn Post",
    subtitle: "Professional hook, takeaways & hashtags",
    icon: "💼",
    color: "purple",
    activeClass: "border-amber-400/60 bg-amber-400/[0.06] text-amber-300",
    badgeClass: "bg-amber-400/15 text-amber-300",
    glowClass: "",
  },
  {
    id: "ig_caption",
    title: "Instagram Caption",
    subtitle: "Engaging social copy, emojis & tags",
    icon: "📸",
    color: "orange",
    activeClass: "border-amber-400/60 bg-amber-400/[0.06] text-amber-300",
    badgeClass: "bg-amber-400/15 text-amber-300",
    glowClass: "",
  },
  {
    id: "summary",
    title: "Event Summary",
    subtitle: "Executive overview & action items",
    icon: "📅",
    color: "pink",
    activeClass: "border-amber-400/60 bg-amber-400/[0.06] text-amber-300",
    badgeClass: "bg-amber-400/15 text-amber-300",
    glowClass: "",
  },
  {
    id: "flyer",
    title: "Flyer",
    subtitle: "Visual poster copy & key slogans",
    icon: "📢",
    color: "teal",
    activeClass: "border-amber-400/60 bg-amber-400/[0.06] text-amber-300",
    badgeClass: "bg-amber-400/15 text-amber-300",
    glowClass: "",
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
    queryFn: () => listMyEvents(token as string),
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
    <div className="relative rounded-panel border border-white/[0.08] bg-surface p-21 sm:p-34">

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*,video/*,.ogg,.oga,.opus,.flac,.aac,.weba,.mkv,.avi,.m4v,.3gp,.txt,.md"
        className="hidden"
        onChange={handleFileSelect}
      />

      <div className="space-y-34">
        {/* Header Bar */}
        <div className="flex flex-wrap items-end justify-between gap-21">
          <div>
            <h2 className="font-display text-h2 font-semibold text-ink">
              New recording
            </h2>
            <p className="mt-[4px] max-w-[60ch] text-sm text-ink-dim">
              Upload a talk, pick the formats and languages, and the agents draft everything for your review.
            </p>
          </div>

          <button
            type="button"
            onClick={loadSampleRecording}
            className="inline-flex items-center gap-8 rounded-full border border-white/[0.12] px-21 py-8 text-sm text-ink transition-colors hover:border-amber-400/50"
          >
            <span>Use the sample talk</span>
          </button>
        </div>

        <div className="grid grid-cols-1 gap-34 lg:grid-cols-golden lg:items-start">
          <div className="min-w-0 space-y-34">
            {/* Media Upload Drag & Drop Target */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => !selectedFile && fileInputRef.current?.click()}
              className={`rounded-panel border border-dashed p-34 text-center transition-colors ${
                isDragging
                  ? "drop-active border-amber-400"
                  : selectedFile
                  ? "neu-inset border-amber-400/50"
                  : "neu-inset cursor-pointer border-white/[0.1] hover:border-amber-400/50"
              }`}
            >
              {selectedFile ? (
                <div className="flex flex-wrap items-center justify-between gap-13">
                  <div className="flex items-center gap-13 text-left">
                    <span className="text-3xl">🎙️</span>
                    <div>
                      <p className="font-semibold text-sm text-amber-300">{selectedFile.name}</p>
                      <p className="text-xs text-slate-400">
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
                      className="rounded-card border border-white/[0.08] bg-white/5 px-13 py-8 text-xs text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
                    >
                      Change File
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFile(null);
                      }}
                      className="rounded-card border border-rose-500/30 bg-rose-500/10 px-13 py-8 text-xs text-rose-300 hover:bg-rose-500/20 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ) : (
                <div className="py-13">
                  <span className="neu-raised mx-auto mb-13 flex h-[55px] w-[55px] items-center justify-center rounded-full bg-surface-raised text-2xl">🎙️</span>
                  <p className="text-base font-medium text-ink">
                    Drop your event recording here, or{" "}
                    <span className="text-amber-300 underline underline-offset-4">browse</span>
                  </p>
                  <p className="mt-8 text-xs text-ink-dim">
                    MP4, MOV, WEBM, MKV, MP3, WAV, M4A, OGG, OPUS, FLAC, AAC or a .txt transcript, up to 500 MB
                  </p>
                </div>
              )}
            </div>

            {/* Post Generation Targets */}
            <div className="space-y-13">
              <div className="flex flex-wrap items-center justify-between gap-8">
                <div>
                  <h3 className="text-sm font-semibold text-ink">Formats</h3>
                  <p className="text-xs text-ink-dim">Choose the posts the agents should write.</p>
                </div>
                <button
                  type="button"
                  onClick={selectAllTypes}
                  className="text-xs font-semibold text-amber-300 hover:underline"
                >
                  Select all
                </button>
              </div>

              {/* Top Row: 6 Colored Post Type Cards */}
              <div className="grid grid-cols-2 gap-13 sm:grid-cols-3">
                {POST_TYPES.map((pt) => {
                  const isSelected = selectedTypes.includes(pt.id);
                  return (
                    <button
                      key={pt.id}
                      type="button"
                      onClick={() => toggleType(pt.id)}
                      className={`relative flex flex-col items-start rounded-card border p-13 text-left transition-colors ${
                        isSelected
                          ? `${pt.activeClass} neu-pressed`
                          : "neu-raised border-white/[0.06] bg-white/[0.02] text-ink-dim hover:text-ink"
                      }`}
                    >
                      {/* Selection Checkmark */}
                      <div className="absolute right-13 top-13">
                        <span
                          className={`h-4 w-4 rounded-full flex items-center justify-center text-[10px] ${
                            isSelected ? "tick-pop bg-amber-400 font-bold text-on-accent" : "border border-white/25"
                          }`}
                        >
                          {isSelected ? "✓" : ""}
                        </span>
                      </div>

                      {/* Icon with Subtle Background */}
                      <div className="mb-13 flex h-[34px] w-[34px] items-center justify-center rounded-card bg-white/[0.05] text-lg">
                        {pt.icon}
                      </div>

                      {/* Label & Description */}
                      <div>
                        <h4 className="text-sm font-semibold text-ink">
                          {pt.title}
                        </h4>
                        <p className="mt-[4px] text-xs leading-snug text-ink-dim">
                          {pt.subtitle}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Multilingual Translation Banner */}
              <div className="space-y-13">
                <div className="flex flex-wrap items-center justify-between gap-13 mb-13">
                  <div className="flex items-center gap-8">
                                        <div>
                      <h3 className="flex items-center gap-8 text-sm font-semibold text-ink">
                        <span>Languages</span>
                        
                      </h3>
                      <p className="text-xs text-ink-dim">
                        Each post is also translated into the languages you pick.
                      </p>
                    </div>
                  </div>

                  <div className="rounded-full bg-white/[0.05] px-13 py-[5px] text-xs text-ink-dim">
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
                        className={`inline-flex items-center gap-8 rounded-full px-13 py-8 text-sm transition-colors ${
                          active
                            ? "neu-pressed border border-amber-400/60 bg-amber-400/[0.08] text-ink"
                            : "neu-raised border border-white/[0.06] bg-white/[0.02] text-ink-dim hover:text-ink"
                        }`}
                      >
                                                <span>{lang.label}</span>
                        {active && <span className="text-xs text-amber-300">✓</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          <aside className="min-w-0 space-y-21 lg:sticky lg:top-[89px]">
            {/* Target Event Linking Bar */}
            <div className="rounded-card border border-white/[0.08] bg-white/[0.02] p-21">
              {selectedEvent ? (
                <div className="flex flex-wrap items-center justify-between gap-13">
                  <div className="flex items-center gap-13">
                    <span className="text-2xl">🎪</span>
                    <div>
                      <div className="flex items-center gap-8">
                        <span className="text-xs font-bold text-amber-300">Linked Event:</span>
                        <span className="text-xs font-semibold text-white">{selectedEvent.name}</span>
                        <span className="rounded bg-amber-500/20 px-8 py-0.5 text-[10px] font-bold text-amber-300">
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
                    className="rounded-lg border border-white/[0.08] bg-white/5 px-13 py-8 text-xs text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                  >
                    ✕ Detach / Change Event
                  </button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-13">
                  <div className="flex items-center gap-13">
                    <span className="text-xs font-semibold text-slate-300">Target Event:</span>
                    <select
                      value={selectedEventId}
                      onChange={(e) => setSelectedEventId(e.target.value)}
                      className="w-full min-w-0 rounded-card border border-white/[0.08] bg-slate-900 px-13 py-8 text-xs text-slate-200 focus:border-amber-500 focus:outline-none"
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

            <div className="rounded-card border border-white/[0.08] bg-white/[0.02] p-21">
              <p className="text-sm text-ink-dim">You will get</p>
              <p className="mt-[4px] font-display text-h2 text-ink">
                {selectedTypes.length} {selectedTypes.length === 1 ? "format" : "formats"} in {selectedLanguages.length}{" "}
                {selectedLanguages.length === 1 ? "language" : "languages"}
              </p>
              <p className="mt-8 text-xs leading-relaxed text-ink-dim">
                Every draft waits for your approval before it is marked ready to publish.
              </p>
            </div>

            {/* Consent Checkbox */}
            <div className="space-y-8">
              <NeuSwitch
                checked={consent}
                onChange={setConsent}
                className="text-xs leading-relaxed text-ink-dim"
                label="Participants know this recording will be transcribed and processed by AI."
              />

              {error && (
                <div className="text-xs text-rose-400 font-semibold">
                  ⚠️ {error}
                </div>
              )}
            </div>

            {/* Submit Execution Button */}
            <div>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={upload.isPending}
                className="btn-primary w-full py-13"
              >
                {upload.isPending ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-on-accent border-t-transparent" />
                    <span>Uploading and generating…</span>
                  </>
                ) : selectedFile ? (
                  <>
                    <span>Generate {selectedTypes.length * selectedLanguages.length} drafts</span>
                  </>
                ) : (
                  <>
                    <span>Choose a recording first</span>
                  </>
                )}
              </button>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
