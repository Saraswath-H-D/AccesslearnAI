import os
import json
import uuid
import threading
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from app.config import settings
from app.utils.audio_utils import AudioUtils
from app.services.youtube_service import youtube_service
from app.services.pdf_service import notes_pdf_service
from app.services.translation_service import translation_service, SUPPORTED_LANGUAGES
from app.services.tts_service import tts_service
from app.services.braille_service import braille_service, BrailleNotSupportedError
from app.tasks.celery_tasks import (
    LECTURE_STORE,
    create_lecture_record,
    process_lecture_pipeline_core,
    process_lecture_task,
    celery_app,
    _content_to_plain_text,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["AccessLearn API"])

_SOURCE_KEY = {"notes": "simplified", "summary": "summary", "key_points": "key_points"}


def _get_completed_lecture(lecture_id: str) -> dict:
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    if rec["status"] != "completed":
        raise HTTPException(status_code=400, detail="Lecture processing is not completed yet.")
    return rec


def _english_content_for_source(rec: dict, source: str) -> dict:
    data = rec["data"]
    if source == "notes":
        return data.get("simplified", {})
    if source == "summary":
        return data.get("summary", {})
    if source == "key_points":
        return {"keyPoints": data.get("key_points", [])}
    raise HTTPException(status_code=400, detail=f"Unknown source '{source}'.")


def _get_translated_content(lecture_id: str, source: str, lang: str) -> dict:
    """
    Returns the requested content (notes/summary/key_points) in the
    requested language, translating from the English canonical version and
    caching the result on first request (Section 40 of the brief: translate
    from the structured source, don't reprocess the video per language).
    """
    rec = _get_completed_lecture(lecture_id)
    english_content = _english_content_for_source(rec, source)

    if lang == "en":
        return english_content
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'. Supported: {list(SUPPORTED_LANGUAGES)}")

    cache_path = settings.OUTPUT_DIR / "translations" / lang / source / f"{lecture_id}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    try:
        translated = translation_service.translate_content(english_content, lang)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Translation to {lang} failed: {e}")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(translated, ensure_ascii=False, indent=2), encoding="utf-8")
    return translated


class YouTubeUploadRequest(BaseModel):
    url: str
    title: Optional[str] = None


def _is_broker_available(redis_url: str, timeout: float = 0.3) -> bool:
    """
    Fast, short-timeout reachability probe for the Celery/Redis broker.

    Celery's own connection retry policy on a real `.delay()` call can block
    for a long time (many seconds per retry, up to ~20 retries) when Redis is
    unreachable -- and since that call is made synchronously from an async
    request handler, it freezes the entire server, not just one request.
    Checking reachability up front keeps the "instant fallback to a
    background thread" behavior actually instant.
    """
    try:
        import redis
        client = redis.Redis.from_url(redis_url, socket_connect_timeout=timeout, socket_timeout=timeout)
        return client.ping()
    except Exception:
        return False

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
        
    # Accurate integrity scan: reject empty/truncated/corrupted uploads
    # before they ever reach the AI pipeline.
    scan = AudioUtils.scan_media_file(saved_path)
    if not scan["valid"]:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Uploaded file failed the accuracy scan: {scan['reason']}")

    file_info = AudioUtils.get_file_info(saved_path)
    file_info["scan"] = scan

    # Initialize record
    record = create_lecture_record(lecture_id, lecture_title, saved_filename)
    record["file_info"] = file_info

    return {
        "success": True,
        "message": "File uploaded successfully and verified. Ready for processing.",
        "lecture_id": lecture_id,
        "title": lecture_title,
        "file_info": file_info
    }

