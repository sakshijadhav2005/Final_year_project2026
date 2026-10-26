"""Build every table (CSV + LaTeX) and figure (PDF + PNG) from the saved raw results.

Inputs : results/raw/*.json, results/asr_scores.csv, results/judge*/runs/*.json,
         results/judge/key_points/*.json, results/retrieval/*, results/fault_injection/*,
         results/coverage.json, results/pytest_junit.xml
Outputs: results/tables/*.csv|tex, figures/*.pdf|png, results/summary.json

    python evaluation/scripts/analyze.py
"""

from __future__ import annotations

import csv
import glob
import json
import re
import statistics as st
import xml.etree.ElementTree as ET
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

import harness  # noqa: E402

R = harness.RESULTS
FIG = harness.EVAL / "figures"
TAB = R / "tables"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)
AGENT_CHARS = 12000
INCIDENT_CALL_SEC = 600  # a single call this long = machine sleep / network outage
TYPES = ["summary", "blog", "linkedin", "newsletter", "instagram", "flyer"]
DIMS = ["factual_consistency", "relevance", "completeness", "readability", "instruction_adherence"]
DIM_LABEL = {"factual_consistency": "Factual cons.", "relevance": "Relevance", "completeness": "Completeness",
             "readability": "Readability", "instruction_adherence": "Instr. adherence"}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 8,
    "axes.titlesize": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "figure.dpi": 300, "savefig.bbox": "tight", "axes.spines.top": False,
    "axes.spines.right": False, "pdf.fonttype": 42,
})
C1, C2, C3, C4 = "#1f4e79", "#c55a11", "#548235", "#7f6000"
SUMMARY: dict = {}


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=300)
    plt.close(fig)


def write_table(name, rows, header=None):
    if not rows:
        return
    header = header or list(rows[0])
    with (TAB / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def tex_table(name, caption, label, colspec, header, rows, wide=False, note=None, colsep="3.5pt"):
    """Write a booktabs LaTeX table generated from data (results/tables/<name>.tex)."""
    env = "table*" if wide else "table"
    lines = [f"\\begin{{{env}}}[t]", "\\centering", f"\\caption{{{caption}}}", f"\\label{{{label}}}",
             "\\footnotesize", f"\\setlength{{\\tabcolsep}}{{{colsep}}}", f"\\begin{{tabular}}{{{colspec}}}", "\\toprule",
             " & ".join(header) + " \\\\", "\\midrule"]
    for r in rows:
        lines.append("\\midrule" if r == "MID" else " & ".join(str(c) for c in r) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    if note:
        lines.append(f"\\\\[2pt]\\parbox{{\\linewidth}}{{\\scriptsize {note}}}")
    lines.append(f"\\end{{{env}}}")
    (TAB / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def f2(x, d=2):
    return "--" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def talk_label(talk_id: str) -> str:
    """'BillGates' -> 'Bill Gates', 'EricMead_2009P_EricMead' -> 'Eric Mead'."""
    base = talk_id.split("_2009P")[0].replace("_", " ")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base)


def q(xs, p):
    return float(np.percentile(xs, p)) if xs else float("nan")


def load_runs():
    runs = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(str(R / "raw" / "*.json")))]
    for r in runs:
        r["incident"] = any(c["sec"] > INCIDENT_CALL_SEC for c in r["calls"])
    return runs


def stage_times(run) -> dict:
    by = defaultdict(list)
    for s in run["stages"]:
        by[s["stage"]].append(s)
    span = lambda ss: max(s["t1"] for s in ss) - min(s["t0"] for s in ss)  # noqa: E731
    out = {}
    for name in ("media_check", "stt", "rag_index", "analysis", "rag_retrieve", "translation"):
        if by.get(name):
            out[name] = sum(s["t1"] - s["t0"] for s in by[name])
    out["rag_retrieve"] = out.get("rag_retrieve", 0) + sum(s["t1"] - s["t0"] for s in by.get("rag_pool", []))
    if by.get("generator"):
        out["generation"] = span(by["generator"])
    out["guardrail"] = sum(s["t1"] - s["t0"] for s in by.get("guardrail", []))
    if by.get("generator_retry"):
        out["guardrail"] += span(by["generator_retry"])
    return out


STAGE_LABEL = {"media_check": "Media check", "stt": "Speech-to-text", "rag_index": "RAG indexing",
               "analysis": "Analysis", "rag_retrieve": "RAG retrieval", "generation": "Generation (6 agents)",
               "guardrail": "Guardrail (+retry)", "translation": "Translation (hi)"}


# --------------------------------------------------------------------------- dataset
def dataset():
    rows = [r for r in csv.DictReader(open(harness.EVAL / "data" / "manifest.csv"))]
    used = [r for r in rows if float(r["duration_sec"]) >= 60]
    d = [float(r["duration_sec"]) / 60 for r in used]
    w = [int(r["ref_words"]) for r in used]
    SUMMARY["dataset"] = {"talks_total": len(rows), "talks_used": len(used),
                          "excluded": [r["talk_id"] for r in rows if float(r["duration_sec"]) < 60],
                          "hours": round(sum(d) / 60, 2), "min_minutes": round(min(d), 1),
                          "max_minutes": round(max(d), 1), "median_minutes": round(st.median(d), 1),
                          "ref_words_total": sum(w), "long_talks_gt2000": sum(x > 2000 for x in w)}
    write_table("dataset", used)
    ds = SUMMARY["dataset"]
    (TAB / "macros.tex").write_text(
        "% generated by analyze.py\n"
        f"\\newcommand{{\\DatasetTalks}}{{{ds['talks_used']}}}\n"
        f"\\newcommand{{\\DatasetHours}}{{{ds['hours']:.1f}}}\n"
        f"\\newcommand{{\\DatasetMinMin}}{{{ds['min_minutes']}}}\n"
        f"\\newcommand{{\\DatasetMaxMin}}{{{ds['max_minutes']}}}\n"
        f"\\newcommand{{\\DatasetMedMin}}{{{ds['median_minutes']}}}\n"
        f"\\newcommand{{\\DatasetLong}}{{{ds['long_talks_gt2000']}}}\n",
        encoding="utf-8")


