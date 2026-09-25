import json
import time
import uuid
import logging
from typing import Dict, Any, List
from pathlib import Path
from celery import Celery

from app.config import settings
from app.services.whisper_service import whisper_service
from app.services.nlp_service import nlp_service  # retained, no longer used by the pipeline -- see notes_service.py
from app.services.tts_service import tts_service
from app.services.braille_service import braille_service, BrailleNotSupportedError
from app.services.image_service import image_service  # retained (Wikimedia fallback), superseded by real video-frame visuals
from app.services.visual_service import visual_service
from app.services.video_structure_service import video_structure_service
from app.services.notes_service import notes_service
from app.services.content_generation_service import content_generation_service
from app.services.quality_service import quality_service

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

# Initialize Celery App
celery_app = Celery(
    "accesslearn_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# In-memory lecture store for status tracking and instant status polling
LECTURE_STORE: Dict[str, Dict[str, Any]] = {}

STAGE_NAMES = [
    "Upload",
    "Transcription",
    "Visual Analysis",
    "Understanding Video",
    "Simplified Notes",
    "Summary & Key Points",
    "Accessibility Conversion",
    "Completed",
]


def create_lecture_record(lecture_id: str, title: str, filename: str) -> Dict[str, Any]:
    record = {
        "id": lecture_id,
        "title": title,
        "filename": filename,
        "status": "queued",
        "progress": 0,
        "current_stage": "Upload Completed",
        "stages": [{"name": name, "status": "pending" if i > 0 else "completed"} for i, name in enumerate(STAGE_NAMES)],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "error": None,
        "data": {}
    }
    LECTURE_STORE[lecture_id] = record
    return record

def update_lecture_stage(lecture_id: str, stage_idx: int, stage_name: str, progress: int):
    if lecture_id in LECTURE_STORE:
        rec = LECTURE_STORE[lecture_id]
        rec["progress"] = progress
        rec["current_stage"] = stage_name
        for idx, stg in enumerate(rec["stages"]):
            if idx < stage_idx:
                stg["status"] = "completed"
            elif idx == stage_idx:
                stg["status"] = "in_progress"
            else:
                stg["status"] = "pending"

def complete_lecture_record(lecture_id: str, data: Dict[str, Any]):
    if lecture_id in LECTURE_STORE:
        rec = LECTURE_STORE[lecture_id]
        rec["progress"] = 100
        rec["status"] = "completed"
        rec["current_stage"] = "Completed"
        for stg in rec["stages"]:
            stg["status"] = "completed"
        rec["data"] = data


def _notes_to_plain_text(notes_data: dict) -> str:
    """Flattens structured notes JSON into plain narratable/brailleable text (headings + prose)."""
    parts = []
    for section in notes_data.get("sections", []):
        parts.append(section.get("heading", ""))
        parts.append(section.get("content", ""))
    return "\n\n".join(p for p in parts if p)


def _content_to_plain_text(content: dict, source: str) -> str:
    if source == "notes":
        return _notes_to_plain_text(content)
    if source == "summary":
        return f"{content.get('shortSummary', '')}\n\n{content.get('detailedSummary', '')}"
    if source == "key_points":
        return "\n".join(f"{i + 1}. {p}" for i, p in enumerate(content.get("keyPoints", [])))
    raise ValueError(f"Unknown source: {source}")


def process_lecture_pipeline_core(lecture_id: str, file_path_str: str, lecture_title: str) -> Dict[str, Any]:
    """
    Thin wrapper around _run_pipeline_stages: catches any unexpected
    exception and marks the lecture FAILED with a clear message, instead of
    leaving it stuck at "processing" forever with no visible error. Every
    individual Gemini-backed stage already has its own internal fallback
    (see notes_service.py etc.), so this only fires on genuine bugs/outages.
    """
    try:
        return _run_pipeline_stages(lecture_id, file_path_str, lecture_title)
    except Exception as e:
        logger.error(f"Pipeline failed for lecture {lecture_id}: {e}", exc_info=True)
        if lecture_id in LECTURE_STORE:
            rec = LECTURE_STORE[lecture_id]
            rec["status"] = "failed"
            rec["error"] = str(e)
            rec["current_stage"] = "Failed"
        raise


def _run_pipeline_stages(lecture_id: str, file_path_str: str, lecture_title: str) -> Dict[str, Any]:
    """
    The AI Video Learning Assistant pipeline: understands the COMPLETE video
    (audio + on-screen visuals), builds a structured, timestamped
    representation of it, and generates every downstream artifact
    (Simplified Notes with flowcharts and real visual references, Summary,
    Key Points) strictly grounded in that structure -- never inventing
    content. English audio/Braille are generated eagerly; Hindi/Kannada
    translations (and their audio) are generated on demand and cached (see
    the /api/notes, /api/summary, /api/audio, /api/braille routes) rather
    than reprocessing the video per language.
    """
    logger.info(f"Pipeline started for lecture {lecture_id}: {lecture_title}")
    file_path = Path(file_path_str)
    is_video = file_path.suffix.lower() in VIDEO_EXTENSIONS

    # --- Stage 1: Transcription (real Whisper, see whisper_service.py) ---
    update_lecture_stage(lecture_id, 1, "Transcribing Audio with Whisper...", 15)
    transcript_res = whisper_service.transcribe(file_path_str, lecture_title)
    full_text = transcript_res["full_text"]
    if not full_text.strip():
        raise RuntimeError("Transcription produced no text (silent or unsupported audio).")
    duration = transcript_res.get("duration", 0.0) or 0.0
    language = transcript_res.get("language", "en") or "en"

    # Segments come back as {timestamp, start_seconds, end_seconds, text};
    # the structure service expects {start, end, text}.
    structure_segments = [
        {"start": s["start_seconds"], "end": s["end_seconds"], "text": s["text"]}
        for s in transcript_res.get("segments", [])
    ]

    # --- Stage 2: Visual analysis of on-screen slides/diagrams/code ---
    visual_observations: List[Dict[str, Any]] = []
    if is_video:
        update_lecture_stage(lecture_id, 2, "Analyzing on-screen slides, diagrams, and code...", 30)
        try:
            frames_dir = settings.OUTPUT_DIR / "frames" / lecture_id
            visual_observations = visual_service.extract_and_analyze(file_path, frames_dir)
        except Exception as e:
            logger.error(f"Visual analysis failed for {lecture_id} (continuing audio-only): {e}")

    # --- Stage 3: Structured video representation (transcript + visuals) ---
    update_lecture_stage(lecture_id, 3, "Understanding video structure and concepts...", 45)
    structure = video_structure_service.build_structure(structure_segments, visual_observations, duration, language=language)
    analysis_path = settings.OUTPUT_DIR / "analysis" / f"{lecture_id}.json"
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.write_text(json.dumps(structure, indent=2), encoding="utf-8")

    # --- Stage 4: Simplified Notes (primary learning artifact, English) ---
    update_lecture_stage(lecture_id, 4, "Writing A-Z simplified notes with flowcharts and visuals...", 60)
    notes_data = notes_service.generate_notes(structure, visual_observations)
    notes_path = settings.OUTPUT_DIR / "notes" / f"{lecture_id}_en.json"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(json.dumps(notes_data, indent=2), encoding="utf-8")

    # --- Stage 5: Summary + Key Points (English) ---
    update_lecture_stage(lecture_id, 5, "Generating summary and key points...", 72)
    summary_data = content_generation_service.generate_summary(structure)
    keypoints_data = content_generation_service.generate_key_points(structure)
    summary_path = settings.OUTPUT_DIR / "summaries" / f"{lecture_id}_en.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    kp_path = settings.OUTPUT_DIR / "keypoints" / f"{lecture_id}_en.json"
    kp_path.parent.mkdir(parents=True, exist_ok=True)
    kp_path.write_text(json.dumps(keypoints_data, indent=2), encoding="utf-8")

    # --- Stage 6: Accessibility conversions (English audio + Braille) ---
    update_lecture_stage(lecture_id, 6, "Synthesizing MP3 audio & Braille BRF...", 88)
    narration_text = _notes_to_plain_text(notes_data)

    mp3_filename = f"{lecture_id}_notes_en.mp3"
    mp3_path = settings.OUTPUT_DIR / mp3_filename
    tts_service.generate_mp3(narration_text, mp3_path, lang="en")

    brf_text, unicode_braille = braille_service.text_to_brf(narration_text, grade=2, language="en")
    brf_filename = f"{lecture_id}_notes_en.brf"
    brf_path = settings.OUTPUT_DIR / brf_filename
    with open(brf_path, "w", encoding="ascii", errors="replace") as f:
        f.write(brf_text)

    # --- Quality validation (best-effort, logged only -- never blocks completion) ---
    try:
        quality_service.validate_notes(structure, notes_data)
    except Exception as e:
        logger.warning(f"Quality validation could not complete for {lecture_id}: {e}")

    result_data = {
        "video": {"duration": duration, "language": language, "is_video": is_video},
        "transcript": transcript_res,
        "structure": structure,
        "simplified": notes_data,
        "summary": summary_data,
        "key_points": keypoints_data.get("keyPoints", []),
        "audio": {
            "filename": mp3_filename,
            "url": f"/api/audio/{lecture_id}",
            "duration_str": "",
        },
        "braille": {
            "filename": brf_filename,
            "url": f"/api/braille/{lecture_id}",
            "brf_text": brf_text,
            "unicode_braille": unicode_braille,
            "line_count": len(brf_text.splitlines())
        }
    }

    complete_lecture_record(lecture_id, result_data)
    logger.info(f"Pipeline finished successfully for lecture {lecture_id}")
    return result_data

@celery_app.task(name="process_lecture_task")
def process_lecture_task(lecture_id: str, file_path_str: str, lecture_title: str):
    """Celery async background task wrapper"""
    return process_lecture_pipeline_core(lecture_id, file_path_str, lecture_title)
