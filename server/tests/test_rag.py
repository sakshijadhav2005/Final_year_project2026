"""Selective RAG: chunking, ranking, the candidate pool and the writer prompt.

Runs offline: conftest clears GOOGLE_CLOUD_PROJECT, so embeddings use the hashed
bag-of-words fallback and no Vertex AI call is made.
"""

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.graphs.agents.base import BaseCreatorAgent, _retrieved_block
from app.graphs.nodes.rag import rag_retrieve
from app.main import app
from app.services.rag import AGENT_TRANSCRIPT_CHARS, BAG_MODEL, chunk_text, rank_chunks


def test_chunks_overlap_and_cover_every_word() -> None:
    words = [f"w{i}" for i in range(600)]
    chunks = chunk_text(" ".join(words), size=250, overlap=50)
    assert len(chunks) == 3
    assert chunks[0].split()[-50:] == chunks[1].split()[:50]
    assert chunks[-1].split()[-1] == "w599"
    assert chunk_text("") == []


def test_rank_chunks_puts_the_relevant_chunk_first() -> None:
    pool = [
        {"text": t, "source": "this_event", "source_id": "j", "model": BAG_MODEL, "vector": []}
        for t in (
            "lunch menu and parking information for attendees",
            "vector databases make retrieval augmented generation fast",
            "thank you all for coming see you next year",
        )
    ]
    for item in pool:
        from app.services.rag import bag_vector

        item["vector"] = bag_vector(item["text"])
    model, top = asyncio.run(rank_chunks(pool, "retrieval augmented generation with vector databases", 2))
    assert model == BAG_MODEL
    assert len(top) == 2
    assert top[0]["text"].startswith("vector databases")
    assert top[0]["score"] >= top[1]["score"]


def test_rag_node_is_a_noop_without_a_pool() -> None:
    assert asyncio.run(rag_retrieve({"brief": {"angle": "x"}})) == {"rag_chunks": []}


def test_rag_node_queries_with_the_brief() -> None:
    from app.services.rag import bag_vector

    texts = ["closing remarks and thanks", "kubernetes autoscaling lessons from production"]
    state = {
        "brief": {"angle": "Scaling lessons", "key_messages": ["kubernetes autoscaling in production"]},
        "rag_pool": [
            {"text": t, "source": "this_event", "source_id": "j", "model": BAG_MODEL, "vector": bag_vector(t)}
            for t in texts
        ],
    }
    out = asyncio.run(rag_retrieve(state))
    assert out["rag_chunks"][0]["text"] == texts[1]
    assert "kubernetes autoscaling" in out["rag_meta"]["query"]
    assert out["rag_meta"]["pool_size"] == 2


def test_writer_prompt_includes_retrieved_context(monkeypatch) -> None:
    seen: dict = {}

    class _LLM:
        async def generate_json(self, *, system, user, temperature=0.3, fast=False):
            seen["user"] = user
            return {"title": "t", "body": "b"}

    monkeypatch.setattr("app.graphs.agents.base.get_llm_provider", lambda: _LLM())
    chunks = [
        {"text": "late point about latency budgets", "source": "this_event"},
        {"text": "last year's keynote on caching", "source": "past_event"},
    ]
    asyncio.run(BaseCreatorAgent("blog", "blog_skill.md").generate("transcript", context_chunks=chunks))
    assert "<RETRIEVED_CONTEXT>" in seen["user"]
    assert "(this event, later in the recording) late point about latency budgets" in seen["user"]
    assert "(earlier event) last year's keynote on caching" in seen["user"]
    assert _retrieved_block([]) == ""


def test_pool_skips_what_writers_already_see_and_adds_org_memory() -> None:
    from app.db.session import SessionLocal
    from app.services.rag import index_transcript_chunks, load_rag_pool

    user_id = uuid.uuid4()
    # ~3,000 words: well past what the writers see.
    transcript = " ".join(f"word{i}" for i in range(3000))

    async def _run():
        async with SessionLocal() as db:
            await index_transcript_chunks(db, user_id=user_id, job_id="past", text="earlier event talk")
            current = await load_rag_pool(
                db, user_id=user_id, job_id="now", transcript=transcript, use_org_memory=False
            )
            with_memory = await load_rag_pool(
                db, user_id=user_id, job_id="now", transcript=transcript, use_org_memory=True
            )
            await db.rollback()
            return current, with_memory

    with TestClient(app):
        current, with_memory = asyncio.run(_run())

    seen = " ".join(transcript[:AGENT_TRANSCRIPT_CHARS].split())
    assert current, "chunks should be indexed on demand"
    assert all(c["source"] == "this_event" and c["text"] not in seen for c in current)
    assert any(c["text"].endswith("word2999") for c in current)
    assert [c["text"] for c in with_memory if c["source"] == "past_event"] == ["earlier event talk"]