# --------------------------------------------------------------------------- ASR
def asr():
    rows = list(csv.DictReader(open(R / "asr_scores.csv")))
    for r in rows:
        for k in ("wer", "cer", "rtf", "duration_sec", "stt_sec"):
            r[k] = float(r[k]) if r[k] not in ("", "None") else None
        for k in ("sub", "del", "ins", "ref_words", "audio_tokens", "output_tokens"):
            r[k] = int(float(r[k]))
    groups = defaultdict(list)
    for r in rows:
        if r["source"] == "app e2e" and r["talk_id"] in INCIDENT_TALKS_STT:
            continue
        groups[(r["source"], r["stt_model"], int(float(r["chunk_seconds"] or 300)))].append(r)
    table = []
    for (src, model, chunk), rs in sorted(groups.items()):
        N = sum(r["ref_words"] for r in rs)
        S, D, I = (sum(r[k] for r in rs) for k in ("sub", "del", "ins"))
        rtf = [r["rtf"] for r in rs if r["rtf"] is not None]
        table.append({"source": src, "model": model, "chunk_s": chunk, "talks": len(rs),
                      "corpus_wer": round((S + D + I) / N * 100, 2),
                      "mean_wer": round(st.mean(r["wer"] for r in rs) * 100, 2),
                      "median_wer": round(st.median(r["wer"] for r in rs) * 100, 2),
                      "max_wer": round(max(r["wer"] for r in rs) * 100, 2),
                      "mean_cer": round(st.mean(r["cer"] for r in rs) * 100, 2),
                      "sub": S, "del": D, "ins": I, "ref_words": N,
                      "median_rtf": round(st.median(rtf), 4) if rtf else None,
                      "median_stt_sec": round(st.median(r["stt_sec"] for r in rs if r["stt_sec"]), 1),
                      "audio_tokens_per_min": round(sum(r["audio_tokens"] for r in rs) / sum(r["duration_sec"] for r in rs) * 60, 1)})
    write_table("asr_summary", table)
    SUMMARY["asr"] = table

    # Figure: per-talk WER of the production configuration, plus model comparison.
    prod = sorted([r for r in rows if r["source"] == "app e2e"], key=lambda r: r["wer"])
    fig, ax = plt.subplots(figsize=(3.5, 2.3))
    names = [talk_label(r["talk_id"]) for r in prod]
    ax.barh(range(len(prod)), [r["wer"] * 100 for r in prod], color=C1, height=0.7)
    corpus = next(t["corpus_wer"] for t in table if t["source"] == "app e2e")
    ax.axvline(corpus, color=C2, ls="--", lw=1, label=f"Corpus WER {corpus:.2f}%")
    ax.set_yticks(range(len(prod)), names)
    ax.set_xlabel("Word error rate (%)")
    ax.legend(frameon=False, loc="lower right")
    save(fig, "fig_wer_per_talk")

    comp = [t for t in table if t["source"] == "stt-only" or t["source"] == "app e2e"]
    if len(comp) > 1:
        fig, ax = plt.subplots(figsize=(3.5, 2.0))
        labels = [f"{t['model'].replace('gemini-', '')}\n{t['chunk_s']} s" + ("*" if t["source"] == "app e2e" else "")
                  + f"\nn={t['talks']}" for t in comp]
        x = np.arange(len(comp))
        ax.bar(x - 0.2, [t["corpus_wer"] for t in comp], 0.4, color=C1, label="Corpus WER (%)")
        ax2 = ax.twinx()
        ax2.bar(x + 0.2, [t["median_rtf"] * 100 for t in comp], 0.4, color=C3, label="Median RTF (×100)")
        ax.set_xticks(x, labels, fontsize=6)
        ax.set_ylabel("Corpus WER (%)")
        ax2.set_ylabel("Median RTF ×100")
        ax2.spines["right"].set_visible(True)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=6, ncol=2, loc="lower center",
                  bbox_to_anchor=(0.5, 1.0))
        save(fig, "fig_asr_models")


