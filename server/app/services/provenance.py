"""Claim-level provenance: link every sentence of a draft to the transcript passage
(and recording time) it most likely came from.

Deterministic and offline (BM25 over overlapping word windows, no LLM or embedding
call), so it runs on every request, stays correct after a human edits the draft and
can be recomputed for old jobs and saved evaluation runs.

Times are estimates: STT segments can be long (one per transcription chunk), so a
word's time is interpolated inside its segment, over speech time when the segment
carries speech spans (pauses get no words), otherwise linearly.
"""

from __future__ import annotations

import math
import re
from collections import Counter

WINDOW_WORDS = 40
WINDOW_STRIDE = 20
# IDF-weighted share of the claim's content words found around the best passage.
# Calibrated on the 108 end-to-end drafts of the evaluation: from 0.3 the passage is
# almost always where the point was made; 0.2-0.3 is often right but paraphrased.
# Lexical matching cannot prove a claim false, so below 0.2 is "untraced", not "wrong".
TRACED = 0.3
PARTIAL = 0.2
MIN_CLAIM_WORDS = 4  # shorter lines (CTAs, sign-offs, hashtag rows) are not claims
TIMELINE_BINS = 4

STOPWORDS = frozenset(
    """a about above after again against all also am an and any are as at be because been
    before being below between both but by can could did do does doing down during each few
    for from further had has have having he her here hers herself him himself his how i if
    in into is it its itself just let me more most my myself no nor not now of off on once
    only or other our ours ourselves out over own same she should so some such than that
    the their theirs them themselves then there these they this those through to too under
    until up very was we were what when where which while who whom why will with would you
    your yours yourself yourselves us one ones get got make made really thing things way
    well even every like much many may might must shall still yet ever never across within
    without upon""".split()
)


def _stem(token: str) -> str:
    for suffix in ("ing", "edly", "ed", "ies", "es", "s", "ly"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return token


def content_tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))
    return [
        _stem(w.strip("'")) for w in words if (len(w) > 2 or w.isdigit()) and w not in STOPWORDS
    ]


def _plain(markdown: str) -> str:
    """Markdown body -> plain text lines (headings, bullets, links, emphasis, tables removed)."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", markdown)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or set(line) <= set("|-: "):
            continue
        line = re.sub(r"^(#{1,6}|>|[-*+]|\d+[.)])\s+", "", line)
        line = line.replace("|", " ").replace("**", "").replace("__", "").replace("`", "")
        line = re.sub(r"(?<!\w)[*_](\S.*?\S|\S)[*_](?!\w)", r"\1", line)
        lines.append(line)
    return "\n".join(lines)


def split_claims(body: str) -> list[str]:
    """Sentences of the draft that state something about the talk."""
    claims = []
    for line in _plain(body).splitlines():
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            sentence = sentence.strip()
            without_tags = re.sub(r"(?<!\w)#\w+", "", sentence)
            if len(content_tokens(without_tags)) >= MIN_CLAIM_WORDS:
                claims.append(sentence)
    return claims


def _segment_offsets(words: list[str], segments: list[dict]) -> list[int] | None:
    """Word index in the full transcript where each segment starts.

    Segment text may be a shortened preview (Vertex STT keeps 500 characters), so each
    segment is located by its first words, searching forward from the previous one."""
    norm = [re.sub(r"\W", "", w.lower()) for w in words]
    offsets, cursor = [], 0
    for seg in segments:
        head = [re.sub(r"\W", "", w.lower()) for w in str(seg.get("text") or "").split()[:6]]
        head = [h for h in head if h]
        if not head:
            return None
        found = next(
            (i for i in range(cursor, len(norm) - len(head) + 1) if norm[i : i + len(head)] == head),
            None,
        )
        if found is None:
            return None
        offsets.append(found)
        cursor = found + 1
    return offsets


def _speech_in(seg: dict, start: float, end: float) -> list[tuple[float, float]]:
    """The segment's speech spans clipped to [start, end]; empty when it has none."""
    spans = []
    for span in seg.get("speech") or []:
        try:
            a, b = max(float(span[0]), start), min(float(span[1]), end)
        except (TypeError, ValueError, IndexError):
            return []
        if b > a:
            spans.append((a, b))
    return spans


def _time_at(fraction: float, start: float, end: float, spans: list[tuple[float, float]]) -> float:
    """Time at `fraction` of a segment's words: on speech time when the segment has
    speech spans (pauses take no words), otherwise spread evenly from start to end."""
    if not spans:
        return start + (end - start) * fraction
    target = fraction * sum(b - a for a, b in spans)
    for a, b in spans:
        if target <= b - a:
            return a + target
        target -= b - a
    return spans[-1][1]


