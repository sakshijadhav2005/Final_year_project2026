"""Extract the TED-LIUM 3 long-form talks to WAV + reference text and write a manifest.

Source: distil-whisper/tedlium-long-form (Hugging Face), built from TED-LIUM release 3
(Hernandez et al., 2018; CC BY-NC-ND 3.0). 19 full talks: 8 validation + 11 test.
Audio is kept out of git (evaluation/.gitignore).

    python evaluation/scripts/prepare_dataset.py
"""

import csv
import io
import json
from pathlib import Path

import pyarrow.parquet as pq
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
AUDIO = ROOT / "data" / "audio"
REFS = ROOT / "data" / "references"


def main() -> None:
    AUDIO.mkdir(parents=True, exist_ok=True)
    REFS.mkdir(parents=True, exist_ok=True)
    rows = []
    for split in ("validation", "test"):
        table = pq.read_table(RAW / f"{split}.parquet").to_pylist()
        for item in table:
            talk = item["speaker_id"]
            data, sr = sf.read(io.BytesIO(item["audio"]["bytes"]))
            wav = AUDIO / f"{talk}.wav"
            sf.write(wav, data, sr, subtype="PCM_16")
            ref = " ".join(item["text"].split())
            (REFS / f"{talk}.txt").write_text(ref, encoding="utf-8")
            rows.append(
                {
                    "talk_id": talk,
                    "split": split,
                    "duration_sec": round(len(data) / sr, 2),
                    "sample_rate": sr,
                    "ref_words": len(ref.split()),
                    "wav_bytes": wav.stat().st_size,
                }
            )
            print(f"{split:10s} {talk:28s} {rows[-1]['duration_sec']:8.1f}s {rows[-1]['ref_words']:6d} words")

    with (ROOT / "data" / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (ROOT / "data" / "PROVENANCE.json").write_text(
        json.dumps(
            {
                "dataset": "TED-LIUM release 3, long-form merge (distil-whisper/tedlium-long-form)",
                "url": "https://huggingface.co/datasets/distil-whisper/tedlium-long-form",
                "original": "https://www.openslr.org/51/",
                "license": "CC BY-NC-ND 3.0 (academic, non-commercial evaluation; not redistributed)",
                "references": "Human transcripts distributed with TED-LIUM 3 (segments concatenated per talk)",
                "talks": len(rows),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