# --------------------------------------------------------------------------- latency / tokens
def latency_tokens(runs):
    # Completed jobs only: a job that failed mid-pipeline has partial timings.
    e2e = [r for r in runs if r["mode"] == "e2e" and not r["incident"] and r["job"]["status"] != "failed"]
    stage_rows, per_run = [], []
    for r in e2e:
        stt = stage_times(r)
        dur = float(MANIFEST[r["talk_id"]]["duration_sec"])
        llm = [c for c in r["calls"] if c["kind"] == "llm"]
        per_run.append({"talk_id": r["talk_id"], "audio_min": round(dur / 60, 2),
                        "transcript_words": len((r["transcript"] or {}).get("full_text", "").split()),
                        "total_sec": round(r["wall_sec"], 1), "rtf_total": round(r["wall_sec"] / dur, 3),
                        "llm_calls": len(llm), "prompt_tokens": sum(c.get("prompt_tokens") or 0 for c in llm),
                        "output_tokens": sum(c.get("output_tokens") or 0 for c in llm),
                        "status": r["job"]["status"], **{k: round(v, 2) for k, v in stt.items()}})
        for k, v in stt.items():
            stage_rows.append((k, v))
    write_table("latency_per_run", per_run)
    table = []
    for k in STAGE_LABEL:
        xs = [v for s, v in stage_rows if s == k]
        if xs:
            table.append({"stage": STAGE_LABEL[k], "n": len(xs), "median_s": round(st.median(xs), 2),
                          "p25_s": round(q(xs, 25), 2), "p75_s": round(q(xs, 75), 2),
                          "min_s": round(min(xs), 2), "max_s": round(max(xs), 2)})
    tot = [p["total_sec"] for p in per_run]
    table.append({"stage": "Total (upload to drafts)", "n": len(tot), "median_s": round(st.median(tot), 1),
                  "p25_s": round(q(tot, 25), 1), "p75_s": round(q(tot, 75), 1),
                  "min_s": round(min(tot), 1), "max_s": round(max(tot), 1)})
    write_table("latency_stages", table)
    SUMMARY["latency"] = {"stages": table, "e2e_runs": len(e2e),
                          "excluded_incident_runs": [r["run_id"] for r in runs if r["incident"]],
                          "median_total_rtf": round(st.median(p["rtf_total"] for p in per_run), 3)}

    # Figure: stage latency box plot.
    keys = [k for k in STAGE_LABEL if any(s == k for s, _ in stage_rows)]
    fig, ax = plt.subplots(figsize=(3.5, 2.3))
    ax.boxplot([[v for s, v in stage_rows if s == k] for k in keys], vert=False, widths=0.6,
               medianprops={"color": C2}, flierprops={"markersize": 2})
    ax.set_yticks(range(1, len(keys) + 1), [STAGE_LABEL[k] for k in keys])
    ax.set_xlabel(f"Stage latency (s), n = {len(e2e)} end-to-end runs")
    save(fig, "fig_latency_stages")

    # Figure: audio length vs total latency and STT time.
    x = [p["audio_min"] for p in per_run]
    fig, ax = plt.subplots(figsize=(3.5, 2.1))
    ax.scatter(x, tot, s=10, color=C1, label="Total pipeline")
    ax.scatter(x, [p.get("stt", 0) for p in per_run], s=10, color=C3, marker="^", label="Speech-to-text")
    rho, pval = stats.spearmanr(x, tot)
    ax.set_xlabel("Talk duration (min)")
    ax.set_ylabel("Latency (s)")
    ax.legend(frameon=False, title=f"Spearman ρ (total) = {rho:.2f}, p = {pval:.3g}", title_fontsize=6)
    save(fig, "fig_latency_vs_duration")
    SUMMARY["latency"]["spearman_duration_total"] = {"rho": rho, "p": pval, "n": len(x)}

    # Tokens per stage (all e2e runs, mean per job).
    tok = defaultdict(lambda: [0, 0])
    for r in e2e:
        for c in r["calls"]:
            if c["kind"] == "llm":
                tok[c["stage"]][0] += c.get("prompt_tokens") or 0
                tok[c["stage"]][1] += c.get("output_tokens") or 0
    n = len(e2e)
    trows = [{"stage": s, "mean_prompt_tokens": round(a / n), "mean_output_tokens": round(b / n)}
             for s, (a, b) in sorted(tok.items(), key=lambda kv: -kv[1][0])]
    write_table("tokens_per_stage", trows)
    emb = [c for r in e2e for c in r["calls"] if c["kind"] == "embed"]
    SUMMARY["tokens"] = {"per_stage_mean_per_job": trows,
                         "mean_llm_calls_per_job": round(st.mean(p["llm_calls"] for p in per_run), 2),
                         "mean_prompt_tokens_per_job": round(st.mean(p["prompt_tokens"] for p in per_run)),
                         "mean_output_tokens_per_job": round(st.mean(p["output_tokens"] for p in per_run)),
                         "embedding_calls_total": len(emb)}
    fig, ax = plt.subplots(figsize=(3.5, 1.9))
    labels = [t["stage"] for t in trows]
    ax.barh(labels, [t["mean_prompt_tokens"] for t in trows], color=C1, label="Input")
    ax.barh(labels, [t["mean_output_tokens"] for t in trows], left=[t["mean_prompt_tokens"] for t in trows],
            color=C2, label="Output")
    ax.set_xlabel(f"Mean tokens per job (n = {n})")
    ax.invert_yaxis()
    ax.legend(frameon=False)
    save(fig, "fig_tokens_stage")
    return per_run


