"""Calibrate the automatic judge against human raters.

1. export  - pick drafts of the live end-to-end runs (same number per format), write
             results/human/items.json (item id -> run and format, the unblinding key) and
             a self-contained rating form, results/human/rating_form.html. Raters open it
             in a browser, score each draft 1-5 on the judge's rubric against the talk's
             reference transcript, and download their ratings as CSV. Items are shown in
             a different order per rater; the condition and the judge's scores are hidden.
2. analyze - read results/human/ratings/*.csv and report, per rubric dimension:
             agreement between raters (Krippendorff's alpha, ordinal) and between the
             human consensus (median) and the primary judge (QWK, Spearman, exact/±1,
             mean difference). Writes results/human/summary.json for analyze.py.

    python evaluation/scripts/human_eval.py export --per-format 6
    python evaluation/scripts/human_eval.py analyze

The form embeds reference transcripts and drafts (CC BY-NC-ND derived), so it is not
published (see evaluation/.gitignore); share it with raters directly. Ratings CSVs hold
only scores and are tracked.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import random
import statistics as st
from collections import defaultdict

import harness
from judge_quality import DIMENSIONS, FORMAT_SPECS, RUBRIC

HUMAN = harness.RESULTS / "human"
TYPES = ["summary", "blog", "linkedin", "newsletter", "instagram", "flyer"]


def export(per_format: int, seed: int) -> None:
    rng = random.Random(seed)
    runs = {}
    for p in sorted(glob.glob(str(harness.RESULTS / "raw" / "*__e2e__*.json"))):
        r = json.load(open(p, encoding="utf-8"))
        if r["job"]["status"] != "failed" and (harness.RESULTS / "judge" / "runs" / f"{r['run_id']}.json").exists():
            runs[r["run_id"]] = r
    items, talks_used = [], set()
    for t in TYPES:
        candidates = [(rid, p) for rid, r in runs.items() for p in r["content"] or []
                      if p["type"] == t and p.get("language") == "en"]
        rng.shuffle(candidates)
        # Prefer talks not used yet, so the sample spreads over as many talks as possible.
        candidates.sort(key=lambda c: runs[c[0]]["talk_id"] in talks_used)
        for rid, piece in candidates[:per_format]:
            talks_used.add(runs[rid]["talk_id"])
            items.append({"run_id": rid, "talk_id": runs[rid]["talk_id"], "type": t,
                          "title": piece.get("title") or "", "body": piece.get("body") or ""})
    rng.shuffle(items)
    for i, it in enumerate(items, 1):
        it["item_id"] = f"H{i:02d}"
    refs = {}
    for talk in sorted({it["talk_id"] for it in items}):
        text = (harness.EVAL / "data" / "references" / f"{talk}.txt").read_text(encoding="utf-8")
        refs[talk] = " ".join(text.replace("<unk>", " ").split())

    harness.save_json(HUMAN / "items.json", [{k: it[k] for k in ("item_id", "run_id", "talk_id", "type")}
                                             for it in items])
    form_items = [{"id": it["item_id"], "talk": it["talk_id"], "type": it["type"],
                   "spec": FORMAT_SPECS[it["type"]], "title": it["title"], "body": it["body"]} for it in items]
    data = json.dumps({"items": form_items, "refs": refs, "dims": DIMENSIONS, "rubric": RUBRIC},
                      ensure_ascii=False).replace("</", "<\\/")
    (HUMAN / "ratings").mkdir(parents=True, exist_ok=True)
    (HUMAN / "rating_form.html").write_text(FORM.replace("__DATA__", data), encoding="utf-8")
    print(f"{len(items)} items from {len(refs)} talks -> {HUMAN / 'rating_form.html'}")


# --------------------------------------------------------------------------- agreement
def krippendorff_ordinal(units: list[list[int]], lo: int = 1, hi: int = 5) -> float | None:
    """Krippendorff's alpha, ordinal metric; units = the ratings each item received."""
    values = range(lo, hi + 1)
    o = defaultdict(float)
    for ratings in units:
        m = len(ratings)
        if m < 2:
            continue
        for i, a in enumerate(ratings):
            for j, b in enumerate(ratings):
                if i != j:
                    o[(a, b)] += 1 / (m - 1)
    n_c = {c: sum(o[(c, k)] for k in values) for c in values}
    n = sum(n_c.values())
    if n <= 1:
        return None

    def delta(c: int, k: int) -> float:
        a, b = min(c, k), max(c, k)
        return (sum(n_c[g] for g in range(a, b + 1)) - (n_c[a] + n_c[b]) / 2) ** 2

    observed = sum(o[(c, k)] * delta(c, k) for c in values for k in values)
    expected = sum(n_c[c] * n_c[k] * delta(c, k) for c in values for k in values) / (n - 1)
    return 1 - observed / expected if expected else None


