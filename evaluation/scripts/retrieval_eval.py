"""Retrieval quality of the selective-RAG retriever (dataset-based, labelled by construction).

Corpus: TED-LIUM 3 human reference transcripts of the long talks (> 2,000 words),
chunked exactly as the app does (app.services.rag.chunk_text, 250 words, 50 overlap).

Queries: for each talk the judge model writes factual questions, each with a verbatim
supporting quote copied from the reference. A question is kept only if its quote occurs
verbatim (after whitespace/case normalisation) in the reference; the relevant chunks
are the chunks that contain the quote. Relevance is therefore decided mechanically,
not by a model.

Retrievers: gemini-embedding-001 (the app, 768-d), the app's previous hashed
bag-of-words vectors (256-d), and BM25 (Okapi, rank_bm25) as a standard lexical baseline.
Settings: within-talk pool (the app's default) and a cross-talk pool of all talks'
chunks (org-memory setting, with distractors).

    python evaluation/scripts/retrieval_eval.py
"""

from __future__ import annotations

import asyncio
import csv
import json
import math
import re

import harness

JUDGE = "gemini-3.7-flash"
KS = (1, 3, 6)
N_QUESTIONS = 10


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9' ]", " ", text.lower()).split())


async def make_queries(client, talk: str, ref: str) -> list[dict]:
    from google.genai import types

    cache = harness.RESULTS / "retrieval" / "queries" / f"{talk}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    prompt = (
        f"Below is the transcript of a talk. Write {N_QUESTIONS} factual questions that a reader "
        "could ask about specific points made in the talk, spread across the WHOLE talk "
        "(beginning, middle and end). Paraphrase: do not copy long phrases from the transcript "
        "into the question. For each question give `quote`: an exact, contiguous, verbatim "
        "copy of 8-25 words from the transcript that answers it. Reply as JSON: "
        '{"items": [{"question": "...", "quote": "..."}]}\n\n<TRANSCRIPT>\n' + ref + "\n</TRANSCRIPT>"
    )
    resp = await client.aio.models.generate_content(
        model=JUDGE, contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json"),
    )
    items = json.loads(resp.text).get("items", [])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    return items


def metrics(ranked: list[int], relevant: set[int]) -> dict:
    out = {}
    for k in KS:
        out[f"recall@{k}"] = float(any(i in relevant for i in ranked[:k]))
    rr = next((1 / (pos + 1) for pos, i in enumerate(ranked) if i in relevant), 0.0)
    out["mrr"] = rr
    k = max(KS)
    dcg = sum(1 / math.log2(pos + 2) for pos, i in enumerate(ranked[:k]) if i in relevant)
    idcg = sum(1 / math.log2(pos + 2) for pos in range(min(len(relevant), k)))
    out[f"ndcg@{k}"] = dcg / idcg if idcg else 0.0
    return out


async def main() -> None:
    from rank_bm25 import BM25Okapi

    from app.providers.vertex_llm import _client
    from app.services.rag import bag_vector, chunk_text, cosine, embed_texts

    manifest = list(csv.DictReader(open(harness.EVAL / "data" / "manifest.csv")))
    talks = [r["talk_id"] for r in manifest if int(r["ref_words"]) > 2000]
    refs = {t: " ".join((harness.EVAL / "data" / "references" / f"{t}.txt").read_text(encoding="utf-8").replace("<unk>", " ").split()) for t in talks}
    client = _client()

    chunks: list[dict] = []
    queries: list[dict] = []
    for talk in talks:
        talk_chunks = chunk_text(refs[talk])
        base = len(chunks)
        chunks += [{"talk": talk, "text": c, "norm": norm(c)} for c in talk_chunks]
        items = await make_queries(client, talk, refs[talk])
        kept = 0
        for it in items:
            q, quote = it.get("question", ""), norm(it.get("quote", ""))
            rel = {base + i for i, c in enumerate(talk_chunks) if quote and quote in norm(c)}
            if len(quote.split()) >= 6 and rel and quote in norm(refs[talk]):
                queries.append({"talk": talk, "question": q, "quote": it["quote"], "relevant": sorted(rel)})
                kept += 1
        print(f"{talk}: {len(talk_chunks)} chunks, {kept}/{len(items)} questions kept", flush=True)

    model, doc_vecs = await embed_texts([c["text"] for c in chunks], task_type="RETRIEVAL_DOCUMENT")
    assert model != "bag-256", "Vertex embeddings unavailable"
    _, q_vecs = await embed_texts([q["question"] for q in queries], task_type="RETRIEVAL_QUERY")
    bag_docs = [bag_vector(c["text"]) for c in chunks]

    rows = []
    for setting in ("within-talk", "cross-talk"):
        for qi, q in enumerate(queries):
            pool = [i for i, c in enumerate(chunks) if setting == "cross-talk" or c["talk"] == q["talk"]]
            bm25 = BM25Okapi([chunks[i]["norm"].split() for i in pool])
            scores = {
                "gemini-embedding-001": [cosine(q_vecs[qi], doc_vecs[i]) for i in pool],
                "hashed bag-of-words (previous)": [cosine(bag_vector(q["question"]), bag_docs[i]) for i in pool],
                "BM25": list(bm25.get_scores(norm(q["question"]).split())),
            }
            for method, s in scores.items():
                ranked = [pool[j] for j in sorted(range(len(pool)), key=lambda j: s[j], reverse=True)]
                rows.append({"setting": setting, "method": method, "talk": q["talk"], "query": qi,
                             "pool_size": len(pool), **metrics(ranked, set(q["relevant"]))})

    out = harness.RESULTS / "retrieval"
    with (out / "per_query.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    harness.save_json(out / "queries.json", queries)
    summary = []
    for setting in ("within-talk", "cross-talk"):
        for method in dict.fromkeys(r["method"] for r in rows):
            rs = [r for r in rows if r["setting"] == setting and r["method"] == method]
            keys = [k for k in rs[0] if k.startswith(("recall", "mrr", "ndcg"))]
            summary.append({"setting": setting, "method": method, "queries": len(rs),
                            "mean_pool": sum(r["pool_size"] for r in rs) / len(rs),
                            **{k: sum(r[k] for r in rs) / len(rs) for k in keys}})
    harness.save_json(out / "summary.json", {"talks": talks, "chunks": len(chunks),
                                              "queries": len(queries), "query_model": JUDGE,
                                              "summary": summary})
    for s in summary:
        print(json.dumps(s))


if __name__ == "__main__":
    harness.configure_env("retrieval")
    harness.install()
    asyncio.run(main())
