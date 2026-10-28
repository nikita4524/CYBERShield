# apps/api-gateway/routes/video_sample.py
"""Simple endpoint that runs the VideoAnalyzer on a synthetic one‑frame video.
It returns the key fields you care about: `ai_probability`, `confidence`,
`metadata[\"ensemble_mean\"]` and any flags. This is useful for quick sanity‑checks
and for the UI button we will add later.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import numpy as np, cv2, tempfile

from services.video_analyzer import VideoAnalyzer

router = APIRouter()

@router.get("/analyze/video-sample")
async def analyze_video_sample():
    """Generate a single synthetic video frame, analyse it, and return results.
    The synthetic frame mimics the deep‑fake generation logic used in the
    notebook so the model has something to score.
    """
    # ---- 1️⃣ Create a synthetic frame (same as notebook) ----
    frame_size = 128
    f = np.random.uniform(0.3, 0.7, (frame_size, frame_size, 3)).astype(np.float32)
    # add simple deep‑fake artefacts
    cy, cx = frame_size // 2, frame_size // 2
    y, x = np.ogrid[:frame_size, :frame_size]
    mask = ((y - cy) ** 2 + (x - cx) ** 2) > 40 ** 2
    f[mask] *= 0.9
    f[mask] += 0.05
    f[cy:cy + 3, :, :] += 0.1
    f = np.clip(f, 0, 1)

    # ---- 2️⃣ Write the frame to a temporary one‑frame video ----
    tmp_dir = Path(tempfile.gettempdir())
    video_path = tmp_dir / "sample_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 5, (frame_size, frame_size))
    out.write((f * 255).astype(np.uint8))
    out.release()

    # ---- 3️⃣ Run the analyzer (ensemble enabled by default) ----
    analyzer = VideoAnalyzer()
    result = analyzer.analyze(str(video_path))

    # ---- 4️⃣ Clean up the temporary file ----
    video_path.unlink(missing_ok=True)

    # ---- 5️⃣ Return the fields the UI cares about ----
    return {
        "ai_probability": result.ai_probability,
        "confidence": result.confidence,
        "ensemble_mean": result.metadata.get("ensemble_mean"),
        "flags": result.flags,
        "metadata": result.metadata,
    }
