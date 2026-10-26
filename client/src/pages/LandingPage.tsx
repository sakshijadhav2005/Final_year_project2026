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
          accept="audio/*,video/*,.ogg,.oga,.opus,.flac,.aac,.weba,.mkv,.avi,.m4v,.3gp,.txt,.md"
          className="hidden"
          onChange={handleFileSelect}
        />

        {/* Hero Section (1.618fr : 1fr Golden Split) */}
        <div className="grid items-center gap-34 lg:grid-cols-[1.618fr_1fr]">
          <div>
            <h1 className="reveal r3 max-w-[16ch] font-display text-[42px] font-semibold leading-[1.05] tracking-[-0.025em] text-ink sm:text-display">
              Every recording, composed into a story.
            </h1>

            <p className="reveal r5 mt-21 max-w-[52ch] text-[17px] leading-relaxed text-ink-dim">
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
                className="btn-primary py-13"
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
              </button>
            </div>
          </div>

          {/* Neuromorphic Stage Upload Target */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="glass neo-stage reveal r4 cursor-pointer p-34 text-center transition-colors hover:border-amber-400/40"
            title="Click to choose a file"
          >
            <div className="relative my-21">
              <div className="pulse-ring" />
              <div className="pulse-ring d2" />
              <div className="neo-btn">
                <div className="dot" />
              </div>
            </div>
            <div className="text-sm font-medium text-ink">
              {selectedFile ? `Ready: ${selectedFile.name}` : "Drop a recording here"}
            </div>
            <p className="mt-8 text-xs text-ink-dim">Audio, video or a .txt transcript</p>
          </div>
        </div>

        {/* 3 Specialist Agent Tiles */}
        <div className="grid gap-21 md:grid-cols-3">
          <div className="neu-tile p-34 reveal r7">
            <div className="neu-tile-icon mb-21 font-semibold" aria-hidden="true">
              ◎
            </div>
            <h3 className="font-display text-h3 text-ink">
              Topic extraction
            </h3>
            <p className="mt-8 text-sm leading-relaxed text-ink-dim">
              Surfaces the core architectural themes and concepts your audience actually leaned into.
            </p>
          </div>

          <div className="neu-tile p-34 reveal r8">
            <div className="neu-tile-icon mb-21 font-semibold" aria-hidden="true">
              ✦
            </div>
            <h3 className="font-display text-h3 text-ink">
              Highlight detection
            </h3>
            <p className="mt-8 text-sm leading-relaxed text-ink-dim">
              Pinpoints high-impact quotable moments worth clipping, sharing, or leading with.
            </p>
          </div>

          <div className="neu-tile p-34 reveal r9">
            <div className="neu-tile-icon mb-21 font-semibold" aria-hidden="true">
              ◐
            </div>
            <h3 className="font-display text-h3 text-ink">
              Sentiment &amp; tone
            </h3>
            <p className="mt-8 text-sm leading-relaxed text-ink-dim">
              Reads the room so every piece of generated copy matches the energy and mood of the session.
            </p>
          </div>
        </div>

        {/* Live Status Strip */}
        <div className="glass reveal r9 flex flex-wrap items-center justify-between gap-13 px-21 py-13 text-xs">
          <div className="flex items-center gap-13">
            <div className="h-2 w-2 rounded-full bg-teal" />
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
