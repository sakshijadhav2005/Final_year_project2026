"""System diagrams for the paper (architecture, LangGraph pipeline). Drawn from the code
structure: app/main.py routers, app/services/job_runner.py, app/graphs/pipeline.py.

    python evaluation/scripts/diagrams.py
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

import harness  # noqa: E402

FIG = harness.EVAL / "figures"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                     "font.size": 6, "pdf.fonttype": 42, "savefig.bbox": "tight"})

BLUE, ORANGE, GREEN, GREY, PURPLE, RED = "#dbe7f3", "#fbe3d1", "#e2efda", "#ededed", "#e8e0f0", "#f8d7da"
EDGE = "#333333"


def box(ax, x, y, w, h, text, fc, fs=6, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.08",
                                fc=fc, ec=EDGE, lw=0.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", linespacing=1.15)


def arrow(ax, x1, y1, x2, y2, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=6, lw=0.6,
                                 color=EDGE, linestyle=ls, connectionstyle=f"arc3,rad={rad}"))


def label(ax, x, y, text, fs=5.5):
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, style="italic",
            bbox={"fc": "white", "ec": "none", "pad": 0.4})


def title(ax, x, y, text):
    ax.text(x, y, text, ha="center", va="bottom", fontsize=7, fontweight="bold")


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=300)
    plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(7.16, 3.1))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 6.3)
    ax.axis("off")

    title(ax, 1.5, 5.85, "Web client")
    box(ax, 0.1, 3.9, 2.8, 1.85, "React 19 + TypeScript\n(Vite, Tailwind CSS)\n\nUpload  ·  live pipeline (SSE)\nContent Studio  ·  review", BLUE)
    title(ax, 5.15, 5.85, "API layer")
    box(ax, 3.6, 3.9, 3.1, 1.85, "FastAPI (async, Pydantic v2)\nJWT auth + role-based access\nuploads · jobs · content\nevents · chat · audit log", ORANGE)
    title(ax, 8.95, 5.85, "Job orchestration")
    box(ax, 7.4, 3.9, 3.1, 1.85, "Job runner\n(background task / Celery)\nmedia check · VAD · STT\nchunk indexing · RAG pool", GREEN)
    title(ax, 12.95, 5.85, "Multi-agent pipeline")
    box(ax, 11.2, 3.9, 3.7, 1.85, "LangGraph StateGraph\nquality gate → analysis → planner\n→ RAG retrieve → 6 writer agents\n(parallel Send) → guardrail\n→ retry / review / translation", PURPLE)

    arrow(ax, 2.9, 5.05, 3.6, 5.05)
    arrow(ax, 3.6, 4.6, 2.9, 4.6)
    label(ax, 3.25, 5.4, "REST / SSE")
    arrow(ax, 6.7, 4.82, 7.4, 4.82)
    label(ax, 7.05, 5.2, "enqueue")
    arrow(ax, 10.5, 4.82, 11.2, 4.82)
    label(ax, 10.85, 5.2, "state")

    title(ax, 1.5, 2.95, "Media")
    box(ax, 0.1, 0.5, 2.8, 2.35, "Object storage\nlocal disk / Cloudflare R2\n/ S3 / MinIO\nstreamed uploads, SHA-256,\nretention purge", GREY)
    title(ax, 5.15, 2.95, "Persistence")
    box(ax, 3.6, 0.5, 3.1, 2.35, "PostgreSQL / SQLite\nusers · events · jobs\ntranscripts · content\nembeddings (JSON vectors)\naudit log", GREY)
    arrow(ax, 4.3, 3.9, 2.2, 2.85)
    arrow(ax, 5.15, 3.9, 5.15, 2.85, style="<|-|>")
    arrow(ax, 7.9, 3.9, 6.7, 2.4, style="<|-|>")

    box(ax, 7.4, 0.5, 7.5, 2.35, "", "#fff8e1")
    ax.text(11.15, 2.58, "Google Cloud Vertex AI (Application Default Credentials)", ha="center",
            fontsize=6.5, fontweight="bold")
    box(ax, 7.6, 0.7, 2.25, 1.55, "Gemini STT\naudio split at quiet\npoints, chunks in\nparallel", "white")
    box(ax, 10.0, 0.7, 2.3, 1.55, "Gemini LLM\nfallback chain\nflash-lite → flash", "white")
    box(ax, 12.45, 0.7, 2.25, 1.55, "gemini-embedding-001\n768-d, regional\nendpoint", "white")
    arrow(ax, 8.7, 3.9, 8.7, 2.25)
    arrow(ax, 9.9, 3.9, 13.4, 2.25, rad=-0.12)
    arrow(ax, 12.2, 3.9, 11.15, 2.25)
    arrow(ax, 13.8, 3.9, 13.8, 2.25)
    save(fig, "fig_architecture")


def pipeline():
    fig, ax = plt.subplots(figsize=(7.16, 2.5))
    ax.set_xlim(0, 17.2)
    ax.set_ylim(-0.1, 5.4)
    ax.axis("off")
    y, h = 2.2, 1.1
    steps = [
        (0.0, 1.4, "Upload\n+ consent", GREY),
        (1.75, 1.5, "Media check\nVAD, AV scan", GREY),
        (3.6, 1.4, "Speech-to-text\n(Vertex STT)", BLUE),
        (5.35, 1.45, "Quality gate\n(confidence)", GREY),
        (7.15, 1.75, "Analysis\ntopics · highlights\nspeakers · tone", ORANGE),
        (9.25, 1.25, "Planner\n(brief)", ORANGE),
        (10.85, 1.35, "Selective\nRAG", GREEN),
    ]
    for x, w, t, c in steps:
        box(ax, x, y, w, h, t, c, fs=5.5)
    for (x1, w1, *_), (x2, *_r) in zip(steps, steps[1:]):
        arrow(ax, x1 + w1, y + h / 2, x2, y + h / 2)

    agents = ["Summary", "Blog", "LinkedIn", "Newsletter", "Instagram", "Flyer"]
    ax0, aw = 12.75, 1.3
    for i, a in enumerate(agents):
        yy = 4.25 - i * 0.68
        box(ax, ax0, yy, aw, 0.52, a, PURPLE)
        arrow(ax, 12.2, y + h / 2, ax0, yy + 0.26)
        arrow(ax, ax0 + aw, yy + 0.26, 14.65, y + h / 2)
    ax.text(ax0 + aw / 2, 4.9, "6 writer agents (parallel)", ha="center", fontsize=5.5, style="italic")

    box(ax, 14.65, y, 1.15, h, "Guardrail\ngrounding\n+ moderation", RED, fs=5)
    # Retry loop: back to the agents, failed drafts only, once.
    ax.annotate("", xy=(ax0 + aw / 2, 4.82), xytext=(15.22, y + h),
                arrowprops={"arrowstyle": "-|>", "lw": 0.6, "ls": "--", "color": EDGE,
                            "connectionstyle": "arc3,rad=0.45"})
    label(ax, 15.9, 4.7, "retry failed\ndrafts (once)")
    box(ax, 16.05, y, 1.1, h, "Translate\n→ pending\nreview", GREEN, fs=5)
    arrow(ax, 15.8, y + h / 2, 16.05, y + h / 2)
    box(ax, 14.4, 0.1, 1.65, 0.8, "Human review\n(needs_review)", RED, fs=5.5)
    arrow(ax, 15.22, y, 15.22, 0.9)
    label(ax, 15.95, 1.55, "still failing")

    box(ax, 3.4, 0.1, 3.6, 0.8, "Chunk index: 250-word chunks,\n50-word overlap → embeddings", GREEN, fs=5.5)
    arrow(ax, 4.3, y, 4.3, 0.9)
    arrow(ax, 6.8, 0.5, 11.5, y, rad=0.18)
    label(ax, 9.6, 0.75, "unseen chunks (+ past events)")
    box(ax, 5.35, 4.2, 1.45, 0.65, "needs_reupload", RED, fs=5.5)
    arrow(ax, 6.07, y + h, 6.07, 4.2)
    save(fig, "fig_pipeline")


if __name__ == "__main__":
    architecture()
    pipeline()
