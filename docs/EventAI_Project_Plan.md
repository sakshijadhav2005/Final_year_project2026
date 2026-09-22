# EventAI — Full Project Plan & Build Specification

**Product name:** EventAI  
**Tagline:** Intelligent Event Recording → Content Generation  
**Track:** Final Year Project, production-ready  
**Document type:** Single source of truth for *what we will build*, *how we will build it*, and *in what order*  
**Status:** Planning document — implementation starts after this spec  
**Version:** 1.0  
**Date:** 22 September 2026  

---

## 1. What we are building (one page)

**One-line pitch:** Upload an event recording (audio/video) → the system transcribes it, understands it through a multi-agent AI pipeline, and automatically produces publish-ready content (blog, newsletter, social posts, flyers, summaries) in multiple languages.

EventAI is a web application for event organizers and content teams. A user uploads a recording of a talk, meetup, conference session, or workshop. The backend:

1. Validates the file (type, size, duration, quality, stub antivirus scan).
2. Ingests media through **VideoDB** (transcription + indexing).
3. Runs a **LangGraph** stateful pipeline: quality check → four parallel analysis agents → content planner → optional RAG → Gemini generation → guardrails → translation.
4. Stores jobs, transcripts, and generated assets in **PostgreSQL** (with **pgvector** for selective RAG).
5. Shows a dark-mode-first dashboard where a human **approves** content before it is marked ready to publish.

This is **not** a chatbot that “talks about” an event. It is a **job-based content factory** with progress, confidence scores, review gates, and audit logs.

### 1.1 Who it is for

| Role | What they do in EventAI |
|------|-------------------------|
| **Event Organizer** | Uploads recordings, owns events, requests content packs, approves public assets |
| **Content Creator** | Reviews transcripts, edits/regenerates drafts, downloads publish-ready copy |
| **Admin** | Manages users, quotas, retention, failed jobs, system health |

### 1.2 Problem we solve

After an event, teams spend hours turning a 45-minute recording into a blog, LinkedIn post, newsletter blurb, and recap. Transcription, note-taking, and rewriting are slow and inconsistent. EventAI compresses that workflow into one upload + one review pass, while being honest that **transcript quality caps content quality**.

### 1.3 What “done” looks like for this academic project

A local (Docker) full stack a student can demo:

- Register / login with JWT roles  
- Upload a sample audio/video  
- See a job move through agent chips (running / complete / failed)  
- View transcript + confidence badge  
- Preview generated blog, LinkedIn post, and summary  
- Approve or reject before “ready to publish”  
- (Phase 2+) newsletter, IG caption, flyer, translation  
- README + `.env.example` + docker-compose so evaluators can run it  

---

## 2. Scope

### 2.1 In scope (we will build this)

**Core product**

- Web UI (React + Vite + TypeScript): auth, upload, dashboard, content preview, review/approve  
- FastAPI backend: auth, upload, jobs, content CRUD, WebSocket/SSE job progress  
- VideoDB ingest + transcription + scene/audio index  
- LangGraph multi-agent pipeline (see §6)  
- Gemini generation + translation  
- Selective RAG (long files / cross-event only)  
- PostgreSQL metadata + pgvector  
- Celery + Redis async jobs  
- JWT auth + RBAC (Admin / Content Creator / Event Organizer)  
- File validation, quality checks, denoise retry, confidence scoring  
- Guardrails: schema validation, moderation, hallucination/grounding check, human gate  
- Docker + docker-compose local stack  
- Basic tests for graph nodes and API endpoints  
- Structured logging + Sentry hook (even if Sentry DSN is optional in dev)  

**Content types (phased)**

| Phase | Content types |
|-------|----------------|
| Phase 1 (MVP) | Event summary, blog post, LinkedIn post |
| Phase 2 | Newsletter, Instagram caption, flyer copy (structured layout JSON + preview) |
| Later | Extra variants (tone/length), scheduled publish (optional, not MVP) |

**Languages**

- Source: whatever VideoDB/transcript language support we configure (English first for demo)  
- Output translation: user-selected target languages after guardrail pass (Phase 2)  

