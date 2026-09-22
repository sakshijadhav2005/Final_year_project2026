# EventAI

**Intelligent Event Recording → Content Generation**

Upload an event recording (audio/video or transcript text), transcribe with VideoDB, analyze with a stateful LangGraph multi-agent pipeline, generate publish-ready copy with Google Gemini, and human-approve before anything is marked ready to publish.

The full specification and blueprint is in [`docs/EventAI_Project_Plan.md`](docs/EventAI_Project_Plan.md).

---

## Current Status: Production Ready

All core stages (Stages 1 through 10) are implemented and verified:
- **Authentication & RBAC:** JWT access & refresh tokens with roles (`admin`, `event_organizer`, `content_creator`).
- **Media Ingestion & Quality:** Silence ratio, sample rate analysis, AV scan hook stub, and audio confidence metrics.
- **Cloud Object Storage (Cloudflare R2):** S3-compatible cloud storage adapter for Cloudflare R2 (zero egress fees) and AWS S3/MinIO, with automatic local fallback.
- **Dual STT Engine:** VideoDB cloud transcription with offline fallback (`FakeSTTProvider`).
- **LangGraph Multi-Agent Pipeline:**
  - Parallel fan-out: **Topic Extraction**, **Highlight Detection**, **Speaker Analysis**, **Sentiment Analysis**.
  - **Content Planner** brief synthesis.
  - **Selective RAG:** Conditional retrieval using PostgreSQL `pgvector` embeddings when tokens > threshold or org-memory is enabled.
  - **Gemini Generator:** Structured generation with prompt injection protection.
  - **Dual Guardrails:** Automated moderation and transcript grounding checks.
  - **Multi-Language Translation:** Output translation for international audiences.
- **Rich Content Studio UI:**
  - 📝 **Executive Summary:** High-level takeaways and metrics.
  - 📰 **Blog Article:** Editorial formatting with reading time estimation.
  - 💼 **LinkedIn Post:** Authentic feed card with hashtag cloud and engagement metrics.
  - 📧 **Newsletter:** Email template with header, recap, and call-to-action button.
  - 📸 **Instagram Caption:** Social media card with emojis and copy caption.
  - 🎨 **Event Flyer:** Golden-ratio portrait visual poster preview.
  - ✏️ **Inline Editing:** Live drafting and saving via `PATCH /api/v1/content/{id}`.
  - 📋 **One-Click Actions:** Animated copy-to-clipboard and multi-format export (`.md`, `.txt`, `.json`).
  - ⚡ **Live Real-Time SSE:** Dynamic agent chip pulsing via Server-Sent Events without polling lag.
  - ⚙️ **Settings & Diagnostics:** Theme toggle (dark/light), media retention auto-purge policies, and target languages.
- **Test Suite:** 19 automated unit and integration tests covering all critical paths.

---

## Tech Stack

| Component | Technology | Description |
|---|---|---|
| **Frontend** | React 19, TypeScript, Vite, TailwindCSS | "Deep Signal" dark-mode first design with golden-ratio shell (61.8% / 38.2%) and Fibonacci spacing. |
| **Backend API** | FastAPI, Python 3.11+, Pydantic v2 | Async REST API, SSE streaming, file streaming, audit trails. |
| **Multi-Agent** | LangGraph (`StateGraph`) | Stateful orchestration, parallel nodes, conditional branching. |
| **Cloud Storage** | Cloudflare R2 / AWS S3 (`boto3`) | S3-compatible zero-egress object storage with local disk fallback. |
| **Media & AI** | VideoDB & Google Gemini (`gemini-3.6-flash`) | Speech-to-text, scene index, structured content generation. |
| **Database** | PostgreSQL + `pgvector`, Redis | Relational data, audit logs, vector similarity search. |
| **Task Queue** | Celery + Redis | Asynchronous background processing. |

---

## Quick Start (Docker Compose)

Run the full stack with a single command:

```bash
cp .env.example .env
docker compose up --build
```

- **Web Application:** http://localhost:8080
- **FastAPI Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Readiness Ping (PostgreSQL + Redis):** http://localhost:8000/api/v1/ready

---

## Local Development (Without Docker for Apps)

### 1. Start Database & Cache
```bash
docker compose up -d postgres redis
```

### 2. Backend Server
```bash
cd server
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Client
```bash
cd client
npm install
npm run dev
```
Client runs at `http://localhost:5173` and proxies `/api` requests to `http://localhost:8000`.

---

## Running the Automated Test Suite

Run the full pytest suite in the server directory:

```bash
cd server
.venv\Scripts\pytest
```

---

## Demo Files & Viva Presentation Guide

For viva evaluation and demonstration, sample files are provided in [`data/samples/`](data/samples/):

1. **Clean Talk Session:** [`data/samples/clean_event_session.txt`](data/samples/clean_event_session.txt)
   - Demonstrates high audio confidence, parallel agent execution, and clean grounding across all 6 formats.
2. **Noisy Session with Unclear Audio:** [`data/samples/noisy_audio_sample.txt`](data/samples/noisy_audio_sample.txt)
   - Demonstrates the audio confidence badge, `[unclear audio]` handling, and grounding alerts.

### Viva Step-by-Step Script:
1. **Login:** Register or login as `organizer@example.com`.
2. **Upload:** Select `clean_event_session.txt`, check the mandatory participant consent box, select target languages, and hit **Start Processing**.
3. **Live Pipeline:** Watch the side panel agent chips transition live from `queued` to `running` to `complete` via SSE.
4. **Content Studio:**
   - Switch between **Summary**, **Blog**, **LinkedIn**, **Newsletter**, **Instagram**, and **Flyer**.
   - Click **✏️ Edit Copy** on the Blog post, adjust a sentence, and click **💾 Save Changes**.
   - Click **📋 Copy** to demonstrate one-click clipboard copying.
   - Click **📥 Download** to download the Markdown or JSON asset.
   - Hit **✓ Approve** on the draft to observe the status transition to `ready_to_publish`.
5. **Architectural Justification:** Explain how selective RAG prevents unnecessary vector search cost on short recordings, and why the Human-in-the-Loop review gate ensures zero unverified AI output reaches the public.
