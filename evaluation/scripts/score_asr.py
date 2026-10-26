"""WER / CER of EventAI transcripts against the TED-LIUM 3 human references.

Normalisation (both sides): TED-LIUM <unk> tokens removed from references, then the
Whisper English text normaliser (lower-case, punctuation, numbers/spelling forms),
as in the ESB / Open ASR Leaderboard protocol. Disfluencies such as "um" are removed
by that normaliser on both sides.

Hypotheses: transcripts stored by the app in the e2e runs (results/raw/*__e2e__*.json)
and any STT-only runs in results/stt/*.json.

    python evaluation/scripts/score_asr.py
"""

from __future__ import annotations

import csv
import glob
import json
import re

import jiwer
from whisper_normalizer.english import EnglishTextNormalizer

import harness

norm = EnglishTextNormalizer()


def clean_ref(text: str) -> str:
    return re.sub(r"<unk>", " ", text)


def score(ref: str, hyp: str) -> dict:
    r, h = norm(clean_ref(ref)), norm(hyp)
    w = jiwer.process_words(r, h)
    c = jiwer.process_characters(r, h)
    return {
        "ref_words": len(r.split()), "hyp_words": len(h.split()),
        "wer": w.wer, "sub": w.substitutions, "del": w.deletions, "ins": w.insertions,
        "hits": w.hits, "cer": c.cer,
    }


def main() -> None:
    manifest = {row["talk_id"]: row for row in csv.DictReader(open(harness.EVAL / "data" / "manifest.csv"))}
    refs = harness.EVAL / "data" / "references"
    rows = []
    sources = [(p, "app e2e") for p in glob.glob(str(harness.RESULTS / "raw" / "*__e2e__*.json"))]
    sources += [(p, "stt-only") for p in glob.glob(str(harness.RESULTS / "stt" / "*.json"))]
    for path, kind in sorted(sources):
        run = json.load(open(path, encoding="utf-8"))
        # Jobs that failed after transcription (e.g. in analysis) still have a valid transcript.
        if run.get("error") or not ((run.get("transcript") or {}).get("full_text") or "").strip():
            print(f"skip (no transcript, reported separately): {path}")
            continue
        talk = run["talk_id"]
        hyp = (run.get("transcript") or {}).get("full_text") or ""
        stt_calls = [c for c in run["calls"] if c["stage"] == "stt" and c["kind"] in ("llm", "stt")]
        stt_stage = [s["t1"] - s["t0"] for s in run["stages"] if s["stage"] == "stt"]
        dur = float(manifest[talk]["duration_sec"])
        model = run.get("stt_model") or (stt_calls[0]["model"] if stt_calls else None)
        rows.append({
            "talk_id": talk, "source": kind, "stt_model": model,
            "chunk_seconds": run.get("chunk_seconds") or (run.get("config") or {}).get("stt_chunk_seconds"),
            "error": run.get("error"),
            "provider": (run.get("transcript") or {}).get("provider"),
            "duration_sec": dur, "chunks": len(stt_calls),
            "stt_sec": round(sum(stt_stage), 2) if stt_stage else None,
            "rtf": round(sum(stt_stage) / dur, 4) if stt_stage else None,
            "audio_tokens": sum(c.get("prompt_tokens") or 0 for c in stt_calls),
            "output_tokens": sum(c.get("output_tokens") or 0 for c in stt_calls),
            **score((refs / f"{talk}.txt").read_text(encoding="utf-8"), hyp),
        })

    out = harness.RESULTS / "asr_scores.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by.setdefault((r["source"], r["stt_model"], r["chunk_seconds"]), []).append(r)
    for key, rs in by.items():
        S = sum(r["sub"] for r in rs); D = sum(r["del"] for r in rs); I = sum(r["ins"] for r in rs)
        N = sum(r["ref_words"] for r in rs)
        print(f"{key}: talks={len(rs)} corpus WER={(S + D + I) / N:.4f} (S={S} D={D} I={I} N={N}) "
              f"mean RTF={sum(r['rtf'] or 0 for r in rs) / len(rs):.4f}")


if __name__ == "__main__":
    main()
