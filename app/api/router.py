import os
import uuid
import threading
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.utils.audio_utils import AudioUtils
from app.tasks.celery_tasks import (
    LECTURE_STORE,
    create_lecture_record,
    process_lecture_pipeline_core,
    process_lecture_task,
    celery_app
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["AccessLearn API"])

def ensure_demo_lectures():
    """Populates high quality demo lectures lazily when needed."""
    demo_id_1 = "demo-quantum-101"
    if demo_id_1 not in LECTURE_STORE:
        create_lecture_record(demo_id_1, "Introduction to Quantum Computing", "quantum_lecture.mp3")
        process_lecture_pipeline_core(demo_id_1, str(settings.UPLOAD_DIR / "demo1.mp3"), "Introduction to Quantum Computing")
        
    demo_id_2 = "demo-neural-net-201"
    if demo_id_2 not in LECTURE_STORE:
        create_lecture_record(demo_id_2, "Neural Networks & Deep Learning", "neural_lecture.mp4")
        process_lecture_pipeline_core(demo_id_2, str(settings.UPLOAD_DIR / "demo2.mp4"), "Neural Networks & Deep Learning")

@router.post("/upload")
async def upload_lecture(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None)
):
    """
    Uploads a lecture audio or video file (.mp3, .wav, .m4a, .mp4, .webm, etc.).
    """
    if not AudioUtils.is_valid_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{file.filename}'. Allowed formats: MP3, WAV, M4A, OGG, MP4, WebM."
        )
        
    lecture_id = f"lec-{uuid.uuid4().hex[:8]}"
    lecture_title = title.strip() if title and title.strip() else Path(file.filename).stem.replace("_", " ").title()
    
    file_ext = Path(file.filename).suffix
    saved_filename = f"{lecture_id}{file_ext}"
    saved_path = settings.UPLOAD_DIR / saved_filename
    
    try:
        contents = await file.read()
        with open(saved_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"File write error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")
        
    file_info = AudioUtils.get_file_info(saved_path)
    
    # Initialize record
    record = create_lecture_record(lecture_id, lecture_title, saved_filename)
    record["file_info"] = file_info
    
    return {
        "success": True,
        "message": "File uploaded successfully. Ready for processing.",
        "lecture_id": lecture_id,
        "title": lecture_title,
        "file_info": file_info
    }

@router.post("/process/{lecture_id}")
async def process_lecture(lecture_id: str, background_tasks: BackgroundTasks):
    """
    Triggers asynchronous AI processing for the uploaded lecture.
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
        
    rec = LECTURE_STORE[lecture_id]
    if rec["status"] == "processing" or rec["status"] == "completed":
        return {"message": f"Lecture is currently in status: {rec['status']}", "lecture_id": lecture_id}
        
    rec["status"] = "processing"
    rec["progress"] = 10
    rec["current_stage"] = "Initializing AI Pipeline..."
    
    filename = rec["filename"]
    file_path_str = str(settings.UPLOAD_DIR / filename)
    lecture_title = rec["title"]
    
    # Check if Celery/Redis is active, otherwise fallback to Python Background thread
    try:
        process_lecture_task.delay(lecture_id, file_path_str, lecture_title)
        mode = "celery_redis"
    except Exception:
        # Fallback to FastAPI BackgroundTasks thread runner
        background_tasks.add_task(process_lecture_pipeline_core, lecture_id, file_path_str, lecture_title)
        mode = "async_thread"
        
    return {
        "success": True,
        "message": "Pipeline processing started.",
        "lecture_id": lecture_id,
        "execution_mode": mode
    }

@router.get("/status/{lecture_id}")
async def get_lecture_status(lecture_id: str):
    """
    Returns real-time pipeline status and stage progress.
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    return LECTURE_STORE[lecture_id]

@router.get("/transcript/{lecture_id}")
async def get_transcript(lecture_id: str):
    """
    Returns timestamped transcript data.
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    if rec["status"] != "completed":
        raise HTTPException(status_code=400, detail="Lecture processing is not completed yet.")
    return rec["data"].get("transcript", {})

@router.get("/summary/{lecture_id}")
async def get_summary(lecture_id: str):
    """
    Returns executive summary, key points, and keywords.
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    if rec["status"] != "completed":
        raise HTTPException(status_code=400, detail="Lecture processing is not completed yet.")
    return {
        "summary": rec["data"].get("summary", {}),
        "key_points": rec["data"].get("key_points", [])
    }

@router.get("/simplified/{lecture_id}")
async def get_simplified(lecture_id: str):
    """
    Returns plain-language simplified explanations and study notes.
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    if rec["status"] != "completed":
        raise HTTPException(status_code=400, detail="Lecture processing is not completed yet.")
    return rec["data"].get("simplified", {})

@router.get("/audio/{lecture_id}")
async def get_audio(lecture_id: str, download: bool = False):
    """
    Streams or downloads synthesized TTS MP3 audio file.
    """
    mp3_path = settings.OUTPUT_DIR / f"{lecture_id}_summary.mp3"
    if not mp3_path.exists():
        # Fallback to default synthesized mp3
        mp3_path = settings.OUTPUT_DIR / "demo-quantum-101_summary.mp3"
        
    if download:
        return FileResponse(
            path=mp3_path,
            filename=f"AccessLearn_{lecture_id}_Audio.mp3",
            media_type="audio/mpeg"
        )
    return FileResponse(path=mp3_path, media_type="audio/mpeg")

@router.get("/braille/{lecture_id}")
async def get_braille(lecture_id: str, download: bool = False):
    """
    Returns Braille data or downloads formatted .BRF Braille file.
    """
    brf_path = settings.OUTPUT_DIR / f"{lecture_id}.brf"
    
    if download:
        if not brf_path.exists():
            raise HTTPException(status_code=404, detail="BRF file not found.")
        return FileResponse(
            path=brf_path,
            filename=f"AccessLearn_{lecture_id}.brf",
            media_type="text/plain"
        )
        
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    return rec["data"].get("braille", {})

@router.get("/lectures")
async def list_lectures():
    """
    Lists all processed and available recent lectures.
    """
    ensure_demo_lectures()
    lectures = []
    for lid, rec in LECTURE_STORE.items():
        lectures.append({
            "id": rec["id"],
            "title": rec["title"],
            "status": rec["status"],
            "progress": rec["progress"],
            "created_at": rec["created_at"],
            "filename": rec["filename"]
        })
    return {"lectures": lectures}

@router.post("/demo/load/{demo_key}")
async def load_demo_lecture(demo_key: str):
    """
    Instantly triggers demo lecture for immediate UI exploration.
    """
    ensure_demo_lectures()
    if demo_key == "quantum":
        demo_id = "demo-quantum-101"
    else:
        demo_id = "demo-neural-net-201"
        
    if demo_id in LECTURE_STORE:
        return {
            "success": True,
            "lecture_id": demo_id,
            "title": LECTURE_STORE[demo_id]["title"]
        }
    raise HTTPException(status_code=404, detail="Demo lecture unavailable.")