# --------------------------------------------------------------------------- reliability (live)
def live_reliability(runs):
    calls = [c for r in runs for c in r["calls"] if c["kind"] in ("llm", "embed")]
    err = [c for c in calls if c.get("error")]
    kinds = defaultdict(int)
    for c in err:
        e = c["error"]
        k = ("429 rate limit" if "429" in e else "timeout/cancelled" if "Cancelled" in e or "Timeout" in e
             else "network (DNS/SSL/connection/auth refresh)"
             if any(s in e for s in ("Transport", "oauth", "SSL", "Connection", "ServerNotFound")) else "other")
        kinds[k] += 1
    empty = sum(1 for c in calls if c.get("empty_text"))
    fallback_runs = 0
    for r in runs:
        models = {c["model"] for c in r["calls"] if c["kind"] == "llm" and c["stage"] != "stt"}
        fallback_runs += any(m != r["config"]["gemini_model_generate"] for m in models)
    status = defaultdict(int)
    for r in runs:
        status[r["job"]["status"]] += 1
    failures = [{"run": r["run_id"], "error": (r["job"].get("error_message") or "")[:120]}
                for r in runs if r["job"]["status"] == "failed"]
    shape = sum("has no attribute 'get'" in f["error"] for f in failures)
    with (TAB / "macros.tex").open("a", encoding="utf-8") as fh:
        fh.write(f"\\newcommand{{\\LiveAnalysisShapeFailures}}{{{shape}}}\n")
    # Guardrail outcomes.
    retry_runs = sum(any(s["stage"] == "generator_retry" for s in r["stages"]) for r in runs)
    issues = defaultdict(int)
    flagged_pieces = total_pieces = 0
    for r in runs:
        for p in r.get("content") or []:
            if p.get("language") != "en":
                continue
            total_pieces += 1
            g = p.get("grounding") or {}
            if g and not g.get("pass", True):
                flagged_pieces += 1
                issues[p["type"]] += 1
    SUMMARY["live_reliability"] = {
        "runs": len(runs), "api_calls": len(calls), "failed_calls": len(err), "error_kinds": dict(kinds),
        "empty_responses": empty, "runs_with_model_fallback": fallback_runs, "job_status": dict(status),
        "failed_jobs": failures, "runs_with_guardrail_retry": retry_runs,
        "final_pieces_flagged": flagged_pieces, "final_pieces_total": total_pieces,
        "flagged_by_type": dict(issues),
    }


# --------------------------------------------------------------------------- quality (judge)
def load_judge(folder):
    out = {}
    for p in glob.glob(str(R / folder / "runs" / "*.json")):
        j = json.load(open(p, encoding="utf-8"))
        out[j["run_id"]] = j
    return out


def score(v, d):
    try:
        return float(v.get(d))
    except (TypeError, ValueError):
        return None