def timed_words(full_text: str, segments: list[dict] | None) -> list[tuple[str, float | None]]:
    """Every transcript word with its estimated start time (None for text uploads)."""
    words = full_text.split()
    timed_segs = [s for s in segments or [] if s.get("start") is not None and s.get("end") is not None]
    if not words or not timed_segs:
        return [(w, None) for w in words]
    offsets = _segment_offsets(words, timed_segs)
    if offsets is None:  # cannot align: spread the words over the whole recording
        offsets = [0]
        timed_segs = [
            {
                "start": timed_segs[0]["start"],
                "end": timed_segs[-1]["end"],
                "speech": [span for s in timed_segs for span in (s.get("speech") or [])],
            }
        ]
    bounds = [*offsets[1:], len(words)]
    times: list[float | None] = [None] * len(words)
    for seg, first, last in zip(timed_segs, offsets, bounds, strict=True):
        start, end = float(seg["start"]), float(seg["end"])
        spans = _speech_in(seg, start, end)
        count = max(last - first, 1)
        for i in range(first, last):
            times[i] = round(_time_at((i - first) / count, start, end, spans), 2)
    first_start = float(timed_segs[0]["start"])
    return [(w, t if t is not None else first_start) for w, t in zip(words, times, strict=True)]


def build_windows(full_text: str, segments: list[dict] | None) -> list[dict]:
    timed = timed_words(full_text, segments)
    total = len(timed)
    windows = []
    for start in range(0, max(total, 1), WINDOW_STRIDE):
        part = timed[start : start + WINDOW_WORDS]
        if not part:
            break
        times = [t for _, t in part if t is not None]
        text = " ".join(w for w, _ in part)
        windows.append(
            {
                "text": text,
                "tokens": content_tokens(text),
                "position": round(start / total, 4) if total else 0.0,
                "start": times[0] if times else None,
                "end": times[-1] if times else None,
            }
        )
        if start + WINDOW_WORDS >= total:
            break
    return windows


class _BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.2, b: float = 0.75) -> None:
        self.docs = [Counter(d) for d in docs]
        self.lengths = [len(d) for d in docs]
        self.avg = (sum(self.lengths) / len(docs)) if docs else 0.0
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for doc, length in zip(self.docs, self.lengths, strict=True):
            norm = self.k1 * (1 - self.b + self.b * length / (self.avg or 1))
            out.append(
                sum(
                    self.idf.get(t, 0.0) * doc[t] * (self.k1 + 1) / (doc[t] + norm)
                    for t in set(query)
                    if t in doc
                )
            )
        return out


def _support(claim_tokens: list[str], window_tokens: list[str], idf: dict[str, float]) -> float:
    """IDF-weighted share of the claim's words found in the evidence: rare, specific
    words (names, numbers, terms) count more than common ones."""
    claim = set(claim_tokens)
    total = sum(idf.get(t, max(idf.values(), default=1.0)) for t in claim)
    found = sum(idf.get(t, 0.0) for t in claim & set(window_tokens))
    return found / total if total else 0.0


def temporal_spread(positions: list[float], bins: int = TIMELINE_BINS) -> dict:
    """Which parts of the talk the draft draws on: counts per equal-length bin and the
    share of bins with at least one traced claim (1.0 = beginning to end)."""
    counts = [0] * bins
    for p in positions:
        counts[min(int(p * bins), bins - 1)] += 1
    return {"bins": counts, "spread": round(sum(1 for c in counts if c) / bins, 3)}


def trace_claims(body: str, full_text: str, segments: list[dict] | None = None) -> dict:
    """Provenance for one draft body against its transcript."""
    windows = build_windows(full_text, segments)
    claims = split_claims(body)
    if not windows or not claims:
        return {
            "method": "bm25-window",
            "claims": [],
            "summary": {"claims": len(claims), "traced": 0, "partial": 0, "coverage": None,
                        **temporal_spread([])},
        }
    bm25 = _BM25([w["tokens"] for w in windows])
    traced = []
    for sentence in claims:
        tokens = content_tokens(sentence)
        scores = bm25.scores(tokens)
        best = max(range(len(windows)), key=scores.__getitem__)
        # A point is often made over several sentences: count the neighbouring windows too.
        neighbourhood = [t for w in windows[max(best - 1, 0) : best + 2] for t in w["tokens"]]
        support = round(_support(tokens, neighbourhood, bm25.idf), 3)
        status = "traced" if support >= TRACED else "partial" if support >= PARTIAL else "untraced"
        window = windows[best] if status != "untraced" else {}
        traced.append(
            {
                "sentence": sentence,
                "status": status,
                "support": support,
                "position": window.get("position"),
                "start": window.get("start"),
                "end": window.get("end"),
                "evidence": window.get("text"),
            }
        )
    found = [c for c in traced if c["status"] == "traced"]
    return {
        "method": "bm25-window",
        "claims": traced,
        "summary": {
            "claims": len(traced),
            "traced": len(found),
            "partial": sum(1 for c in traced if c["status"] == "partial"),
            "coverage": round(len(found) / len(traced), 3),
            **temporal_spread([c["position"] for c in found]),
        },
    }