### 2.2 Out of scope for Phase 1 (explicit)

- Live streaming / real-time WebSocket transcription of an in-progress event  
- Direct LinkedIn / Instagram publishing APIs  
- Full ClamAV production cluster (we **stub** the scan hook in Phase 1)  
- Self-hosted Whisper as primary STT (kept as a **swappable provider interface** only)  
- Mobile native apps  
- Multi-tenant SaaS billing  
- Fine-tuning our own LLM  
- Forcing RAG on every short recording  

### 2.3 Suggested later advancements (documented, not Phase 1)

- Live event mode (VideoDB streaming)  
- Speaker-aware quotes in generated content  
- Auto-schedule to social APIs (always behind human approval)  
- Engagement scoring of social posts  
- Analytics on which content types get downloaded  
- Version history & regeneration with different tone/length  
- Human correction of agent tags feeding future few-shot examples  

---

## 3. Design decisions (locked for implementation)

These are the decisions we will **not** re-debate during scaffolding unless a library is unavailable.

| Topic | Decision | Why |
|-------|----------|-----|
| STT | VideoDB SDK, not raw Whisper in the app | Ingest + index + search in one vendor; Whisper remains a fallback interface |
| Orchestration | LangGraph **StateGraph**, not a linear LangChain chain | Parallel agents, retries, conditional routing |
| LLM | Google Gemini for generation + translation | Matches blueprint; cheaper models for tagging nodes if needed |
| RAG | **Optional**, gated by token length or “use org memory” flag | Short events fit context; RAG is complexity we only pay when needed |
| Vector store | **pgvector on PostgreSQL** first | One database for metadata + embeddings in Phase 1 |
| Jobs | Celery + Redis | Transcription/generation must not block HTTP |
| Auth | JWT access + refresh tokens, roles in claims | Simple, demoable, no extra IdP required for MVP |
| UI | Dark-mode-first “Deep Signal” theme | Agent chips and progress read well on dark surfaces |
| Layout | Golden ratio 61.8% / 38.2% + Fibonacci spacing | Distinctive, consistent FYP design system |
| Transcript in prompts | Always untrusted user content, never merged into system prompt | Prompt-injection defense |
| Publish | Nothing is “published” without human approval | Guardrail + academic honesty about hallucination |

---

## 4. Tech stack (use exactly this)

| Layer | Technology | Notes |
|-------|------------|--------|
| Frontend | React + TypeScript + Vite + TailwindCSS | Fast loop, typed UI |
| Server state | TanStack Query | Jobs, content, user |
| Client state | Zustand | Theme, auth session, UI panel |
| Backend | FastAPI, Python 3.11+ | Async API |
| Agents | LangGraph | Stateful graph |
| Media | VideoDB Python SDK | Upload, transcribe, index |
| LLM | Google Gemini API | Generate + translate |
| DB | PostgreSQL + pgvector | Users, jobs, content, embeddings |
| Queue | Celery + Redis | Long jobs |
| Auth | JWT + refresh, RBAC | Admin / Creator / Organizer |
| Containers | Docker + docker-compose | Local full stack |
| Monitoring | Structured logs + Sentry (optional DSN) | NFR: graceful API failure |
| CI | GitHub Actions (Phase 3) | Lint, test, build |
| Hosting (later) | Render / Cloud Run / ECS | After Docker works locally |

**If a package is unavailable:** propose the closest alternative in code comments and README; do not silently swap the architecture.

---

## 5. System architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                   │
│   Upload UI · Dashboard · Content Preview · Review/Approve UI    │
└───────────────────────────────┬───────────────────────────────────┘
                                 │ REST / WebSocket (or SSE)
┌───────────────────────────────▼───────────────────────────────────┐
│                    BACKEND API (FastAPI)                          │
│  Auth · Upload Handler · Job Orchestration · Rate Limiting        │
└───────┬─────────────────────────────────────────────┬─────────────┘
        │                                              │
┌───────▼─────────┐                          ┌─────────▼───────────┐
│  File Validation │                          │   Job Queue          │
│  + AV scan stub  │                          │  Celery + Redis      │
│  + Quality Check │                          │                      │
└───────┬─────────┘                          └─────────┬────────────┘
        │                                                │
        ▼                                                ▼