def quality(runs):
    judge = load_judge("judge")
    if not judge:
        return
    by_run = {r["run_id"]: r for r in runs}
    # Rubric for the production e2e runs (one per talk).
    rubric = defaultdict(list)
    unsupported = defaultdict(list)
    for rid, j in judge.items():
        if j["mode"] != "e2e":
            continue
        for t, v in j["verdicts"].items():
            for d in DIMS:
                s = score(v, d)
                if s is not None:
                    rubric[(t, d)].append(s)
            unsupported[t].append(len(v.get("unsupported_claims") or []))
    table = []
    for t in TYPES:
        row = {"format": t, "n": len(rubric[(t, DIMS[0])])}
        for d in DIMS:
            row[d] = round(st.mean(rubric[(t, d)]), 2) if rubric[(t, d)] else None
        row["mean_unsupported_claims"] = round(st.mean(unsupported[t]), 2) if unsupported[t] else None
        table.append(row)
    write_table("quality_rubric", table)
    SUMMARY["quality_rubric"] = table
    overall = {d: round(st.mean(x for t in TYPES for x in rubric[(t, d)]), 2) for d in DIMS}
    SUMMARY["quality_overall"] = overall

    fig, ax = plt.subplots(figsize=(3.5, 2.1))
    M = np.array([[row[d] for d in DIMS] for row in table], dtype=float)
    im = ax.imshow(M, cmap="Blues", vmin=3, vmax=5, aspect="auto")  # scores lie in 3.7-5
    ax.set_xticks(range(len(DIMS)), [DIM_LABEL[d] for d in DIMS], rotation=25, ha="right")
    ax.set_yticks(range(len(TYPES)), [t.capitalize() for t in TYPES])
    for i in range(M.shape[0]):
        for k in range(M.shape[1]):
            ax.text(k, i, f"{M[i, k]:.2f}", ha="center", va="center", fontsize=6,
                    color="white" if M[i, k] > 4.4 else "black")
    fig.colorbar(im, ax=ax, fraction=0.04, label="Mean score (scale 1-5; colour 3-5)")
    save(fig, "fig_quality_heatmap")

    # Objective format checks (no LLM).
    banned = ["i am thrilled", "in today's fast-paced", "delve", "tapestry", "beacon", "game-changer",
              "revolutionize", "pivotal"]
    checks = defaultdict(list)
    for r in runs:
        if r["mode"] != "e2e":
            continue
        for p in r.get("content") or []:
            if p.get("language") != "en":
                continue
            body = p.get("body") or ""
            tags = len(re.findall(r"(?<!\w)#\w+", body))
            words = len(body.split())
            if p["type"] == "summary":
                checks["summary <= 400 words"].append(words <= 400)
            if p["type"] == "linkedin":
                checks["linkedin 3-5 hashtags"].append(3 <= tags <= 5)
                checks["linkedin no banned phrases"].append(not any(b in body.lower() for b in banned))
            if p["type"] == "instagram":
                checks["instagram 10-15 hashtags"].append(10 <= tags <= 15)
            if p["type"] == "flyer":
                checks["flyer no invented date (TBA or none)"].append(
                    not re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}", body))
    SUMMARY["format_checks"] = {k: {"pass": sum(v), "n": len(v)} for k, v in checks.items()}
    write_table("format_checks", [{"check": k, "pass": sum(v), "n": len(v),
                                    "rate": round(sum(v) / len(v), 3)} for k, v in checks.items()])

    # RAG ablation: key-point coverage, early vs late, paired by talk.
    rows = []
    for rid, j in judge.items():
        if j["mode"] != "regen":
            continue
        run = by_run.get(rid)
        if not run or run["incident_quality_invalid"]:
            continue
        pts = json.load(open(R / "judge" / "key_points" / f"{j['talk_id']}.json", encoding="utf-8"))
        asr_len = len((run["transcript"] or {}).get("full_text") or "")
        visible = min(1.0, AGENT_CHARS / asr_len) if asr_len else 1.0
        late = {p["id"] for p in pts if p["position"] > visible}
        early = {p["id"] for p in pts if p["position"] <= visible}
        for t, v in j["verdicts"].items():
            cov = set()
            for x in v.get("covered_key_points") or []:
                try:
                    cov.add(int(x))
                except (TypeError, ValueError):
                    pass
            rows.append({"talk": j["talk_id"], "condition": j["condition"], "repeat": j["repeat"], "type": t,
                         "late_cov": len(cov & late) / len(late) if late else None,
                         "early_cov": len(cov & early) / len(early) if early else None,
                         "all_cov": len(cov & (early | late)) / len(early | late) if (early | late) else None,
                         "n_late": len(late), "n_early": len(early),
                         **{d: score(v, d) for d in DIMS},
                         "unsupported": len(v.get("unsupported_claims") or [])})
    write_table("rag_ablation_per_draft", rows)
    talks = sorted({r["talk"] for r in rows})

    def per_talk(metric, cond, types=None):
        out = []
        for t in talks:
            xs = [r[metric] for r in rows if r["talk"] == t and r["condition"] == cond
                  and r[metric] is not None and (types is None or r["type"] in types)]
            out.append(st.mean(xs) if xs else None)
        return out

    abl = []
    for metric, types, label in (
        ("late_cov", None, "Late coverage, all formats"),
        ("early_cov", None, "Early coverage, all formats"),
        ("late_cov", ["blog", "newsletter", "summary"], "Late coverage, long formats"),
        ("all_cov", None, "All key points, all formats"),
        *[(d, None, DIM_LABEL[d]) for d in DIMS],
        ("unsupported", None, "Unsupported claims per draft"),
    ):
        on, off = per_talk(metric, "rag_on", types), per_talk(metric, "rag_off", types)
        pairs = [(a, b) for a, b in zip(on, off) if a is not None and b is not None]
        a = np.array([p[0] for p in pairs]); b = np.array([p[1] for p in pairs])
        diff = a - b
        try:
            w = stats.wilcoxon(a, b, zero_method="wilcox") if np.any(diff != 0) else None
        except ValueError:
            w = None
        abl.append({"metric": label, "talks": len(pairs), "rag_on_mean": round(a.mean(), 3),
                    "rag_off_mean": round(b.mean(), 3), "mean_diff": round(diff.mean(), 3),
                    "talks_improved": int((diff > 0).sum()), "talks_worse": int((diff < 0).sum()),
                    "wilcoxon_p": round(w.pvalue, 4) if w else None})
    write_table("rag_ablation", abl)
    SUMMARY["rag_ablation"] = abl

    on, off = per_talk("late_cov", "rag_on"), per_talk("late_cov", "rag_off")
    eon, eoff = per_talk("early_cov", "rag_on"), per_talk("early_cov", "rag_off")
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.9), sharey=True)
    for ax, (x_on, x_off, title) in zip(axes, ((eon, eoff, "Early points (seen directly)"),
                                               (on, off, "Late points (beyond 12k chars)"))):
        pairs = [(a, b) for a, b in zip(x_off, x_on) if a is not None and b is not None]
        for a, b in pairs:
            ax.plot([0, 1], [a * 100, b * 100], color="0.7", lw=0.7)
        ax.scatter([0] * len(pairs), [a * 100 for a, _ in pairs], s=8, color=C2, zorder=3)
        ax.scatter([1] * len(pairs), [b * 100 for _, b in pairs], s=8, color=C1, zorder=3)
        ax.plot([0, 1], [np.mean([a for a, _ in pairs]) * 100, np.mean([b for _, b in pairs]) * 100],
                color="k", lw=1.6, marker="D", ms=3, zorder=4)
        ax.set_xticks([0, 1], ["RAG off", "RAG on"])
        ax.set_title(title)
        ax.set_xlim(-0.4, 1.4)
    axes[0].set_ylabel("Key points covered (%)")
    save(fig, "fig_rag_ablation")

    # Second-judge agreement.
    j2 = load_judge("judge2")
    pairs = defaultdict(list)
    for rid, b in j2.items():
        a = judge.get(rid)
        if not a:
            continue
        for t, vb in b["verdicts"].items():
            va = a["verdicts"].get(t)
            if not va:
                continue
            for d in DIMS:
                x, y = score(va, d), score(vb, d)
                if x is not None and y is not None:
                    pairs[d].append((x, y))
    agree = []
    for d in DIMS:
        ps = pairs[d]
        if not ps:
            continue
        x = np.array([p[0] for p in ps]); y = np.array([p[1] for p in ps])
        agree.append({"dimension": DIM_LABEL[d], "n": len(ps), "exact": round(float((x == y).mean()), 3),
                      "within_1": round(float((abs(x - y) <= 1).mean()), 3),
                      "qwk": round(qwk(x, y), 3), "mean_j1": round(x.mean(), 2), "mean_j2": round(y.mean(), 2)})
    write_table("judge_agreement", agree)
    SUMMARY["judge_agreement"] = agree


