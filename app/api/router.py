import os
import uuid
import socket
import threading
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.utils.audio_utils import AudioUtils
from app.services.quiz_service import quiz_service
from app.services.chat_service import chat_service
from app.services.video_url_service import video_url_service, AuthRequiredError, SUPPORTED_BROWSERS
from app.tasks.celery_tasks import (
    LECTURE_STORE,
    create_lecture_record,
    delete_lecture_record,
    save_lecture_store,
    process_lecture_pipeline_core,
    process_lecture_task,
    celery_app
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["AccessLearn API"])

def _is_redis_reachable(redis_url: str, timeout: float = 0.2) -> bool:
    """Fast TCP-level check so we don't hand off to Celery when no broker is listening."""
    try:
        parsed = urlparse(redis_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


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

class UploadUrlRequest(BaseModel):
    url: str
    title: Optional[str] = None
    browser: Optional[str] = None  # e.g. "chrome" - only needed if the video requires sign-in


@router.post("/upload-url")
async def upload_lecture_from_url(body: UploadUrlRequest):
    """
    Fetches a lecture's audio from a video URL (YouTube or any other site
    yt-dlp supports) instead of a direct file upload. If the video needs the
    requester to be signed in, responds 401 with auth_required so the client
    can retry with a browser to pull cookies from.
    """
    lecture_id = f"lec-{uuid.uuid4().hex[:8]}"

    try:
        result = video_url_service.fetch_audio(body.url, settings.UPLOAD_DIR, lecture_id, browser=body.browser)
    except AuthRequiredError as e:
        raise HTTPException(
            status_code=401,
            detail={"auth_required": True, "message": str(e), "supported_browsers": SUPPORTED_BROWSERS}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lecture_title = body.title.strip() if body.title and body.title.strip() else result["title"]
    saved_path = settings.UPLOAD_DIR / result["filename"]
    file_info = AudioUtils.get_file_info(saved_path)

    record = create_lecture_record(lecture_id, lecture_title, result["filename"])
    record["file_info"] = file_info
    record["source_url"] = result.get("source_url")

    return {
        "success": True,
        "message": "Video fetched successfully. Ready for processing.",
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

    # Check if Celery/Redis is actually reachable first: Celery's .delay() does
    # NOT reliably raise immediately when the broker is down (kombu retries the
    # connection in the background instead), so relying on a try/except alone
    # can silently queue a task that never runs, leaving the lecture stuck at
    # "processing" forever. A quick TCP probe makes the fallback deterministic.
    if _is_redis_reachable(settings.REDIS_URL):
        try:
            process_lecture_task.delay(lecture_id, file_path_str, lecture_title)
            mode = "celery_redis"
        except Exception:
            background_tasks.add_task(process_lecture_pipeline_core, lecture_id, file_path_str, lecture_title)
            mode = "async_thread"
    else:
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

class ChatMessageRequest(BaseModel):
    message: str


@router.get("/quiz/{lecture_id}")
async def get_quiz(lecture_id: str):
    """
    Returns (generating and caching on first call) an AI-built multiple-choice
    quiz grounded in this lecture's transcript, keywords, and key points.
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    if rec["status"] != "completed":
        raise HTTPException(status_code=400, detail="Lecture processing is not completed yet.")

    if "quiz" not in rec["data"]:
        transcript_text = (rec["data"].get("transcript") or {}).get("full_text", "")
        nlp_data = {
            "keywords": (rec["data"].get("summary") or {}).get("keywords", []),
            "key_points": rec["data"].get("key_points", [])
        }
        rec["data"]["quiz"] = quiz_service.generate_quiz(transcript_text, nlp_data, rec["title"])
        save_lecture_store()

    return {"lecture_id": lecture_id, "questions": rec["data"]["quiz"]}


@router.delete("/lectures/{lecture_id}")
async def delete_lecture(lecture_id: str):
    """
    Permanently deletes a lecture record along with its uploaded audio/video
    file and any generated MP3/Braille outputs on disk.
    """
    if lecture_id.startswith("demo-"):
        raise HTTPException(status_code=400, detail="Demo lectures cannot be deleted.")
    deleted = delete_lecture_record(lecture_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    return {"success": True, "message": "Lecture deleted.", "lecture_id": lecture_id}


@router.post("/chat/{lecture_id}")
async def post_chat_message(lecture_id: str, body: ChatMessageRequest):
    """
    AI doubt-solving endpoint. Answers a student's question strictly using
    this lecture's own content (transcript, notes, keywords, key points).
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    if rec["status"] != "completed":
        raise HTTPException(status_code=400, detail="Lecture processing is not completed yet.")

    answer = chat_service.answer_question(body.message, rec["data"], rec["title"])
    return {"lecture_id": lecture_id, "question": body.message, "answer": answer}


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
