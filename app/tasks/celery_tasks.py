import time
import uuid
import logging
from typing import Dict, Any
from pathlib import Path
from celery import Celery

from app.config import settings
from app.services.whisper_service import whisper_service
from app.services.nlp_service import nlp_service
from app.services.tts_service import tts_service
from app.services.braille_service import braille_service

logger = logging.getLogger(__name__)

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

def create_lecture_record(lecture_id: str, title: str, filename: str) -> Dict[str, Any]:
    record = {
        "id": lecture_id,
        "title": title,
        "filename": filename,
        "status": "queued",
        "progress": 0,
        "current_stage": "Upload Completed",
        "stages": [
            {"name": "Upload", "status": "completed"},
            {"name": "Transcription", "status": "pending"},
            {"name": "AI Processing", "status": "pending"},
            {"name": "Accessibility Conversion", "status": "pending"},
            {"name": "Completed", "status": "pending"}
        ],
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

def process_lecture_pipeline_core(lecture_id: str, file_path_str: str, lecture_title: str) -> Dict[str, Any]:
    """
    Executes the 4-stage accessibility processing pipeline.
    """
    logger.info(f"Pipeline started for lecture {lecture_id}: {lecture_title}")
    
    # Stage 1: Transcription
    update_lecture_stage(lecture_id, 1, "Transcribing Audio with Whisper...", 25)
    time.sleep(1.0)  # Smooth simulation pause for UI feedback
    
    transcript_res = whisper_service.transcribe(file_path_str, lecture_title)
    
    # Stage 2: AI Processing (Simplification & Summary)
    update_lecture_stage(lecture_id, 2, "Generating AI Simplifications & Notes...", 55)
    time.sleep(1.0)
    
    nlp_res = nlp_service.process_transcript(transcript_res["full_text"], lecture_title)
    
    # Stage 3: Accessibility Conversions (TTS Audio & Braille BRF)
    update_lecture_stage(lecture_id, 3, "Synthesizing MP3 Audio & Braille BRF...", 85)
    time.sleep(1.0)
    
    # Synthesize Audio
    mp3_filename = f"{lecture_id}_summary.mp3"
    mp3_path = settings.OUTPUT_DIR / mp3_filename
    combined_audio_text = f"Lecture Summary for {lecture_title}. " + nlp_res.get("short_summary", "") + " " + nlp_res.get("easy_explanation", "")
    tts_service.generate_mp3(combined_audio_text, mp3_path)
    
    # Convert to Braille BRF
    braille_source_text = f"ACCESSLEARN AI BRAILLE SUMMARY\nTitle: {lecture_title}\n\n" + nlp_res.get("short_summary", "") + "\n\nKEY POINTS:\n" + "\n".join([f"- {kp}" for kp in nlp_res.get("key_points", [])])
    brf_text, unicode_braille = braille_service.text_to_brf(braille_source_text, grade=2)
    
    brf_filename = f"{lecture_id}.brf"
    brf_path = settings.OUTPUT_DIR / brf_filename
    with open(brf_path, "w", encoding="ascii", errors="replace") as f:
        f.write(brf_text)
        
    result_data = {
        "transcript": transcript_res,
        "simplified": {
            "simplified_content": nlp_res.get("simplified_content", ""),
            "easy_explanation": nlp_res.get("easy_explanation", ""),
            "study_notes": nlp_res.get("study_notes", [])
        },
        "summary": {
            "short_summary": nlp_res.get("short_summary", ""),
            "keywords": nlp_res.get("keywords", [])
        },
        "key_points": nlp_res.get("key_points", []),
        "audio": {
            "filename": mp3_filename,
            "url": f"/api/audio/{lecture_id}",
            "duration_str": "03:00"
        },
        "braille": {
            "filename": brf_filename,
            "url": f"/api/braille/{lecture_id}",
            "brf_text": brf_text,
            "unicode_braille": unicode_braille,
            "line_count": len(brf_text.splitlines())
        }
    }
    
    # Stage 4: Complete
    complete_lecture_record(lecture_id, result_data)
    logger.info(f"Pipeline finished successfully for lecture {lecture_id}")
    return result_data

@celery_app.task(name="process_lecture_task")
def process_lecture_task(lecture_id: str, file_path_str: str, lecture_title: str):
    """Celery async background task wrapper"""
    return process_lecture_pipeline_core(lecture_id, file_path_str, lecture_title)