def qwk(a, b, lo=1, hi=5):
    a = np.rint(a).astype(int); b = np.rint(b).astype(int)
    n = hi - lo + 1
    O = np.zeros((n, n))
    for x, y in zip(a, b):
        O[x - lo, y - lo] += 1
    W = np.array([[(i - j) ** 2 / (n - 1) ** 2 for j in range(n)] for i in range(n)])
    E = np.outer(O.sum(1), O.sum(0)) / O.sum()
    return 1 - (W * O).sum() / (W * E).sum() if (W * E).sum() else float("nan")


# --------------------------------------------------------------------------- retrieval
def retrieval():
    path = R / "retrieval" / "summary.json"
    if not path.exists():
        return
    s = json.load(open(path, encoding="utf-8"))
    rows = [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in s["summary"]]
    write_table("retrieval", rows)
    SUMMARY["retrieval"] = {k: v for k, v in s.items() if k != "summary"} | {"rows": rows}
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.9), sharey=True)
    colors = {"gemini-embedding-001": C1, "BM25": C3, "hashed bag-of-words (previous)": C2}
    for ax, setting in zip(axes, ("within-talk", "cross-talk")):
        for r in rows:
            if r["setting"] != setting:
                continue
            ax.plot([1, 3, 6], [r["recall@1"], r["recall@3"], r["recall@6"]], marker="o", ms=3,
                    color=colors.get(r["method"], "k"), label=r["method"].replace(" (previous)", "\n(previous)"))
        ax.set_title(f"{setting} (pool ≈ {int(next(r['mean_pool'] for r in rows if r['setting'] == setting))})")
        ax.set_xticks([1, 3, 6])
        ax.set_xlabel("k")
        ax.set_ylim(0, 1.02)
    axes[0].set_ylabel("Recall@k")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, [x.replace("\n", " ") for x in lab], frameon=False, fontsize=6, ncol=3,
               loc="lower center", bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(bottom=0.36)
    save(fig, "fig_retrieval")


# --------------------------------------------------------------------------- fault injection / tests
def faults():
    path = R / "fault_injection" / "summary.json"
    if not path.exists():
        return
    s = json.load(open(path, encoding="utf-8"))
    SUMMARY["fault_injection"] = s
    rows = [{"scenario": x["scenario"], "trials": x["trials"],
             "outcome": "; ".join(f"{k} {v}" for k, v in x["outcomes"].items()),
             "usable_rate": x["usable_output_rate"], "mean_attempts": x["mean_attempts"],
             "median_latency_s": x["latency_median_sec"], "next_call_model": x["second_call_model"]}
            for x in s["scenarios"]]
    write_table("fault_injection", rows)
    fig, ax = plt.subplots(figsize=(3.5, 2.0))
    cats = ["primary model", "fallback model", "unparsed (raw text)", "offline template"]
    cols = [C1, C3, C4, C2]
    left = np.zeros(len(rows))
    for cat, col in zip(cats, cols):
        vals = np.array([x["outcomes"].get(cat, 0) / x["trials"] * 100 for x in s["scenarios"]])
        ax.barh(range(len(rows)), vals, left=left, color=col, label=cat, height=0.7)
        left += vals
    ax.set_yticks(range(len(rows)), [x["scenario"] for x in s["scenarios"]], fontsize=6)
    ax.invert_yaxis()
    ax.set_xlabel("Outcome share of trials (%)")
    ax.legend(frameon=False, fontsize=5.5, ncol=2, loc="upper center", bbox_to_anchor=(0.4, -0.25))
    save(fig, "fig_fault_injection")


def tests():
    root = ET.parse(R / "pytest_junit.xml").getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    cov = json.load(open(R / "coverage.json"))
    files = cov["files"]
    groups = defaultdict(lambda: [0, 0])
    for f, d in files.items():
        g = f.replace("\\", "/").split("app/")[-1].split("/")[0]
        groups[g][0] += d["summary"]["covered_lines"]
        groups[g][1] += d["summary"]["num_statements"]
    files_tests = defaultdict(int)
    for tc in suite.iter("testcase"):
        files_tests[tc.get("classname", "").split(".")[-1]] += 1
    SUMMARY["tests"] = {"tests": int(suite.get("tests")), "failures": int(suite.get("failures")),
                        "errors": int(suite.get("errors")), "skipped": int(suite.get("skipped", 0)),
                        "time_s": float(suite.get("time")), "line_coverage": round(cov["totals"]["percent_covered"], 1),
                        "statements": cov["totals"]["num_statements"],
                        "by_package": {g: round(a / b * 100, 1) for g, (a, b) in groups.items() if b},
                        "tests_by_file": dict(files_tests)}


