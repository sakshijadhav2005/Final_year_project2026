from __future__ import annotations

import hashlib
import math
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import Embedding

VOCAB = 256


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


def chunk_text(text: str, size: int = 400) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]


async def index_transcript_chunks(db: AsyncSession, *, user_id: UUID, job_id: str, text: str) -> None:
    for chunk in chunk_text(text):
        db.add(
            Embedding(
                user_id=user_id,
                source_type="transcript_chunk",
                source_id=job_id,
                chunk_text=chunk,
                embedding=bag_vector(chunk),
            )
        )
    await db.flush()


async def retrieve_chunks(
    db: AsyncSession,
    *,
    user_id: UUID,
    query: str,
    use_org_memory: bool,
    limit: int = 4,
) -> list[dict]:
    qvec = bag_vector(query)
    stmt = select(Embedding).where(Embedding.user_id == user_id)
    if not use_org_memory:
        stmt = stmt.order_by(Embedding.created_at.desc()).limit(12)
    rows = list((await db.execute(stmt)).scalars().all())
    scored = sorted(rows, key=lambda row: cosine(qvec, list(row.embedding or [])), reverse=True)
    out: list[dict] = []
    for row in scored[:limit]:
        out.append({"text": row.chunk_text, "source": row.source_type, "source_id": row.source_id})
    if not out:
        head = " ".join(query.split()[:400])
        if head:
            out.append({"text": head, "source": "transcript_head"})
    return out
