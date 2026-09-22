# Final Year Project Report: EventAI

**Intelligent Event Recording → Content Generation**

---

## 1. Abstract
EventAI is a state-of-the-art web application designed for event organizers and content teams. It streamlines the post-event content creation workflow by allowing users to upload event recordings (audio/video). The system transcribes the media, processes it through a LangGraph-based multi-agent AI pipeline, and automatically produces structured, publish-ready content such as blogs, newsletters, and social media posts (e.g., LinkedIn, Instagram). The platform includes a human-in-the-loop review system to ensure quality and mitigate hallucination.

## 2. Problem Statement
Following a conference, meetup, or talk, content teams spend hours transcribing audio, taking notes, and rewriting content into various formats. This manual process is slow, inconsistent, and expensive. EventAI compresses this workflow into a single upload-and-review pass, using AI to extract topics, highlights, sentiment, and generate formatted copy.

## 3. Technology Stack
EventAI is built on a modern, robust, and asynchronous tech stack to ensure high performance and scalability:
- **Frontend**: React 19, TypeScript, Vite, TailwindCSS (Deep Signal dark-mode first design with golden-ratio layouts).
- **Backend**: FastAPI (Python 3.11+), Pydantic v2.
- **AI & Pipeline**: LangGraph (`StateGraph`), Google Gemini API for generation/translation.
- **Media Ingestion**: VideoDB for transcription, indexing, and search.
- **Database**: PostgreSQL with `pgvector` (for selective RAG embeddings).
- **Queueing**: Celery & Redis for asynchronous background tasks.
- **Cloud Storage**: S3-compatible cloud storage adapter (Cloudflare R2, AWS S3/MinIO) with local disk fallback.

## 4. System Architecture
The application is separated into a decoupled client-server model:
1. **Frontend (React)**: Handles JWT authentication, file uploads, real-time job progress (via WebSocket/SSE), and a rich Content Studio UI for live editing and human approval.
2. **Backend API (FastAPI)**: Orchestrates the business logic, handles uploads, enforces role-based access control (Admin, Event Organizer, Content Creator), and manages database persistence.
3. **Background Worker (Celery)**: Processes long-running tasks including media quality checks, VideoDB ingestion, and the AI agent pipeline.

### The LangGraph Pipeline
Instead of a linear script, EventAI orchestrates AI operations via a **StateGraph**. The multi-agent pipeline includes:
- **Quality Check**: Validates audio silence ratio and duration.
- **Parallel Analysis Agents**: Extracts **Topics**, **Highlights**, **Speakers**, and **Sentiment** concurrently to reduce latency.
- **Content Planner**: Synthesizes the analysis into a comprehensive brief.
- **Selective RAG**: Conditionally retrieves past organizational memory (via `pgvector`) if the transcript exceeds token thresholds.
- **Gemini Generator**: Formats the brief into structured pieces (blogs, newsletters, etc.).
- **Guardrails**: Automated checks for moderation, schema validation, and transcript grounding.

## 5. Security & Privacy
EventAI incorporates multiple layers of security and ethical guardrails:
- **Participant Consent**: Uploads require explicit confirmation that participants consented to recording and AI processing.
- **Data Retention Policies**: Automated cron jobs purge raw media files after a configured retention period unless specifically marked to be kept.
- **RBAC & JWT**: Strict role-based routing (Admin, Creator, Organizer) verified on every API request.
- **Prompt Injection Defense**: Transcripts are treated as untrusted inputs and wrapped safely outside of system instructions.
- **Human-In-The-Loop**: No AI-generated content is marked "ready to publish" without explicit human approval.

## 6. How to Run the Project Locally

### Option 1: Docker Compose (Quick Start)
Run the full stack (Frontend, Backend, PostgreSQL, Redis) with a single command:
```bash
cp .env.example .env
# Edit .env and insert your GEMINI_API_KEY and VIDEODB_API_KEY
docker compose up --build
```
- Web Application: http://localhost:8080
- FastAPI Documentation: http://localhost:8000/docs

### Option 2: Manual Local Development
**1. Start Database & Cache:**
```bash
docker compose up -d postgres redis
```

**2. Start Backend Server:**
```bash
cd server
python -m venv .venv
.\.venv\Scripts\activate   # On Windows
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

**3. Start Frontend Client:**
```bash
cd client
npm install
npm run dev
```
The client runs at `http://localhost:5173` and proxies API requests to the FastAPI backend.

---
*Generated for the Final Year Project Evaluation - 2026*