def correlation(per_run):
    asr_rows = {r["talk_id"]: r for r in csv.DictReader(open(R / "asr_scores.csv")) if r["source"] == "app e2e"}
    judge = load_judge("judge")
    qual = {}
    for j in judge.values():
        if j["mode"] == "e2e":
            xs = [score(v, d) for v in j["verdicts"].values() for d in DIMS]
            xs = [x for x in xs if x is not None]
            qual[j["talk_id"]] = st.mean(xs) if xs else None
    names = ["Duration", "Transcript words", "WER", "Total latency", "Input tokens", "Mean rubric"]
    data = []
    for p in per_run:
        t = p["talk_id"]
        if t not in asr_rows or qual.get(t) is None:
            continue
        data.append([p["audio_min"], p["transcript_words"], float(asr_rows[t]["wer"]), p["total_sec"],
                     p["prompt_tokens"], qual[t]])
    if len(data) < 8:
        return
    A = np.array(data)
    rho, pv = stats.spearmanr(A)
    SUMMARY["correlation"] = {"n": len(data), "variables": names, "rho": np.round(rho, 3).tolist(),
                              "p": np.round(pv, 4).tolist()}
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    im = ax.imshow(rho, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(names)), names, rotation=35, ha="right")
    ax.set_yticks(range(len(names)), names)
    for i in range(len(names)):
        for k in range(len(names)):
            ax.text(k, i, f"{rho[i, k]:.2f}" + ("*" if pv[i, k] < 0.05 and i != k else ""), ha="center",
                    va="center", fontsize=5.5, color="white" if abs(rho[i, k]) > 0.6 else "black")
    fig.colorbar(im, ax=ax, fraction=0.04, label=f"Spearman ρ (n = {len(data)})")
    save(fig, "fig_correlation")


def make_tex():
    S = SUMMARY
    # ASR
    rows = []
    for t in S["asr"]:
        name = t["model"].replace("gemini-", "") + (" (pipeline)" if t["source"] == "app e2e" else "")
        rows.append([name, t["chunk_s"], t["talks"], f2(t["corpus_wer"]), f2(t["median_wer"]), f2(t["max_wer"]),
                     f2(t["mean_cer"]), f"{t['sub']}/{t['del']}/{t['ins']}", f2(t["median_rtf"], 3),
                     f2(t["median_stt_sec"], 1)])
    tex_table("tab_asr", "Speech recognition on TED-LIUM~3 talks (WER/CER in \\%, Whisper normaliser). "
              "The first row is the production configuration inside the live pipeline; the others are "
              "cached-stage runs of the same \\texttt{transcribe\\_file} function, four configurations "
              "processed concurrently.", "tab:asr", "lrrrrrrrrr",
              ["Model", "Chunk (s)", "Talks", "Corpus WER", "Median", "Max", "CER", "S/D/I", "RTF", "STT (s)"],
              rows, wide=True)
    # latency
    rows = [[t["stage"], t["n"], f2(t["median_s"]), f"{f2(t['p25_s'])}--{f2(t['p75_s'])}",
             f"{f2(t['min_s'])}--{f2(t['max_s'])}"] for t in S["latency"]["stages"]]
    rows.insert(-1, "MID")
    tex_table("tab_latency", "Per-stage latency of the live end-to-end runs (seconds; completed jobs, "
              "upload to finished drafts incl.\\ Hindi translation).", "tab:latency", "lrrrr",
              ["Stage", "$n$", "Median", "IQR", "Range"], rows)
    # retrieval
    rows = []
    for r in S["retrieval"]["rows"]:
        rows.append([r["setting"], r["method"].replace(" (previous)", " (prev.)"), f2(r["recall@1"]), f2(r["recall@3"]),
                     f2(r["recall@6"]), f2(r["mrr"]), f2(r["ndcg@6"])])
    rows.insert(3, "MID")
    tex_table("tab_retrieval", f"Retrieval on {S['retrieval']['queries']} labelled questions over "
              f"{S['retrieval']['chunks']} chunks of {len(S['retrieval']['talks'])} long talks.", "tab:retrieval",
              "llrrrrr", ["Pool", "Retriever", "R@1", "R@3", "R@6", "MRR", "nDCG@6"], rows, wide=True)
    # RAG ablation
    rows = []
    for a in S["rag_ablation"]:
        pct = "coverage" in a["metric"].lower() or "key points" in a["metric"].lower()
        fmt = (lambda v: f2(v * 100, 1)) if pct else (lambda v: f2(v, 2))
        rows.append([a["metric"] + (" (\\%)" if pct else ""), fmt(a["rag_off_mean"]), fmt(a["rag_on_mean"]),
                     ("+" if a["mean_diff"] >= 0 else "") + fmt(a["mean_diff"]),
                     f"{a['talks_improved']}/{a['talks_worse']}", f2(a["wilcoxon_p"], 4) if a["wilcoxon_p"] is not None else "--"])
    rows.insert(4, "MID")
    tex_table("tab_rag", f"RAG ablation: same stored transcript, 3 runs per condition, averaged per talk "
              f"($n={S['rag_ablation'][0]['talks']}$ long talks); two-sided Wilcoxon signed-rank test. "
              "Coverage from the automatic judge.", "tab:rag", "lrrrrr",
              ["Metric", "RAG off", "RAG on", "$\\Delta$", "$+$/$-$", "$p$"], rows, colsep="2.2pt",
              note="$+$/$-$: talks whose per-talk mean rose/fell with RAG.")
    # quality
    rows = [[r["format"].capitalize(), r["n"], *[f2(r[d]) for d in DIMS], f2(r["mean_unsupported_claims"])]
            for r in S["quality_rubric"]]
    rows.append("MID")
    ov = S["quality_overall"]
    rows.append(["All", sum(r["n"] for r in S["quality_rubric"]), *[f2(ov[d]) for d in DIMS], "--"])
    tex_table("tab_quality", "Automatic-judge quality scores (1--5) of the English drafts of the live "
              "end-to-end runs, judged against the human reference transcript.", "tab:quality", "lrrrrrrr",
              ["Format", "$n$", "Fact.", "Rel.", "Compl.", "Read.", "Instr.", "Unsup."], rows, wide=True)
    rows = [[k, f"{v['pass']}/{v['n']}"] for k, v in S["format_checks"].items()]
    tex_table("tab_format", "Deterministic format checks on the end-to-end drafts.", "tab:format", "lr",
              ["Check", "Pass"], rows)
    rows = [[a["dimension"], a["n"], f2(a["exact"] * 100, 1), f2(a["within_1"] * 100, 1), f2(a["qwk"]),
             f2(a["mean_j1"]), f2(a["mean_j2"])] for a in S["judge_agreement"]]
    tex_table("tab_judge", "Agreement between the primary judge (J1, gemini-3.7-flash) and a second judge "
              "(J2, gemini-3.6-flash) on the same drafts.", "tab:judge", "lrrrrrr",
              ["Dimension", "$n$", "Exact \\%", "$\\pm$1 \\%", "QWK", "J1", "J2"], rows)
    # faults
    rows = []
    for x in S["fault_injection"]["scenarios"]:
        out = "; ".join(f"{k} {v}" for k, v in x["outcomes"].items())
        rows.append([x["scenario"], out, f2(x["mean_attempts"], 1), f2(x["latency_median_sec"]),
                     (x["second_call_model"] or "").replace("gemini-", ""), str(x.get("degraded_flagged", 0))])
    cb = S["fault_injection"]["circuit_breaker_probe"]
    sp = S["fault_injection"].get("sustained_429_probe")
    note = (f"Circuit-breaker probe: {cb['consecutive_failing_calls']} consecutive failing calls "
            f"(fail\\_max = {cb['fail_max']}) reached the upstream {cb['upstream_invocations']} times; "
            f"{cb['short_circuited']} were short-circuited.")
    if sp:
        note += (f" Sustained 429 on the primary over {sp['calls']} calls: the primary was tried by "
                 f"{sp['primary_attempts']} calls, then skipped by its model breaker (fail\\_max = "
                 f"{sp['fail_max']}, {sp['reset_seconds']:.0f}\\,s window).")
    tex_table("tab_faults", "Mock-based fault injection into the production Vertex provider (20 trials per "
              "scenario). ``Next call'' is the first model tried by the next call in the same process; "
              "``Flagged'' counts trials whose fallback output was marked as degraded.",
              "tab:faults", "llrrlr", ["Scenario", "Outcome (of 20)", "Calls", "Lat. (s)", "Next call", "Flagged"],
              rows, wide=True, note=note)
    t = S["tests"]
    tex_table("tab_tests", "Automated test suite (pytest, offline fake providers).", "tab:tests", "lr",
              ["Item", "Value"],
              [["Test cases (files)", f"{t['tests']} ({len(t['tests_by_file'])})"],
               ["Passed / failed / errors", f"{t['tests'] - t['failures'] - t['errors']} / {t['failures']} / {t['errors']}"],
               ["Line coverage (app)", f"{t['line_coverage']}\\% of {t['statements']} statements"],
               ["Coverage: core / graphs / services", f"{t['by_package'].get('core')} / {t['by_package'].get('graphs')} / {t['by_package'].get('services')}\\%"],
               ["Coverage: providers / api", f"{t['by_package'].get('providers')} / {t['by_package'].get('api')}\\%"],
               ["Wall time", f"{t['time_s']:.1f} s"]])


