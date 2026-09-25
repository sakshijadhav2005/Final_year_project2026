from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.graphs.pipeline import get_compiled_graph
from app.models.content import ContentPiece
from app.models.job import AgentOutput, Job, Transcript
from app.models.recording import Recording
from app.services.audit import write_audit
from app.services.av_scan import scan_file
from app.services.guardrails import should_use_rag
from app.services.quality import inspect_media
from app.services.rag import index_transcript_chunks, retrieve_chunks
from app.services.transcription import transcribe_file

import asyncio

AGENT_KEYS = [
    "quality_check",
    "topic_extraction",
    "highlight_detection",
    "speaker_analysis",
    "sentiment_analysis",
    "content_planner",
    "rag_retrieve",
    "generator",
    "guardrail",
    "translation",
]

TERMINAL = {
    "pending_review",
    "ready_to_publish",
    "needs_reupload",
    "needs_review",
    "failed",
    "cancelled",
}

ACTIVE_JOB_TASKS: dict[str, asyncio.Task] = {}
CANCELLED_JOB_IDS: set[str] = set()


def cancel_job_task(job_id: str) -> None:
    job_str = str(job_id)
    CANCELLED_JOB_IDS.add(job_str)
    task = ACTIVE_JOB_TASKS.get(job_str)
    if task and not task.done():
        task.cancel()


def _queued_progress() -> dict[str, str]:
    return {key: "queued" for key in AGENT_KEYS}


async def _save(db: AsyncSession, job: Job, **kwargs) -> None:
    for key, value in kwargs.items():
        setattr(job, key, value)
    db.add(job)
    await db.commit()
    try:
        await db.refresh(job)
    except Exception:
        pass


async def _cancelled(db: AsyncSession, job_id: UUID) -> bool:
    job_str = str(job_id)
    if job_str in CANCELLED_JOB_IDS:
        return True
    status = (await db.execute(select(Job.status).where(Job.id == job_id))).scalar_one_or_none()
    return status is None or status == "cancelled"