┌────────────────────┐                     ┌──────────────────────────┐
│   VideoDB Ingest    │                     │  LangGraph Orchestrator   │
│  + Transcription     │────transcript─────▶│  quality → 4 agents       │
│  + Scene/Audio Index │                     │  planner → RAG? → Gemini  │
└─────────────────────┘                     │  guardrail → translate    │
                                             └────────────┬──────────────┘
                                                          ▼
                           PostgreSQL + pgvector  →  User Dashboard
```

### 5.1 Runtime flow (happy path)

1. User authenticates; JWT stored (memory + httpOnly refresh cookie preferred; if cookies are hard in first week, localStorage with documented XSS caveat is acceptable for **dev only**, then tighten).  
2. `POST /uploads` with multipart file + consent checkbox + optional retain-media flag.  
3. API validates file, writes a `Job` row (`queued`), enqueues Celery task, returns `job_id`.  
4. Worker: AV stub → audio quality check → VideoDB ingest/transcribe → persist transcript + confidence.  
5. If confidence too low after denoise retry → `needs_reupload` (no generation).  
6. Else LangGraph runs; each node updates job progress (WebSocket/SSE).  
7. Guardrail pass → content rows `pending_review`.  
8. User approves → `ready_to_publish`. Reject → `rejected` with comment; optional regenerate later.

### 5.2 Failure flow (never silent hang)

Every VideoDB / Gemini / DB / Redis call: timeout + exponential backoff + circuit breaker (pybreaker or equivalent). After retries: job `failed` with a user-visible reason and a correlation id in logs. Partial artifacts (transcript) are kept so we do not re-transcribe on regenerate.

---

## 6. LangGraph pipeline (the core AI system)

We will implement a **StateGraph**, not a sequential script.

### 6.1 Shared graph state (conceptual)

```text
JobState
  job_id, user_id, org_id
  transcript_text          # untrusted
  transcript_segments[]    # text, start, end, confidence, speaker?
  quality                  # silence_ratio, sample_rate, avg_confidence
  topics                   # TopicExtractionResult | null
  highlights               # HighlightDetectionResult | null
  speakers                 # SpeakerAnalysisResult | null
  sentiment                # SentimentAnalysisResult | null
  brief                    # ContentPlan
  rag_chunks[]             # optional
  requested_types[]        # blog | linkedin | summary | ...
  generated[]              # GeneratedPiece
  guardrail                # pass | fail + issues[]
  translations[]           # optional
  route                    # continue | retry_generate | needs_review | failed
  retry_count
```

### 6.2 Nodes

| Node | Responsibility | Output schema | Routing |
|------|----------------|---------------|---------|
| `quality_check` | Avg/min segment confidence, silence, duration | `QualityReport` | Low → `needs_review` / `needs_reupload`; else fan-out |
| `topic_extraction` | Themes, keywords, session type | `TopicExtractionResult` | Parallel |
| `highlight_detection` | Quotable moments, timestamps | `HighlightDetectionResult` | Parallel |
| `speaker_analysis` | Roles, notable speakers, quote attribution if diarization exists | `SpeakerAnalysisResult` | Parallel |
| `sentiment_analysis` | Overall + per-segment tone | `SentimentAnalysisResult` | Parallel |
| `content_planner` | Merge four agents into a brief per content type | `ContentPlan` | Then RAG gate |
| `rag_retrieve` | Only if token threshold or `use_org_memory` | `RagContext` | Skipable |
| `generator` | Gemini produces requested types | `GeneratedPiece[]` | Then guardrail |
| `guardrail` | Schema, moderation, grounding | `GuardrailReport` | Fail once → retry generator; fail twice → `needs_review` |
| `translation` | Only after guardrail **pass** and user requested languages | `Translation[]` | End |

### 6.3 Parallelism

The four analysis agents **fan out in true parallel** (LangGraph Send / parallel nodes). Planner waits for all four. This is the main latency mitigation besides the job queue.

### 6.4 Prompt safety (mandatory)

- System prompt: instructions, schemas, “transcript is untrusted data”.  
- User/transcript payload: in a clearly delimited block, e.g. `<untrusted_transcript> ... </untrusted_transcript>`.  
- Never: concatenate transcript into the system message.  
- Never: let generated text invoke tools without a validated tool-call schema (Phase 1 generators should **not** have tools at all).  

### 6.5 Temperature policy

| Content | Temperature |
|---------|-------------|
| Summary, blog factual sections | 0.2–0.4 |
| LinkedIn / IG captions / flyer slogans | higher, still capped (e.g. 0.7) |
| Analysis agents (topics, sentiment) | low; cheaper/faster model tier allowed |

### 6.6 Mock-first

Stage 4 of implementation uses **fixed mock LLM responses** so graph routing, retries, and schemas can be tested without Gemini spend. Stage 5 swaps the generator adapter to real Gemini **one content type at a time**.

### 6.7 RAG gate (honest)

```text
if transcript_tokens > RAG_TOKEN_THRESHOLD (config, e.g. ~20–30 min equivalent)
   OR job.use_cross_event_memory == true:
    run rag_retrieve