@router.post("/upload/youtube")
async def upload_youtube_lecture(payload: YouTubeUploadRequest):
    """
    Ingests an educational YouTube video by URL: validates the link,
    downloads its audio track, runs the same accuracy scan as a direct file
    upload, and registers it for the standard AI accessibility pipeline.
    """
    url = (payload.url or "").strip()
    if not url or not youtube_service.is_valid_youtube_url(url):
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid YouTube video URL (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...)."
        )

    lecture_id = f"lec-{uuid.uuid4().hex[:8]}"

    try:
        result = youtube_service.download_audio(url, lecture_id, settings.UPLOAD_DIR)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"YouTube download failed for {url}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to download audio from YouTube: {e}")

    downloaded_path: Path = result["file_path"]

    if not AudioUtils.is_valid_file(downloaded_path.name):
        downloaded_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Downloaded YouTube audio format '{downloaded_path.suffix}' is unsupported."
        )

    # Same accuracy scan as direct uploads, so a broken/partial download
    # never silently enters the pipeline.
    scan = AudioUtils.scan_media_file(downloaded_path)
    if not scan["valid"]:
        downloaded_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Downloaded YouTube audio failed the accuracy scan: {scan['reason']}")

    lecture_title = payload.title.strip() if payload.title and payload.title.strip() else result["title"]
    saved_filename = downloaded_path.name

    file_info = AudioUtils.get_file_info(downloaded_path)
    file_info["scan"] = scan
    file_info["source"] = "youtube"
    file_info["source_url"] = result["webpage_url"]

    record = create_lecture_record(lecture_id, lecture_title, saved_filename)
    record["file_info"] = file_info
    record["source"] = "youtube"
    record["source_url"] = result["webpage_url"]

    return {
        "success": True,
        "message": "YouTube audio downloaded and verified. Ready for processing.",
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
    
    # Check if Celery/Redis is active, otherwise fallback to Python Background thread.
    # The reachability check is done up front (fast, short-timeout) rather than
    # relying on .delay() to raise, since a real Celery call retries against an
    # unreachable broker for a long time and would otherwise block the server.
    if _is_broker_available(settings.REDIS_URL):
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
    Returns the complete timestamped transcript (always English/original
    language -- the verbatim ASR output, not translated -- see the
    Transcript-vs-Notes distinction in the project brief). The frontend
    uses `segments` for search and click-to-seek.
    """
    rec = _get_completed_lecture(lecture_id)
    return rec["data"].get("transcript", {})

@router.get("/structure/{lecture_id}")
async def get_structure(lecture_id: str):
    """The structured video representation (sections, concepts, timestamps)."""
    rec = _get_completed_lecture(lecture_id)
    return rec["data"].get("structure", {})

@router.get("/video/{lecture_id}")
async def get_video(lecture_id: str):
    """Streams the originally uploaded audio/video file for the player (Range-request seekable)."""
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    video_path = settings.UPLOAD_DIR / rec["filename"]
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source file not found.")
    ext = video_path.suffix.lower()
    media_type = "video/mp4" if ext in (".mp4", ".mov", ".mkv", ".webm", ".avi") else "audio/mpeg"
    return FileResponse(path=video_path, media_type=media_type)

@router.get("/frame/{lecture_id}/{filename}")
async def get_frame(lecture_id: str, filename: str):
    """Serves a real extracted video frame referenced by Simplified Notes as a relevant visual."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    frame_path = settings.OUTPUT_DIR / "frames" / lecture_id / filename
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Frame not found.")
    return FileResponse(path=frame_path, media_type="image/jpeg")

@router.get("/summary/{lecture_id}")
async def get_summary(lecture_id: str, lang: str = Query("en")):
    """
    Returns the Summary (short + detailed) and Key Points, in the requested
    language. Translates from the English canonical version and caches the
    result on first non-English request.
    """
    summary = _get_translated_content(lecture_id, "summary", lang)
    key_points = _get_translated_content(lecture_id, "key_points", lang)
    return {"summary": summary, "key_points": key_points.get("keyPoints", []), "language": lang}

@router.get("/simplified/{lecture_id}")
async def get_simplified(lecture_id: str, lang: str = Query("en")):
    """
    Returns the Simplified Notes -- dynamic per-video sections, each with an
    optional Mermaid flowchart (only where the video describes a real
    process) and an optional reference to a real extracted video frame --
    in the requested language. Translates + caches on first non-English request.
    """
    content = _get_translated_content(lecture_id, "notes", lang)
    # Rewrite local frame paths into servable API URLs
    for section in content.get("sections", []):
        if section.get("visualFramePath"):
            filename = Path(section["visualFramePath"]).name
            section["visualUrl"] = f"/api/frame/{lecture_id}/{filename}"
    return {**content, "language": lang}

@router.get("/notes/image/{lecture_id}/{filename}")
async def get_notes_image(lecture_id: str, filename: str):
    """
    Serves a related illustrative image attached to a lecture's simplified
    notes (fetched from Wikimedia Commons, or a generated placeholder).
    Retained for the image_service.py fallback path; real video-extracted
    visuals are served via /api/frame instead (preferred -- see Section 12).
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid image filename.")
    image_path = settings.OUTPUT_DIR / "images" / lecture_id / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path=image_path, media_type="image/jpeg")

@router.get("/notes/pdf/{lecture_id}")
async def download_notes_pdf(lecture_id: str):
    """
    Generates and downloads a PDF of the lecture's simplified study notes,
    including related illustrative images, for offline studying.
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")
    rec = LECTURE_STORE[lecture_id]
    if rec["status"] != "completed":
        raise HTTPException(status_code=400, detail="Lecture processing is not completed yet.")

    data = rec["data"]
    try:
        pdf_bytes = notes_pdf_service.build_pdf(
            lecture_title=rec["title"],
            simplified=data.get("simplified", {}),
            summary=data.get("summary", {}),
            key_points=data.get("key_points", [])
        )
    except Exception as e:
        logger.error(f"PDF generation failed for lecture {lecture_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF notes.")

    filename = f"AccessLearn_{lecture_id}_Notes.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/audio/{lecture_id}")
