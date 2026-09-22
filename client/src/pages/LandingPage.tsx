import { useState, useRef, useEffect, type ChangeEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { uploadRecording } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

const CONTENT_TYPES = "summary,blog,linkedin,newsletter,ig_caption,flyer";

export function LandingPage() {
  const token = useAuthStore((s) => s.accessToken);
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(true);
  const languages = "en,hi";
  const [error, setError] = useState<string | null>(null);
  const [readyCount, setReadyCount] = useState(0);

  // Status strip animated count
  useEffect(() => {
    const timer = setTimeout(() => {
      let n = 0;
      const iv = setInterval(() => {
        n++;
        setReadyCount(n);
        if (n >= 4) clearInterval(iv);
      }, 240);
    }, 900);
    return () => clearTimeout(timer);
  }, []);

  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadRecording(token as string, file, { consent, languages, types: CONTENT_TYPES }),
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: Error) => setError(err.message),
  });

  function handleFileSelect(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
    }
  }

  function handleTriggerUpload() {
    if (!token) {
      navigate("/register");
      return;
    }
    if (!selectedFile) {
      fileInputRef.current?.click();
      return;
    }
    if (!consent) {
      setError("Please confirm participant consent before processing.");
      return;
    }
    upload.mutate(selectedFile);
  }

  return (
    <GoldenShell>
      <div className="space-y-55">
        {/* Hidden File Input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,video/*,.txt,.md"
          className="hidden"
          onChange={handleFileSelect}
        />

        {/* Hero Section (1.618fr : 1fr Golden Split) */}
        <div className="grid items-center gap-34 lg:grid-cols-[1.618fr_1fr]">
          <div>
            <div className="reveal r2 mb-13 text-xs font-semibold tracking-[0.2em] text-gold uppercase">
              From Recording to Content
            </div>

            <h1 className="reveal r3 font-display text-4xl font-normal italic leading-tight text-ink-light sm:text-5xl dark:text-ink-dark">
              Every recording, quietly{" "}
              <em className="not-italic bg-gradient-to-r from-gold-soft via-lavender to-teal bg-clip-text text-transparent drop-shadow-[0_0_18px_rgba(216,180,120,0.25)]">
                composed
              </em>{" "}
              into a story.
            </h1>

            <div className="reveal r4 my-21 h-[1px] w-16 bg-gradient-to-r from-gold to-transparent" />

            <p className="reveal r5 max-w-lg text-base font-light leading-relaxed text-ink-light/70 dark:text-ink-dim">
              Drop in an event recording and let it unfold — topics, highlights, sentiment, and speakers, drawn out and rewoven into content worth publishing.
            </p>

            {/* Selected File Badge & Options */}
            {selectedFile ? (
              <div className="reveal r6 mt-21 max-w-lg glass p-13 text-xs space-y-8 border-gold/40">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-gold dark:text-gold-soft">📎 {selectedFile.name}</span>
                  <button
                    type="button"
                    onClick={() => setSelectedFile(null)}
                    className="text-danger hover:underline"
                  >
                    Remove
                  </button>
                </div>
                <label className="flex items-center gap-8 text-[11px] opacity-80 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="accent-gold"
                  />
                  Participants informed recording may be processed (Consent confirmed)
                </label>
              </div>
            ) : null}

            {error && <p className="mt-13 text-xs text-danger">{error}</p>}

            {/* Primary Action & Quick Demo Buttons */}
            <div className="reveal r6 mt-21 flex flex-wrap items-center gap-13">
              <button
                type="button"
                onClick={handleTriggerUpload}
                disabled={upload.isPending}
                className="group inline-flex items-center gap-13 rounded-full border border-gold/30 bg-gradient-to-r from-[#D8B478]/20 via-[#B9A6DA]/15 to-[#6FCFC4]/10 px-34 py-13 font-sans text-sm font-medium tracking-wide text-gold dark:text-gold-soft shadow-[0_10px_28px_rgba(216,180,120,0.15)] transition-all hover:scale-105 hover:border-gold"
              >
                <span>
                  {upload.isPending
                    ? "Ingesting Recording…"
                    : selectedFile
                    ? "Begin Content Synthesis"
                    : token
                    ? "Select Event Recording"
                    : "Register Account to Begin Session"}
                </span>
                <span className="transition-transform group-hover:translate-x-1">→</span>
              </button>

              {!selectedFile && (
                <button
                  type="button"
                  onClick={() => {
                    fetch("/data/samples/clean_event_session.txt")
                      .then((r) => r.text())
                      .then((txt) => {
                        const f = new File([txt], "clean_event_session.txt", { type: "text/plain" });
                        setSelectedFile(f);
                      })
                      .catch(() => {
                        const f = new File(["Welcome to the EventAI keynote demo session."], "clean_event_session.txt", { type: "text/plain" });
                        setSelectedFile(f);
                      });
                  }}
                  className="rounded-full border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-21 py-13 text-xs text-ink-light/60 dark:text-ink-dim hover:text-gold dark:hover:text-gold-soft hover:border-gold/30 transition-all"
                >
                  ⚡ Try Sample Recording
                </button>
              )}
            </div>
          </div>

          {/* Neuromorphic Stage Upload Target */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="glass neo-stage reveal r4 cursor-pointer p-34 text-center transition-transform hover:scale-[1.02]"
            title="Click to choose a file"
          >
            <div className="relative my-21">
              <div className="pulse-ring" />
              <div className="pulse-ring d2" />
              <div className="neo-btn">
                <div className="dot" />
              </div>
            </div>
            <div className="neo-label text-xs uppercase tracking-widest text-ink-dim">
              {selectedFile ? `READY: ${selectedFile.name}` : "LISTENING FOR UPLOAD"}
            </div>
            <p className="mt-8 text-[11px] opacity-50">Audio, Video, or .txt Transcripts</p>
          </div>
        </div>

        {/* 3 Specialist Agent Tiles */}
        <div className="grid gap-21 md:grid-cols-3">
          <div className="glass p-21 reveal r7 group cursor-default transition-all">
            <div className="mb-13 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-lavender to-teal text-base font-bold text-[#101322] shadow-[0_0_15px_rgba(185,166,218,0.4)] transition-transform group-hover:scale-110">
              ◎
            </div>
            <h3 className="font-display text-lg font-medium text-ink-light dark:text-ink-dark">
              Topic extraction
            </h3>
            <p className="mt-8 text-xs leading-relaxed text-ink-light/60 dark:text-ink-dim">
              Surfaces the core architectural themes and concepts your audience actually leaned into.
            </p>
          </div>

          <div className="glass p-21 reveal r8 group cursor-default transition-all">
            <div className="mb-13 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-lavender to-teal text-base font-bold text-[#101322] shadow-[0_0_15px_rgba(185,166,218,0.4)] transition-transform group-hover:scale-110">
              ✦
            </div>
            <h3 className="font-display text-lg font-medium text-ink-light dark:text-ink-dark">
              Highlight detection
            </h3>
            <p className="mt-8 text-xs leading-relaxed text-ink-light/60 dark:text-ink-dim">
              Pinpoints high-impact quotable moments worth clipping, sharing, or leading with.
            </p>
          </div>

          <div className="glass p-21 reveal r9 group cursor-default transition-all">
            <div className="mb-13 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-lavender to-teal text-base font-bold text-[#101322] shadow-[0_0_15px_rgba(185,166,218,0.4)] transition-transform group-hover:scale-110">
              ◐
            </div>
            <h3 className="font-display text-lg font-medium text-ink-light dark:text-ink-dark">
              Sentiment &amp; tone
            </h3>
            <p className="mt-8 text-xs leading-relaxed text-ink-light/60 dark:text-ink-dim">
              Reads the room so every piece of generated copy matches the energy and mood of the session.
            </p>
          </div>
        </div>

        {/* Live Status Strip */}
        <div className="glass reveal r9 flex flex-wrap items-center justify-between gap-13 px-21 py-13 text-xs">
          <div className="flex items-center gap-13">
            <div className="h-2 w-2 rounded-full bg-teal animate-ping" />
            <span className="text-ink-light/60 dark:text-ink-dim">
              Transcribing —{" "}
              <span className="font-semibold text-gold dark:text-gold-soft">
                {readyCount} of 6 pieces ready
              </span>
            </span>
          </div>
          <span className="text-ink-dim">
            Sentiment &amp; speaker analysis running in parallel…
          </span>
        </div>

        {/* Existing Jobs Footer Link */}
        <div className="text-center pt-13 text-xs text-ink-light/60 dark:text-ink-dim">
          Looking for past generated content?{" "}
          <Link to="/dashboard" className="text-gold dark:text-gold-soft underline hover:text-ink-light dark:hover:text-white">
            Open your Workspace Dashboard →
          </Link>
        </div>
      </div>
    </GoldenShell>
  );
}