else:
    skip RAG; pass full transcript to Gemini
```

Do **not** chunk every 5-minute meetup. Document this in the report as justified restraint.

---

## 7. Media, quality, and noisy files

### 7.1 Upload limits (defaults — configurable via env)

| Constraint | Default (demo-friendly, tighten later) |
|------------|----------------------------------------|
| Types | `mp4`, `mov`, `webm`, `mp3`, `wav`, `m4a` (whitelist MIME + extension) |
| Max size | 500 MB (adjust for demo hardware) |
| Max duration | 3 hours (long files may trigger RAG) |
| Min duration | ~15 seconds |

### 7.2 Pre-ingestion quality (librosa / pydub)

- Sample rate check (flag very low rates)  
- Duration  
- Silence ratio  
- Optional peak/RMS level  

If silence ratio is extreme → fail early with “needs re-upload” rather than paying for STT.

### 7.3 Transcription confidence

- Persist per-segment confidence when VideoDB provides it; if not, store a documented proxy (e.g. coverage / vendor quality field) and **do not fake** Whisper-style scores.  
- Low average confidence → **one** denoise retry (`noisereduce` spectral gating) → re-transcribe once.  
- Still low → `needs_reupload`.  
- Borderline segments → keep text marked `[unclear audio]` so Gemini does not invent words.  

### 7.4 User-facing quality

Dashboard shows a **transcript confidence badge** (high / medium / low) and explanation copy so sparse generated content is understandable.

### 7.5 Antivirus

`scan_file(path) -> ScanResult` interface. Production: ClamAV. Dev: stub that always returns `clean` unless `EVENTAI_FAKE_MALWARE=1` for tests. **Never skip the hook in the pipeline** — always call it.

---

## 8. Data model (what we persist)

Logical entities (SQLAlchemy / Alembic in implementation):

### 8.1 Users & auth

- `users`: id, email, hashed_password, role, is_active, created_at  
- `refresh_tokens`: id, user_id, token_hash, expires_at, revoked  
- `audit_logs`: id, user_id, action, resource_type, resource_id, ip, created_at, metadata JSON  

### 8.2 Events & media

- `events`: id, organizer_id, title, description, consent_confirmed, created_at  
- `recordings`: id, event_id, storage_uri, content_type, size_bytes, duration_sec, videodb_id, retain_until, deleted_at  
- `transcripts`: id, recording_id, full_text, language, avg_confidence, quality_json, denoise_attempted  

### 8.3 Jobs & pipeline

- `jobs`: id, user_id, recording_id, status, requested_types JSON, progress_json, error_code, error_message, started_at, finished_at  
- Status enum: `queued | validating | transcribing | analyzing | planning | generating | guarding | translating | pending_review | ready_to_publish | needs_reupload | needs_review | failed | cancelled`

### 8.4 Agent outputs & content

- `agent_outputs`: job_id, agent_name, payload JSON, schema_version, created_at  
- `content_pieces`: id, job_id, type, language, title, body, structured_json (flyer), status (`draft | pending_review | approved | rejected`), grounding_json, moderation_json, version  
- `embeddings`: id, org_id, source_type (`transcript_chunk | past_newsletter`), chunk_text, embedding vector, metadata  

### 8.5 Retention / privacy

- Upload requires **consent checkbox**: “Participants were informed this recording may be processed.” Stored on `events.consent_confirmed`.  
- Configurable `MEDIA_RETENTION_HOURS`; worker deletes raw files unless `retain_source=true`.  
- Optional PII redaction flag (Phase 2+): mask names in transcript before generation.  

---

## 9. API surface (backend contract)

Base: `/api/v1`. All mutating routes authenticated unless noted.

### 9.1 Health & meta

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/ready` | DB + Redis ping |