MANIFEST = {r["talk_id"]: r for r in csv.DictReader(open(harness.EVAL / "data" / "manifest.csv"))}
INCIDENT_TALKS_STT: set[str] = set()


def main():
    runs = load_runs()
    for r in runs:
        # An outage stalls a call but the pipeline still completes: outputs remain valid for
        # quality, only timing is excluded. Failed jobs have no outputs to judge.
        r["incident_quality_invalid"] = r["job"]["status"] == "failed"
    for r in runs:
        if r["mode"] == "e2e" and any(c["sec"] > INCIDENT_CALL_SEC and c["stage"] == "stt" for c in r["calls"]):
            INCIDENT_TALKS_STT.add(r["talk_id"])
    dataset()
    asr()
    per_run = latency_tokens(runs)
    # Runs replaced by a re-run after an outage still count as real reliability outcomes.
    incidents = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(str(R / "incidents" / "*.json")))]
    in_raw = {(r["run_id"], r["started_utc"]) for r in runs}
    live_reliability(runs + [r for r in incidents if (r["run_id"], r["started_utc"]) not in in_raw])
    SUMMARY["incidents"] = [{"run_id": r["run_id"], "status": r["job"]["status"],
                             "max_call_sec": round(max(c["sec"] for c in r["calls"]), 1),
                             "error": (r["job"].get("error_message") or "")[:160]} for r in incidents]
    quality(runs)
    retrieval()
    faults()
    tests()
    correlation(per_run)
    make_tex()
    harness.save_json(R / "summary.json", SUMMARY)
    print(json.dumps(SUMMARY, indent=1, default=str)[:20000])


if __name__ == "__main__":
    main()
