import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class AudioUtils:
    """
    Utility helpers for processing audio and video files.
    """

    ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".mp4", ".webm", ".flac"}

    # Minimum plausible size (bytes) for a real audio/video file. Anything
    # smaller is almost certainly a truncated download or an empty/corrupted
    # upload rather than real media.
    MIN_PLAUSIBLE_SIZE_BYTES = 512

    # Known container/file-signature magic bytes, used as a structural
    # fallback check for formats mutagen cannot parse directly (e.g. WebM).
    _MAGIC_SIGNATURES = {
        b"\x1aE\xdf\xa3": "webm/mkv",
        b"RIFF": "wav/avi",
        b"OggS": "ogg",
        b"fLaC": "flac",
    }

    @classmethod
    def is_valid_file(cls, filename: str) -> bool:
        ext = Path(filename).suffix.lower()
        return ext in cls.ALLOWED_EXTENSIONS

    @classmethod
    def get_file_info(cls, file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {"file_name": file_path.name, "size_mb": 0.0, "format": "unknown"}

        size_bytes = file_path.stat().st_size
        size_mb = round(size_bytes / (1024 * 1024), 2)
        ext = file_path.suffix.lower().replace(".", "").upper()

        return {
            "file_name": file_path.name,
            "size_mb": size_mb,
            "format": ext,
            "path": str(file_path)
        }

    @classmethod
    def scan_media_file(cls, file_path: Path) -> Dict[str, Any]:
        """
        Accurately scans an uploaded or downloaded media file for integrity
        before it enters the AI pipeline: confirms it exists, isn't empty or
        truncated, and (where the container format allows it) verifies a
        real, non-zero audio/video duration via metadata inspection.

        Returns a dict: {valid, duration_seconds, reason, codec_info}
        """
        result: Dict[str, Any] = {
            "valid": False,
            "duration_seconds": None,
            "reason": None,
            "codec_info": None,
        }

        if not file_path.exists():
            result["reason"] = "File does not exist on disk."
            return result

        size_bytes = file_path.stat().st_size
        if size_bytes == 0:
            result["reason"] = "File is empty (0 bytes)."
            return result
        if size_bytes < cls.MIN_PLAUSIBLE_SIZE_BYTES:
            result["reason"] = "File is too small to be valid media (likely corrupted or truncated)."
            return result

        # Deep scan: try to read real duration/codec metadata with mutagen.
        try:
            import mutagen
            probe = mutagen.File(str(file_path))
            if probe is not None and getattr(probe, "info", None) is not None:
                duration = getattr(probe.info, "length", 0.0) or 0.0
                if duration <= 0:
                    result["reason"] = "Media file has a zero-length audio track (corrupted or empty)."
                    return result
                result.update({
                    "valid": True,
                    "duration_seconds": round(duration, 2),
                    "codec_info": type(probe).__name__,
                })
                return result
        except Exception as e:
            logger.warning(f"Deep metadata scan could not parse {file_path.name}: {e}")

        # Shallow fallback: formats mutagen doesn't natively parse (e.g. WebM,
        # some MP4/video containers). Verify against known file signatures so
        # we don't block valid uploads just because deep inspection is
        # unavailable, while still rejecting garbage/non-media files.
        if cls._has_valid_media_signature(file_path):
            result.update({
                "valid": True,
                "duration_seconds": None,
                "codec_info": "unverified-container",
            })
        else:
            result["reason"] = "File does not match any recognized audio/video container signature."

        return result

    @classmethod
    def _has_valid_media_signature(cls, file_path: Path) -> bool:
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
        except Exception:
            return False

        if not header:
            return False

        for magic, _label in cls._MAGIC_SIGNATURES.items():
            if header.startswith(magic):
                return True

        # ID3-tagged or bare MP3 frame sync
        if header[:3] == b"ID3":
            return True
        if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return True

        # MP4/M4A "ftyp" box appears at byte offset 4
        if len(header) >= 8 and header[4:8] == b"ftyp":
            return True

        return False