### 9.2 Auth

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/register` | Create user (role restricted: first Admin via env, else Organizer/Creator) |
| POST | `/auth/login` | Access + refresh |
| POST | `/auth/refresh` | Rotate refresh |
| POST | `/auth/logout` | Revoke refresh |
| GET | `/auth/me` | Current user |

### 9.3 Uploads & jobs

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/uploads` | Multipart upload, create recording + job |
| GET | `/jobs` | List current user’s jobs |
| GET | `/jobs/{id}` | Status, progress, confidence |
| GET | `/jobs/{id}/transcript` | Transcript + segments |
| POST | `/jobs/{id}/cancel` | Best-effort cancel |
| POST | `/jobs/{id}/regenerate` | New content types / tone (Phase 2; stub ok in P1) |
| WS/SSE | `/jobs/{id}/events` | Agent progress stream |

### 9.4 Content

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/jobs/{id}/content` | All pieces |
| GET | `/content/{id}` | One piece |
| PATCH | `/content/{id}` | Inline edit (creator/organizer) |
| POST | `/content/{id}/approve` | Human gate |
| POST | `/content/{id}/reject` | With reason |
| GET | `/content/{id}/download` | Markdown / text / JSON for flyer |

### 9.5 Admin

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/jobs` | All jobs |
| GET | `/admin/audit` | Audit log query |
| POST | `/admin/users/{id}/role` | Change role |

**Rate limits:** uploads and generate/regenerate endpoints (slowapi or equivalent).

---

## 10. Frontend: screens, design system, UX

### 10.1 Screens we will ship

1. **Landing / upload hero** — 61.8% of first viewport height is the upload module; 38.2% is steps (“Upload → Transcribe → Analyze → Generate → Approve”).  
2. **Login / Register**  
3. **Dashboard** — golden split: **61.8%** main (job list + selected job transcript/content), **38.2%** side panel (agent chips, history, quality badge).  
4. **Job detail** — progress, transcript with `[unclear audio]` styling, content tabs (blog / LinkedIn / summary).  
5. **Review** — approve / reject / edit before publish.  
6. **Settings (minimal)** — theme, retention opt-in, language targets (Phase 2).  
7. **Admin (minimal)** — users + failed jobs.  

### 10.2 Design system — “Deep Signal” (Option A), dark-mode-first

**Color**

| Token | Value | Use |
|-------|-------|-----|
| Primary | `#4F46E5` | Buttons, links |
| Primary dark | `#3730A3` | Hover / pressed |
| Accent | `#14B8A6` | Agent active, highlights, success-adjacent |
| Success | `#22C55E` | Complete chips |
| Warning | `#F59E0B` | Medium confidence |
| Error | `#EF4444` | Failed / low quality |
| BG dark | `#0F1115` | App background |
| Surface dark | `#1A1D23` | Cards |
| Text dark | `#E6E6EA` | Body on dark |
| BG light | `#FAFAFA` | Light fallback |
| Surface light | `#FFFFFF` | Light cards |
| Text light | `#1E1E24` | Body on light |

**Typography**

- Body/UI: **Manrope** (or Inter)  
- Headings: **Sora** (or Space Grotesk)  
- Scale: body **16px**, H3 **20px**, H2 **26px**, H1 **42px**  

