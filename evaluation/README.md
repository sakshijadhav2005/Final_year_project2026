# EventAI evaluation package

Everything behind the numbers, tables and figures in the paper. Every figure and table
is produced by a script from saved raw results; nothing is typed in by hand. The paper itself
(`paper/`) is kept locally and is not published in this repository.

## Result labels

| Label | Meaning |
|---|---|
| **live** | Real calls to Google Cloud Vertex AI through the unmodified EventAI backend |
| **cached-stage** | Live calls on a stored intermediate (e.g. regeneration from the stored transcript) |
| **mock** | Deterministic fault injection, no network (`fault_injection.py`) |
| **automatic judge** | LLM-as-judge scores (gemini-3.7-flash), not human ratings |
| **dataset** | Scored against TED-LIUM 3 human reference transcripts |

## Data

`data/` – TED-LIUM release 3 long-form talks (distil-whisper/tedlium-long-form, CC BY-NC-ND 3.0,
used for non-commercial academic evaluation; audio is not committed). 19 talks; one 5.5 s talk
(`DanBarber_2010_S103`) is excluded as too short, leaving 18 talks (~4 h).
`data/manifest.csv`, `data/PROVENANCE.json`, `data/references/*.txt` (human transcripts).

## How runs execute

`scripts/harness.py` imports the real backend and only *wraps* functions to record timings
(`time.perf_counter`) and the token usage returned by the Google SDKs. Each worker uses its own
SQLite database under `work/`, never the developer database. Before each run the Vertex
provider's in-process model memory is reset so every run starts on the configured model;
fallbacks within a run are visible in the call log.

## Reproduce

```powershell
# from the repository root, using the backend virtualenv
$py = "server\.venv\Scripts\python.exe"
& $py evaluation\scripts\prepare_dataset.py                       # extract WAV + references
& $py evaluation\scripts\run_pipeline.py --worker w1 --ablation 3 --talks <talks...>   # live e2e + RAG ablation
& $py evaluation\scripts\run_stt.py --models gemini-3.6-flash gemini-3.7-flash --chunks 300
& $py evaluation\scripts\run_stt.py --models gemini-3.1-flash-lite --chunks 120 600
& $py evaluation\scripts\score_asr.py                             # WER / CER
& $py evaluation\scripts\retrieval_eval.py                        # Recall@k / MRR / nDCG
& $py evaluation\scripts\judge_quality.py                         # rubric + key-point coverage
& $py evaluation\scripts\judge_quality.py --second-judge          # judge agreement subset
& $py evaluation\scripts\fault_injection.py --trials 20           # mock reliability
& $py -m pytest server\tests --cov=app ...                        # see results/coverage.json
& $py evaluation\scripts\diagrams.py                              # architecture + pipeline figures
& $py evaluation\scripts\analyze.py                               # all tables, figures, summary.json
& $py evaluation\scripts\screenshots.py --talk Brian_Cox          # UI screenshots (Playwright, Edge)
```

Live runs need `gcloud auth application-default login` and a project with the Vertex AI API
enabled (`GOOGLE_CLOUD_PROJECT`, `LLM_PROVIDER=vertex` in `.env`).

## Outputs

Per-run records (`results/raw/`, `results/stt/`, `results/pilot/`, the run files in
`results/incidents/`) contain full talk transcripts and generated drafts derived from
CC BY-NC-ND material, so they are not published in this repository; the scripts above
regenerate them. Everything derived from them (`summary.json`, tables, figures, judge
verdicts, retrieval results) is included.

- `results/raw/` – one JSON per pipeline run: config snapshot, stage timings, every API call
  (model, latency, tokens, finish reason, errors), transcript, drafts, agent outputs.
- `results/incidents/` – runs hit by machine sleep / network outages (kept, reported, excluded
  from latency statistics; re-run where noted in the paper). `*__prefix.json` are the seven
  Elizabeth Gilbert runs that failed before the response-shape fix (the runs in `raw/` were
  made after it); `fault_injection_prefix/` is the mock experiment before the resilience fixes.
- `results/pilot/` – pilot runs that exposed the guardrail and template-leakage issues.
- `results/stt/`, `results/asr_scores.csv` – transcription experiments.
- `results/retrieval/`, `results/judge*/`, `results/fault_injection/` – per-item results.
- `results/tables/*.csv`, `results/summary.json` – every number used in the paper.
- `figures/*.pdf|png`, `figures/screenshots/*.png`.