async def process_job(job_id: str, reuse_transcript: bool = False) -> None:
    job_str = str(job_id)
    current_task = asyncio.current_task()
    if current_task:
        ACTIVE_JOB_TASKS[job_str] = current_task

    try:
        settings = get_settings()
        async with SessionLocal() as db:
            job = (await db.execute(select(Job).where(Job.id == UUID(job_id)))).scalar_one_or_none()
            if job is None or job.status == "cancelled" or job_str in CANCELLED_JOB_IDS:
                return

            recording = (
                await db.execute(select(Recording).where(Recording.id == job.recording_id))
            ).scalar_one_or_none()
        if recording is None:
            await _save(
                db,
                job,
                status="failed",
                error_code="missing_recording",
                error_message="Recording missing",
            )
            return

        job.started_at = datetime.now(UTC)
        progress = _queued_progress()
        progress["quality_check"] = "running"
        await _save(
            db, job, status="validating", progress=progress, error_code=None, error_message=None
        )

        transcript_row = None
        if reuse_transcript:
            transcript_row = (
                await db.execute(select(Transcript).where(Transcript.job_id == job.id))
            ).scalar_one_or_none()

        if transcript_row is None:
            from app.services.storage import get_storage

            local_path = get_storage().get_local_path(recording.storage_uri)
            scan = scan_file(local_path)
            if not scan.clean:
                await _save(
                    db,
                    job,
                    status="failed",
                    error_code="malware",
                    error_message=scan.detail,
                    progress={key: "failed" for key in AGENT_KEYS},
                )
                return

            quality = inspect_media(local_path)
            if not quality.ok:
                await _save(
                    db,
                    job,
                    status="needs_reupload",
                    error_code="low_quality",
                    error_message=quality.reason,
                    progress={**_queued_progress(), "quality_check": "failed"},
                    finished_at=datetime.now(UTC),
                )
                return

            if await _cancelled(db, job.id):
                return

            progress["quality_check"] = "complete"
            await _save(db, job, status="transcribing", progress=progress)

            try:
                transcript = await transcribe_file(local_path)
            except Exception as exc:
                await _save(
                    db,
                    job,
                    status="failed",
                    error_code="transcription_failed",
                    error_message=str(exc),
                    finished_at=datetime.now(UTC),
                )
                return

            # --- VAD HALLUCINATION GUARDRAIL ---
            # Reject known Whisper hallucinations caused by background noise/coughing
            known_hallucinations = [
                "अमर रहे, अमर रहे, नेताजी सुभाष चंद्र बोस अमर रहे।",
                "अमर रहे, अमर रहे, नेताजी सुभाष चंद्र बोस अमर रहे",
                "अमर रहे, अमर रहे, नेताजी सुभाष चंद्र बोस",
            ]
            
            clean_text = transcript.text.strip()
            if any(hallucination in clean_text for hallucination in known_hallucinations):
                await _save(
                    db,
                    job,
                    status="needs_reupload",
                    error_code="vad_hallucination",
                    error_message="Audio was mostly silence or noise (detected hallucinated output). Please upload a clearer recording with actual speech.",
                    finished_at=datetime.now(UTC),
                    progress={key: "failed" for key in AGENT_KEYS},
                )
                return

            if transcript.vendor_id:
                recording.videodb_id = transcript.vendor_id
            recording.duration_sec = (
                int(quality.duration_sec) if quality.duration_sec else recording.duration_sec
            )

            if await _cancelled(db, job.id):
                return

            existing = (
                await db.execute(select(Transcript).where(Transcript.job_id == job.id))
            ).scalar_one_or_none()
            if existing:
                await db.delete(existing)
                await db.flush()

            transcript_row = Transcript(
                recording_id=recording.id,
                job_id=job.id,
                full_text=transcript.text,
                language=transcript.language,
                avg_confidence=transcript.avg_confidence,
                quality_json=quality.as_dict(),
                segments=[
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "end": seg.end,
                        "confidence": seg.confidence,
                        "speaker": seg.speaker,
                    }
                    for seg in transcript.segments
                ],
                denoise_attempted="+denoise" in (transcript.provider or ""),
                provider=transcript.provider,
            )
            db.add(transcript_row)
            await db.flush()
            if settings.rag_enabled:
                await index_transcript_chunks(
                    db, user_id=job.user_id, job_id=str(job.id), text=transcript.text
                )
        else:
            quality = transcript_row.quality_json or {"ok": True}
            progress["quality_check"] = "complete"
            await _save(db, job, progress=progress)

        rag_chunks: list[dict] = []
        if settings.rag_enabled and should_use_rag(
            transcript_row.full_text, job.use_org_memory, settings.rag_token_threshold
        ):
            rag_chunks = await retrieve_chunks(
                db,
                user_id=job.user_id,
                query=transcript_row.full_text,
                use_org_memory=job.use_org_memory,
            )

        if reuse_transcript:
            await db.execute(delete(ContentPiece).where(ContentPiece.job_id == job.id))
            await db.flush()

        quality_dict = (
            quality.as_dict()
            if hasattr(quality, "as_dict")
            else (quality if isinstance(quality, dict) else {"ok": True})
        )

        # Fetch Centralized User & Brand Memory
        from app.models.user import UserProfile

        user_prof = (
            await db.execute(select(UserProfile).where(UserProfile.user_id == job.user_id))
        ).scalar_one_or_none()
        user_memory = {}
        if user_prof:
            user_memory = {
                "full_name": user_prof.full_name,
                "organization": user_prof.organization,
                "job_title": user_prof.job_title,
                "bio": user_prof.bio,
                "linkedin_handle": user_prof.linkedin_handle,
                "instagram_handle": user_prof.instagram_handle,
                "website_url": user_prof.website_url,
                "brand_tone": user_prof.brand_tone,
                "custom_signoff": user_prof.custom_signoff,
            }

        graph = get_compiled_graph()
        initial = {
            "job_id": str(job.id),
            "user_id": str(job.user_id),
            "transcript_text": transcript_row.full_text,
            "avg_confidence": transcript_row.avg_confidence,
            "quality": quality_dict,
            "requested_types": job.requested_types or [],
            "target_languages": job.target_languages or ["en"],
            "use_org_memory": job.use_org_memory,
            "user_memory": user_memory,
            "retry_count": 0,
            "rag_chunks": rag_chunks,
        }
        await _save(db, job, status="analyzing", progress=progress)

        final_state = dict(initial)
        try:
            async for event in graph.astream(initial, stream_mode="updates"):
                if await _cancelled(db, job.id):
                    return
                for node_name, update in event.items():
                    if isinstance(update, dict):
                        final_state.update(update)

                    # Map LangGraph node names to stepper progress keys
                    if node_name == "parallel_analysis":
                        progress["topic_extraction"] = "complete"
                        progress["highlight_detection"] = "complete"
                        progress["speaker_analysis"] = "complete"
                        progress["sentiment_analysis"] = "complete"
                        progress["content_planner"] = "running"
                        next_status = "planning"
                    elif node_name == "content_planner":
                        progress["content_planner"] = "complete"
                        progress["generator"] = "running"
                        next_status = "generating"
                    elif node_name in ("dynamic_generator", "generator"):
                        progress["generator"] = "complete"
                        progress["guardrail"] = "running"
                        next_status = "guarding"
                    elif node_name in ("guardrail_node", "guardrail"):
                        progress["guardrail"] = "complete"
                        progress["translation"] = "running"
                        next_status = "translating"
                    elif node_name == "translation":
                        progress["translation"] = "complete"
                        next_status = "pending_review"
                    else:
                        if node_name in progress:
                            progress[node_name] = "complete"
                        next_status = {
                            "topic_extraction": "analyzing",
                            "highlight_detection": "analyzing",
                            "speaker_analysis": "analyzing",
                            "sentiment_analysis": "analyzing",
                            "content_planner": "planning",
                            "rag_retrieve": "planning",
                            "generator": "generating",
                            "guardrail": "guarding",
                            "translation": "translating",
                        }.get(node_name)

                    await _save(
                        db,
                        job,
                        status=next_status or job.status,
                        progress=dict(progress),
                    )
        except Exception as exc:
            await _save(
                db,
                job,
                status="failed",
                error_code="pipeline_failed",
                error_message=str(exc),
                finished_at=datetime.now(UTC),
                progress={
                    key: "failed" if progress.get(key) != "complete" else "complete"
                    for key in AGENT_KEYS
                },
            )
            return

        if await _cancelled(db, job.id):
            return

        route = final_state.get("route")
        for name, payload in (
            ("topics", final_state.get("topics")),
            ("highlights", final_state.get("highlights")),
            ("speakers", final_state.get("speakers")),
            ("sentiment", final_state.get("sentiment")),
            ("brief", final_state.get("brief")),
            ("guardrail", final_state.get("guardrail")),
        ):
            if payload:
                db.add(AgentOutput(job_id=job.id, agent_name=name, payload=payload))

        if route == "needs_reupload":
            await _save(
                db,
                job,
                status="needs_reupload",
                error_code="low_confidence",
                error_message="Transcript confidence too low to generate content",
                finished_at=datetime.now(UTC),
                progress={**_queued_progress(), "quality_check": "failed"},
            )
            return

        event_id = recording.event_id if hasattr(recording, "event_id") else None
        author_name = user_memory.get("full_name") or "Event Speaker"
        generated = list(final_state.get("generated") or [])
        for piece in generated:
            db.add(
                ContentPiece(
                    job_id=job.id,
                    user_id=job.user_id,
                    event_id=event_id,
                    author_name=author_name,
                    type=str(piece.get("type") or "summary"),
                    language="en",
                    title=piece.get("title"),
                    body=str(piece.get("body") or ""),
                    structured=piece.get("structured"),
                    status="pending_review",
                    grounding=piece.get("grounding"),
                    moderation=piece.get("moderation"),
                )
            )
        for item in final_state.get("translations") or []:
            db.add(
                ContentPiece(
                    job_id=job.id,
                    user_id=job.user_id,
                    event_id=event_id,
                    author_name=author_name,
                    type=str(item.get("type") or "summary"),
                    language=str(item.get("language") or "und"),
                    title=item.get("title"),
                    body=str(item.get("body") or ""),
                    status="pending_review",
                )
            )

        await write_audit(
            db,
            user_id=job.user_id,
            action="generate",
            resource_type="job",
            resource_id=str(job.id),
        )

        status = "needs_review" if route == "needs_review" else "pending_review"
        await _save(
            db,
            job,
            status=status,
            finished_at=datetime.now(UTC),
            progress={key: "complete" for key in AGENT_KEYS},
        )
    except asyncio.CancelledError:
        return
    finally:
        ACTIVE_JOB_TASKS.pop(job_str, None)
        CANCELLED_JOB_IDS.discard(job_str)


async def purge_expired_media() -> int:
    settings = get_settings()
    removed = 0
    async with SessionLocal() as db:
        rows = list((await db.execute(select(Recording))).scalars().all())
        cutoff_hours = settings.media_retention_hours
        now = datetime.now(UTC)
        for recording in rows:
            if recording.retain_source:
                continue
            created = recording.created_at
            if created is None:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age_hours = (now - created).total_seconds() / 3600
            if age_hours < cutoff_hours:
                continue
            from app.services.storage import get_storage

            if recording.storage_uri:
                get_storage().delete(recording.storage_uri)
                removed += 1
            recording.storage_uri = ""
        await db.commit()
    return removed