**Spacing (Fibonacci, 8px base):** `8, 13, 21, 34, 55, 89` px only for padding/margin. No ad-hoc `12px` / `16px` / `24px` unless it already equals a scale step (8 is allowed).

**Cards:** preview cards ≈ **1.618 : 1** (landscape social/blog) or **1 : 1.618** (flyer portrait).

**Agent chips:** `queued | running | complete | failed | skipped` with accent pulse while running.

**Motion:** prefer status updates over a single infinite spinner. Communicate that a long recording can take **minutes**.

---

## 11. Security & privacy (build checklist)

We will implement these as code, not slides:

1. Whitelist file type/size/duration; reject double extensions / spoofed MIME.  
2. AV scan hook before VideoDB.  
3. All VideoDB / Gemini keys **server-side only** (`os.environ`). Never `VITE_GEMINI_*`.  
4. TLS in production; local HTTP ok in docker-compose.  
5. Encrypt at rest as a **documented hosting concern**; app-level: hashed passwords (bcrypt/argon2), hashed refresh tokens.  
6. JWT access (short) + refresh (rotate). RBAC on every route.  
7. Rate limit upload/generate.  
8. Transcript = untrusted; structural prompt split.  
9. Audit log: generate, approve, reject, download, delete.  
10. Consent checkbox required.  
11. Retention / auto-delete worker.  
12. CORS allowlist of frontend origin.  
13. No secrets in git; `.env.example` only.  

**Ethical note for the report:** recordings contain voices and opinions. Technical controls do not replace **participant consent**. We surface this in the UI and the dissertation limitations chapter.

---

## 12. Guardrails (inside the graph)

| Guardrail | Where | What it catches |
|-----------|-------|-----------------|
| Input validation | Upload + quality node | Bad files, extreme silence, injection-looking patterns logged (not blindly stripped from speech) |
| Schema validation | After every LLM node | Invalid JSON → retry once |
| Content moderation | Post-generation | Hate, defamation-style claims, obvious PII dumps — fail to `needs_review` |
| Hallucination / grounding | Post-generation | Claims not traceable to a transcript span → flag or strip |
| Human review | Before publish | Required for all public-facing types |
| Failure fallback | Every external call | Backoff then `failed`, never hang |

Grounding approach: lightweight verifier prompt (or heuristic quote match) that maps claims → transcript spans. Unsupported claims are **not** silently published.

---

## 13. Drawbacks, limitations, and mitigations (for the report *and* the product)

We will implement the mitigations that are in scope; the rest stay as documented future work.

| # | Drawback | Mitigation we will actually build |
|---|----------|-----------------------------------|
| 1 | VideoDB / Gemini outages | Retry + backoff + circuit breaker; cache transcript; `STTProvider` / `LLMProvider` interfaces |
| 2 | Noisy / multi-speaker audio | Quality check, denoise once, `[unclear audio]`, confidence badge; transcript edit UI as soon as practical |
| 3 | Hallucination | Grounding check, low temperature for factual types, human approve |
| 4 | Latency | Parallel agents, job queue, streamed node status |
| 5 | Cost | Reuse transcript; cheaper model for tagging; quotas in config |
| 6 | RAG overhead | Length/org-memory gate only |
| 7 | Translation quality | Phase 2: back-translation check for selected languages |
| 8 | No agent feedback loop | Phase 2: accept/reject topics before planner if time; else listed as enhancement |
| 9 | Privacy | Consent, retention, server-side keys, optional PII later |

---

## 14. Repository layout (what we will create)

```text
Final_year_project/
  docs/
    EventAI_Project_Plan.md          ← this document
  README.md
  .env.example
  docker-compose.yml
  .github/workflows/ci.yml           ← Phase 3
  backend/
    app/
      main.py
      core/          # config, security, logging
      api/           # routers
      models/
      schemas/
      services/      # videodb, gemini, quality, av_scan
      providers/     # STTProvider, LLMProvider
      graphs/        # LangGraph StateGraph + nodes
      workers/       # Celery tasks
      db/
    tests/
    Dockerfile
    pyproject.toml / requirements.txt
  frontend/
    src/
      pages/
      components/
      layouts/       # golden-ratio shell
      lib/           # api client, query
      store/         # zustand
      styles/        # design tokens (phi spacing, colors)
    Dockerfile
    package.json
```

