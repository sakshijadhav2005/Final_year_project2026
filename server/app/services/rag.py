from __future__ import annotations

import hashlib
import math
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.embedding import Embedding

logger = structlog.get_logger("rag")

VOCAB = 256
BAG_MODEL = "bag-256"  # offline fallback: hashed bag-of-words, no API needed
EMBED_BATCH = 16

# The writing agents read only the first part of the transcript (see
# app.graphs.agents.base.AGENT_TRANSCRIPT_CHARS); retrieval supplies the rest.
AGENT_TRANSCRIPT_CHARS = 12000


def bag_vector(text: str) -> list[float]:
    vec = [0.0] * VOCAB
    for token in text.lower().split():
        digest = hashlib.md5(token.encode("utf-8", errors="ignore")).hexdigest()
        vec[int(digest, 16) % VOCAB] += 1.0
    return vec


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def chunk_text(text: str, size: int = 250, overlap: int = 50) -> list[str]:
    """Split into word windows that overlap, so a point made across a boundary
    still lands whole in one chunk."""
    words = text.split()
    if not words:
        return []
    step = max(size - overlap, 1)
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
    return chunks


async def embed_texts(texts: list[str], *, task_type: str) -> tuple[str, list[list[float]]]:
    """Vertex AI embeddings when a Google Cloud project is configured, otherwise
    (or if the call fails) the hashed bag-of-words vectors. Returns (model, vectors)."""
    settings = get_settings()
    if texts and settings.google_cloud_project and settings.rag_embedding_model:
        try:
            from google.genai import types

            from app.providers.vertex_llm import _client

            client = _client(settings.rag_embedding_location)
            vectors: list[list[float]] = []
            for i in range(0, len(texts), EMBED_BATCH):
                response = await client.aio.models.embed_content(
                    model=settings.rag_embedding_model,
                    contents=texts[i : i + EMBED_BATCH],
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=settings.rag_embedding_dims,
                    ),
                )
                vectors.extend(list(e.values or []) for e in response.embeddings or [])
            if len(vectors) == len(texts):
                return settings.rag_embedding_model, vectors
        except Exception as exc:
            logger.warning("embedding_failed_using_bag_vectors", error=str(exc)[:300])
    return BAG_MODEL, [bag_vector(t) for t in texts]


async def index_transcript_chunks(
    db: AsyncSession, *, user_id: UUID, job_id: str, text: str
) -> None:
    chunks = chunk_text(text)
    model, vectors = await embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")
    for seq, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        db.add(
            Embedding(
                user_id=user_id,
                source_type="transcript_chunk",
                source_id=job_id,
                chunk_text=chunk,
                embedding=vector,
                extra={"model": model, "seq": seq},
            )
        )
    await db.flush()


async def load_rag_pool(
    db: AsyncSession,
    *,
    user_id: UUID,
    job_id: str,
    transcript: str,
    use_org_memory: bool,
    org_limit: int = 300,
) -> list[dict]:
    """Candidate chunks for the rag_retrieve graph node.

    This event: only the parts the writing agents cannot already see.
    Org memory: chunks from the user's earlier events.
    """
    own_stmt = select(Embedding).where(
        Embedding.user_id == user_id, Embedding.source_id == job_id
    )
    own = list((await db.execute(own_stmt)).scalars().all())
    if not own and transcript.strip():
        # Reused transcript from before indexing existed (or RAG was off): index now.
        await index_transcript_chunks(db, user_id=user_id, job_id=job_id, text=transcript)
        own = list((await db.execute(own_stmt)).scalars().all())

    seen = " ".join(transcript[:AGENT_TRANSCRIPT_CHARS].split())
    rows = [(row, "this_event") for row in own if row.chunk_text not in seen]
    if use_org_memory:
        others = (
            await db.execute(
                select(Embedding)
                .where(Embedding.user_id == user_id, Embedding.source_id != job_id)
                .order_by(Embedding.created_at.desc())
                .limit(org_limit)
            )
        ).scalars()
        rows.extend((row, "past_event") for row in others)

    return [
        {
            "text": row.chunk_text,
            "source": source,
            "source_id": row.source_id,
            "model": (row.extra or {}).get("model", BAG_MODEL),
            "vector": list(row.embedding or []),
        }
        for row, source in rows
    ]


async def rank_chunks(pool: list[dict], query: str, k: int) -> tuple[str, list[dict]]:
    """Top-k chunks by cosine similarity to the query. Chunks stored with a different
    embedding model than the query are compared on bag-of-words vectors instead."""
    if not pool or not query.strip():
        return BAG_MODEL, []
    model, (qvec,) = await embed_texts([query], task_type="RETRIEVAL_QUERY")
    qbag = qvec if model == BAG_MODEL else bag_vector(query)
    scored = []
    for item in pool:
        if item["model"] == model:
            score = cosine(qvec, item["vector"])
        else:
            score = cosine(qbag, bag_vector(item["text"]))
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return model, [
        {
            "text": item["text"],
            "source": item["source"],
            "source_id": item["source_id"],
            "score": round(score, 4),
        }
        for score, item in scored[:k]
    ]