def analyze() -> None:
    import numpy as np
    from scipy import stats

    from analyze import qwk

    key = {it["item_id"]: it for it in json.load(open(HUMAN / "items.json", encoding="utf-8"))}
    ratings = defaultdict(dict)  # item -> rater -> {dim: score}
    for path in sorted(glob.glob(str(HUMAN / "ratings" / "*.csv"))):
        for row in csv.DictReader(open(path, encoding="utf-8")):
            if row["item_id"] in key and all(row.get(d) for d in DIMENSIONS):
                ratings[row["item_id"]][row["rater"]] = {d: int(row[d]) for d in DIMENSIONS}
    raters = sorted({r for by in ratings.values() for r in by})
    if not ratings:
        raise SystemExit(f"No ratings in {HUMAN / 'ratings'}")
    judge = {}
    for item_id, it in key.items():
        verdict = json.load(open(harness.RESULTS / "judge" / "runs" / f"{it['run_id']}.json",
                                 encoding="utf-8"))["verdicts"].get(it["type"], {})
        judge[item_id] = verdict

    rows = []
    for d in DIMENSIONS:
        units = [[r[d] for r in by.values()] for by in ratings.values()]
        human, machine = [], []
        for item_id, by in ratings.items():
            try:
                j = int(judge[item_id][d])
            except (KeyError, TypeError, ValueError):
                continue
            human.append(st.median_low([r[d] for r in by.values()]))
            machine.append(j)
        h, m = np.array(human), np.array(machine)
        rho = stats.spearmanr(h, m).statistic if len(set(human)) > 1 and len(set(machine)) > 1 else None
        rows.append({"dimension": d, "items": len(human), "raters": len(raters),
                     "alpha_raters": round(a, 3) if (a := krippendorff_ordinal(units)) is not None else None,
                     "qwk_human_judge": round(float(qwk(h, m)), 3), "spearman": round(float(rho), 3) if rho is not None else None,
                     "exact": round(float((h == m).mean()), 3), "within_1": round(float((abs(h - m) <= 1).mean()), 3),
                     "mean_human": round(float(h.mean()), 2), "mean_judge": round(float(m.mean()), 2)})
    summary = {"raters": raters, "items_rated": len(ratings), "dimensions": rows}
    harness.save_json(HUMAN / "summary.json", summary)
    print(json.dumps(summary, indent=1))