---

## 15. Environment variables (no secrets in source)

`.env.example` will list (names may be refined in code):

```text
# App
EVENTAI_ENV=development
SECRET_KEY=
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=http://localhost:5173

# Postgres
DATABASE_URL=postgresql+asyncpg://eventai:eventai@postgres:5432/eventai

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# VideoDB
VIDEODB_API_KEY=
VIDEODB_COLLECTION=

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL_GENERATE=gemini-3.6-flash
GEMINI_MODEL_ANALYZE=gemini-3.6-flash

# RAG
RAG_TOKEN_THRESHOLD=12000
RAG_ENABLED=true

# Media
MAX_UPLOAD_MB=500
MAX_DURATION_SEC=10800
MEDIA_RETENTION_HOURS=72
CLAMAV_ENABLED=false

# Sentry (optional)
SENTRY_DSN=
```

---

## 16. Implementation roadmap (how we build it)

Work **incrementally**. Each stage must be runnable before the next starts.

### Stage 1 — Scaffolding (health checks)

- Monorepo folders, docker-compose: `frontend`, `backend`, `postgres` (pgvector image), `redis`  
- FastAPI `/health` + `/ready`  
- Vite React app with design tokens (colors, fonts, spacing) and a placeholder layout  
- README: how to `docker compose up`  

**Exit criteria:** Browser opens the app; `GET /health` returns ok.

### Stage 2 — Auth

- Register, login, refresh, `/me`  
- Roles in JWT  
- Frontend login/register + protected routes  

**Exit criteria:** Cannot open dashboard without token; role claim visible.

### Stage 3 — Upload + VideoDB transcription

- Validation + AV stub + quality check  
- Celery task (can run **inline/thread** in Stage 3 if Celery wiring is still young — but the **task function** must exist)  
- Persist recording + transcript  
- Dashboard shows job + transcript  

**Exit criteria:** Upload sample file → transcript in UI (or vendor sandbox). If VideoDB keys missing, **fake STT provider** returns a fixture transcript so UI still works.

### Stage 4 — LangGraph with mocks

- StateGraph with quality + 4 agents + planner  
- Pydantic schemas + retry on bad JSON  
- Mock LLM  
- Agent chips update from job progress  

**Exit criteria:** Fixture transcript produces planner brief without Gemini.

### Stage 5 — Real Gemini, one type at a time

1. Summary  
2. LinkedIn post  
3. Blog  

**Exit criteria:** Three previews on dashboard from a real or recorded demo file.

### Stage 6 — Guardrails

- Schema, moderation, grounding  
- Retry generate once  
- Human approve/reject  

**Exit criteria:** Ungrounded claim flagged; approve required for `ready_to_publish`.

### Stage 7 — Translation

- After guardrail pass  
- Store `language` on content pieces  

### Stage 8 — Dashboard polish

- Golden ratio layout, Fibonacci spacing, chips, confidence badge, dark/light  

### Stage 9 — Real async queue

- Celery workers in compose  
- SSE/WebSocket progress  
- No HTTP request waits for Gemini  

### Stage 10 — Tests

- Graph routing (quality fail → needs_reupload)  
- Auth + upload validation API tests  
- Guardrail retry unit tests  

### Mapping to original phases

| Original phase | Stages | Calendar (guide) |
|----------------|--------|------------------|
| Phase 1 MVP (4–6 weeks) | 1–6 + 8 (summary/blog/LinkedIn) | First demo |
| Phase 2 | 7 + remaining content types + RAG path + richer HITL | Mid demo |
| Phase 3 | 9–10 + Sentry + GitHub Actions + load/security notes | Final |

---

## 17. Testing strategy

