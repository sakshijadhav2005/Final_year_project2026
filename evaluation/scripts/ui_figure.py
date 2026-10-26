"""Compose the Playwright screenshots into the paper's UI figure (2 x 2 panels).

    python evaluation/scripts/ui_figure.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

import harness  # noqa: E402

SHOTS = harness.EVAL / "figures" / "screenshots"
PANELS = [
    ("05_upload_form", "(a) Upload: formats, languages, consent"),
    ("06_pipeline_live_2", "(b) Live pipeline view (SSE)"),
    ("07_job_complete", "(c) Finished job: guardrail alert, review actions"),
    ("08_studio_linkedin", "(d) Content Studio: LinkedIn draft"),
]

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                     "font.size": 7, "pdf.fonttype": 42, "savefig.bbox": "tight"})
fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.6))
for ax, (name, caption) in zip(axes.flat, PANELS):
    img = mpimg.imread(SHOTS / f"{name}.png")
    ax.imshow(img)
    ax.set_title(caption, fontsize=7, pad=3)
    ax.axis("off")
fig.subplots_adjust(wspace=0.04, hspace=0.12)
fig.savefig(harness.EVAL / "figures" / "fig_ui.pdf", dpi=200)
fig.savefig(harness.EVAL / "figures" / "fig_ui.png", dpi=200)