FORM = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Draft Rating Form</title>
<style>
:root{--bg:#fafaf7;--fg:#1d1d1b;--dim:#6b6b66;--line:#d9d8d2;--card:#fff;--accent:#1f4e79}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--dim:#a19f97;--line:#3a3935;--card:#1f1f1d;--accent:#8fb8e0}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:22px;margin:0 0 4px}.dim{color:var(--dim)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}
pre{white-space:pre-wrap;word-wrap:break-word;font:14px/1.5 ui-monospace,monospace;background:var(--bg);padding:12px;border-radius:8px;max-height:420px;overflow:auto}
details pre{max-height:320px}
table{border-collapse:collapse;width:100%;margin-top:8px}td{padding:6px 4px;border-top:1px solid var(--line)}
label{display:inline-flex;align-items:center;gap:3px;margin-right:10px;cursor:pointer}
button{font:inherit;padding:8px 16px;border-radius:999px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}
button.ghost{background:transparent;color:var(--accent)}input[type=text]{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.done{color:#3a8a3a}
</style></head><body><main>
<h1>Draft rating form</h1>
<p class="dim">Score each AI-written draft against the talk's transcript. Your progress is saved in this browser. When you finish, download your ratings and send the CSV file back.</p>
<div class="card"><label>Your name or initials <input type="text" id="rater" placeholder="e.g. R1"></label>
<p class="dim" id="progress"></p>
<details><summary>Rubric</summary><pre id="rubric"></pre></details></div>
<div id="item"></div>
<nav><button class="ghost" id="prev">Previous</button><button id="next">Next</button><span style="flex:1"></span><button id="dl">Download ratings (CSV)</button></nav>
</main>
<script>
const D = __DATA__;
const store = {get(k){try{return JSON.parse(localStorage.getItem(k))}catch(e){return null}}, set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
let ratings = store.get("ratings") || {}; let idx = 0; let order = D.items.map((_, i) => i);
const raterEl = document.getElementById("rater"); raterEl.value = store.get("rater") || "";
document.getElementById("rubric").textContent = D.rubric.split("Also list")[0];
function shuffle(){ // a fixed order per rater name, so item order effects average out across raters
  let h = 0; for (const ch of raterEl.value) h = (Math.imul(h, 31) + ch.charCodeAt(0)) >>> 0;
  order = D.items.map((_, i) => i);
  for (let i = order.length - 1; i > 0; i--) { h = (Math.imul(h, 1103515245) + 12345) >>> 0; const j = h % (i + 1); [order[i], order[j]] = [order[j], order[i]]; }
}
function esc(s){return String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
function render(){
  const it = D.items[order[idx]]; const r = ratings[it.id] || {};
  const rows = D.dims.map(d => `<tr><td>${d.replace(/_/g," ")}</td><td>${[1,2,3,4,5].map(v =>
    `<label><input type="radio" name="${d}" value="${v}" ${r[d]==v?"checked":""}>${v}</label>`).join("")}</td></tr>`).join("");
  document.getElementById("item").innerHTML = `<div class="card"><p class="dim">Item ${idx+1} of ${D.items.length} · ${it.id} · format: <b>${it.type}</b></p>
    <p><b>Format requirements:</b> ${esc(it.spec)}</p>
    <details><summary>Talk transcript (reference)</summary><pre>${esc(D.refs[it.talk])}</pre></details>
    <h3>${esc(it.title)}</h3><pre>${esc(it.body)}</pre><table>${rows}</table></div>`;
  document.querySelectorAll("#item input[type=radio]").forEach(el => el.addEventListener("change", e => {
    ratings[it.id] = {...(ratings[it.id] || {}), [e.target.name]: Number(e.target.value)}; store.set("ratings", ratings); progress(); }));
  progress();
}
function progress(){
  const done = D.items.filter(it => D.dims.every(d => (ratings[it.id] || {})[d])).length;
  document.getElementById("progress").innerHTML = `${done} of ${D.items.length} drafts fully rated` + (done === D.items.length ? ' <span class="done">✓ complete</span>' : "");
}
raterEl.addEventListener("change", () => { store.set("rater", raterEl.value); shuffle(); idx = 0; render(); });
document.getElementById("prev").onclick = () => { if (idx > 0) { idx--; render(); scrollTo(0, 0); } };
document.getElementById("next").onclick = () => { if (idx < D.items.length - 1) { idx++; render(); scrollTo(0, 0); } };
document.getElementById("dl").onclick = () => {
  const rater = raterEl.value.trim(); if (!rater) { alert("Enter your name or initials first."); return; }
  const lines = [["item_id", "rater", ...D.dims].join(",")];
  for (const it of D.items) { const r = ratings[it.id] || {}; lines.push([it.id, JSON.stringify(rater), ...D.dims.map(d => r[d] || "")].join(",")); }
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], {type: "text/csv"}));
  a.download = `ratings_${rater.replace(/\W+/g, "_")}.csv`; a.click();
};
shuffle(); render();
</script></body></html>
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--per-format", type=int, default=6)
    ex.add_argument("--seed", type=int, default=7)
    sub.add_parser("analyze")
    args = ap.parse_args()
    if args.cmd == "export":
        export(args.per_format, args.seed)
    else:
        analyze()