| Layer | What |
|-------|------|
| Unit | Pydantic schemas; quality routing; RAG gate predicate; prompt builders (system vs transcript split) |
| Graph | Mocked LLMs; fan-in planner; guardrail retry then `needs_review` |
| API | Auth, forbidden roles, upload reject (bad type), job status |
| Frontend | Later: critical pages if time; otherwise manual demo script |
| Manual demo script | 1 clean audio, 1 silent/noisy file, 1 approve flow, 1 failed job |

---

## 18. Non-functional requirements

| NFR | Target |
|-----|--------|
| Upload response | Returns `job_id` in seconds; processing async |
| Progress | UI updates as nodes complete, not only at the end |
| Failures | User-visible error + logs with job id |
| Secrets | Env only |
| Accessibility | Keyboard login, contrast on dark theme, chip labels not color-only |
| Observability | JSON logs; optional Sentry |
| Reproducibility | docker-compose + README |

---

## 19. Demo script (for viva / evaluation)

1. Show architecture slide from this document.  
2. Login as Organizer.  
3. Upload a short event clip; point at consent checkbox.  
4. Side panel: agents go running → complete.  
5. Show confidence badge and a `[unclear audio]` example if possible.  
6. Open Summary / LinkedIn / Blog; show grounding flags if any.  
7. Approve blog; status becomes ready to publish.  
8. Show that a second generate does **not** re-call VideoDB (cached transcript).  
9. (If Phase 2) Translate one piece.  
10. Mention RAG is **off** for this short clip and **why**.  

---

## 20. Academic report mapping (what this doc feeds)

| Report chapter | Use this spec |
|----------------|---------------|
| Introduction / problem | §1–2 |
| Literature / related | VideoDB, LangGraph, RAG selectivity, Gemini |
| Requirements | §2, §9, §18 |
| Architecture | §5–6 |
| Implementation | §14–16 |
| UI/UX | §10 |
| Security & ethics | §11, limitation #9 |
| Testing | §17 |
| Results / demo | §19 |
| Limitations & future work | §13, §2.3 |

---

## 21. Assumptions (so we do not guess later)

1. **Demo language is English first.** Other source languages depend on VideoDB; translation is output-side.  
2. **Flyer** in Phase 2 is structured copy + CSS preview, not a full Canva-quality PDF designer. PDF export is nice-to-have.  
3. **Object storage:** local disk / docker volume in Phase 1; S3-compatible interface can be added without changing API.  
4. **VideoDB account** may be unavailable on day 1 → `FakeSTTProvider` + fixture media is a first-class path.  
5. **Single organization per user** in Phase 1 (no complex tenancy). Cross-event RAG is “this user’s past approved content.”  
6. **WebSocket vs SSE:** SSE is acceptable if WS complexity slows Stage 9.  
7. **Register:** open self-register as Organizer/Creator; Admin seeded by env `BOOTSTRAP_ADMIN_EMAIL`.  

---

## 22. Open points (only if we must change the spec)

These were **not** blocking this plan. Default answers are already chosen:

| Question | Default we will use |
|----------|---------------------|
| Exact Gemini model IDs | Env-configurable; start with a current Flash-class model |
| Access token storage | Prefer httpOnly cookie; document if we use memory+refresh |
| Max upload for college demo | 500 MB default, lower if machines are weak |
| ClamAV in student labs | Stub on, real daemon optional in compose profile `security` |

If VideoDB SDK APIs differ from this document, **adapt the provider**, do not redesign the graph.

---

## 23. Definition of a successful FYP

Evaluators can clone (or unzip) the repo, copy `.env.example`, run docker-compose, register, upload a sample, and see a **multi-agent pipeline** produce **reviewable content** with **honest confidence and limitations**. The report can justify **selective RAG**, **human gates**, and **third-party risk** instead of claiming a fully autonomous publisher.

---

## 24. Immediate next step after this document

**Stage 1 scaffolding** — not a giant dump of the whole app:

1. `docker-compose.yml` + Postgres (pgvector) + Redis  
2. FastAPI health/ready  
3. Vite + React + Tailwind with Deep Signal tokens and golden-ratio shell  
4. Root README  

No API keys in source. Confirm Stage 1 runs, then Stage 2 Auth.

---

*End of EventAI project plan. This file is the implementation contract until a later version is explicitly written.*
