import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import cv2

from app.services.gemini_service import gemini_service, GeminiUnavailableError

logger = logging.getLogger("accesslearn.visual")

# Sampling policy: fixed-interval keyframe extraction. A full scene-change
# detector (diffing consecutive frames to catch slide transitions precisely)
# would be more precise, but fixed-interval sampling is simple, predictable,
# and -- at these intervals -- reliably catches slide/diagram changes in
# typical lecture-paced video without the added complexity/failure modes of
# a custom change-detection heuristic. Documented as a future improvement.
MIN_FRAMES = 6
MAX_FRAMES = 16  # kept modest: all frames go into ONE batched Gemini call (see below)
MIN_INTERVAL_SECONDS = 10.0


def _format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class VisualAnalysisService:
    """
    Extracts keyframes from the uploaded video and uses Gemini's vision
    capability to describe any educational content on screen -- slides,
    diagrams, charts, code, tables, on-screen text -- so the pipeline
    captures information the speaker may never say aloud.

    All sampled frames are analyzed in a SINGLE batched Gemini call (all
    images + one prompt asking for a per-frame JSON verdict) rather than one
    call per frame. This was a deliberate fix after testing: one-call-per-
    frame hit the free-tier rate limit (HTTP 429) and model-overload errors
    (HTTP 503) repeatedly on a video with only a handful of sampled frames.
    Batching cuts N API calls down to 1 per video for this stage.
    """

    def extract_and_analyze(self, video_path: Path, output_dir: Path) -> List[Dict[str, Any]]:
        frames = self._extract_frames(video_path, output_dir)
        if not frames:
            return []
        return self._analyze_frames_batch(frames)

    def _extract_frames(self, video_path: Path, output_dir: Path) -> List[Dict[str, Any]]:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning(f"Could not open video for frame extraction: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = total_frames / fps if fps else 0.0

        if duration <= 0:
            cap.release()
            return []

        interval = max(MIN_INTERVAL_SECONDS, duration / MAX_FRAMES)
        sample_times = []
        t = interval / 2  # skip the very first instant (often a blank/intro frame)
        while t < duration and len(sample_times) < MAX_FRAMES:
            sample_times.append(t)
            t += interval
        if len(sample_times) < MIN_FRAMES and duration > 0:
            n = min(MIN_FRAMES, max(1, int(duration)))
            sample_times = [duration * (i + 1) / (n + 1) for i in range(n)]

        output_dir.mkdir(parents=True, exist_ok=True)
        frames = []

        for idx, sec in enumerate(sample_times):
            cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
            success, frame = cap.read()
            if not success:
                continue
            frame_path = output_dir / f"frame_{idx:03d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            frames.append({"index": idx, "timestamp_seconds": round(sec, 1), "timestamp_str": _format_timestamp(sec), "frame_path": frame_path})

        cap.release()
        return frames

    def _analyze_frames_batch(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        image_bytes_list = []
        for f in frames:
            with open(f["frame_path"], "rb") as fh:
                image_bytes_list.append(fh.read())

        frame_list_desc = "\n".join(f"Frame {f['index']}: timestamp {f['timestamp_str']}" for f in frames)
        prompt = (
            "You are shown a sequence of frames sampled from an educational lecture video, "
            "in chronological order, with their timestamps below:\n\n"
            f"{frame_list_desc}\n\n"
            "For each frame, if it shows a slide, diagram, chart, code, table, or important "
            "on-screen text, describe exactly what it shows (transcribe key text/labels verbatim "
            "where legible). If a frame just shows a person talking with no meaningful on-screen "
            "content, mark it as not notable. "
            "Return ONLY valid JSON (no markdown fences) with this exact structure:\n"
            '{"frames": [{"index": 0, "notable": true, "description": "..."}, '
            '{"index": 1, "notable": false, "description": null}]}'
        )

        try:
            data = gemini_service.generate_json(prompt, images=image_bytes_list)
        except GeminiUnavailableError as e:
            logger.warning(f"Batched visual analysis failed: {e}")
            return []

        by_index = {item.get("index"): item for item in data.get("frames", [])}
        results = []
        for f in frames:
            verdict = by_index.get(f["index"])
            if verdict and verdict.get("notable") and verdict.get("description"):
                results.append({
                    "timestamp_seconds": f["timestamp_seconds"],
                    "timestamp_str": f["timestamp_str"],
                    "description": verdict["description"],
                    "frame_path": str(f["frame_path"]),
                })
            else:
                Path(f["frame_path"]).unlink(missing_ok=True)

        logger.info(f"Visual analysis: {len(results)}/{len(frames)} sampled frames had notable content.")
        return results


visual_service = VisualAnalysisService()