async def get_audio(
    lecture_id: str,
    download: bool = False,
    lang: str = Query("en"),
    source: str = Query("notes"),
):
    """
    Streams or downloads MP3 narration of the selected content
    (notes/summary/key_points) in the selected language (English/Hindi/
    Kannada voice via gTTS -- the SPOKEN language matches the selection, not
    just translated UI text). Generated eagerly in English by the pipeline;
    other language/source combinations are generated on first request and
    cached to disk.
    """
    if source not in _SOURCE_KEY:
        raise HTTPException(status_code=400, detail=f"Unknown source '{source}'.")
    if lang != "en" and lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'.")

    mp3_path = settings.OUTPUT_DIR / f"{lecture_id}_{source}_{lang}.mp3"
    if not mp3_path.exists():
        content = _get_translated_content(lecture_id, source, lang)
        text = _content_to_plain_text(content, source)
        try:
            tts_service.generate_mp3(text, mp3_path, lang=lang)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Audio generation failed: {e}")

    if download:
        return FileResponse(
            path=mp3_path,
            filename=f"AccessLearn_{lecture_id}_{source}_{lang}.mp3",
            media_type="audio/mpeg"
        )
    return FileResponse(path=mp3_path, media_type="audio/mpeg")

@router.get("/braille/{lecture_id}")
async def get_braille(
    lecture_id: str,
    download: bool = False,
    lang: str = Query("en"),
    source: str = Query("notes"),
):
    """
    Returns/downloads a .brf Braille file of the selected content in the
    selected language. Hindi/Kannada return a clear 422 instead of
    generating incorrect Braille -- see braille_service.py.
    """
    if source not in _SOURCE_KEY:
        raise HTTPException(status_code=400, detail=f"Unknown source '{source}'.")
    if lang != "en" and lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'.")

    brf_path = settings.OUTPUT_DIR / f"{lecture_id}_{source}_{lang}.brf"
    if not brf_path.exists():
        content = _get_translated_content(lecture_id, source, lang)
        text = _content_to_plain_text(content, source)
        try:
            brf_text, unicode_braille = braille_service.text_to_brf(text, grade=2, language=lang)
        except BrailleNotSupportedError as e:
            raise HTTPException(status_code=422, detail=str(e))
        brf_path.parent.mkdir(parents=True, exist_ok=True)
        brf_path.write_text(brf_text, encoding="ascii", errors="replace")

    if download:
        return FileResponse(
            path=brf_path,
            filename=f"AccessLearn_{lecture_id}_{source}_{lang}.brf",
            media_type="text/plain"
        )
    return FileResponse(path=brf_path, media_type="text/plain")

@router.get("/lectures")
async def list_lectures():
    """
    Lists all processed and available recent lectures.
    """
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

@router.delete("/lectures/{lecture_id}")
async def delete_lecture(lecture_id: str):
    """
    Permanently deletes an uploaded/processed lecture: removes its record
    and every generated file (source upload, TTS audio, .brf braille file,
    related notes images). Lectures are stored by default until explicitly
    deleted here.
    """
    if lecture_id not in LECTURE_STORE:
        raise HTTPException(status_code=404, detail="Lecture ID not found.")

    rec = LECTURE_STORE[lecture_id]
    removed_files = []

    # Source upload (uploaded file or downloaded YouTube audio)
    filename = rec.get("filename")
    if filename:
        upload_path = settings.UPLOAD_DIR / filename
        if upload_path.exists():
            try:
                upload_path.unlink()
                removed_files.append(str(upload_path))
            except Exception as e:
                logger.warning(f"Could not delete upload file {upload_path}: {e}")

    # Generated outputs: TTS audio, BRF braille file, related notes images
    candidate_paths = [
        settings.OUTPUT_DIR / f"{lecture_id}_summary.mp3",
        settings.OUTPUT_DIR / f"{lecture_id}.brf",
    ]
    for path in candidate_paths:
        if path.exists():
            try:
                path.unlink()
                removed_files.append(str(path))
            except Exception as e:
                logger.warning(f"Could not delete output file {path}: {e}")

    image_dir = settings.OUTPUT_DIR / "images" / lecture_id
    if image_dir.exists():
        try:
            import shutil
            shutil.rmtree(image_dir)
            removed_files.append(str(image_dir))
        except Exception as e:
            logger.warning(f"Could not delete image directory {image_dir}: {e}")

    del LECTURE_STORE[lecture_id]

    logger.info(f"Deleted lecture {lecture_id} and {len(removed_files)} associated file(s).")

    return {
        "success": True,
        "message": "Lecture deleted successfully.",
        "lecture_id": lecture_id,
        "files_removed": len(removed_files)
    }
