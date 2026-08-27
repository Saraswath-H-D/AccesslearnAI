import os
from pathlib import Path
from typing import Dict, Any

class AudioUtils:
    """
    Utility helpers for processing audio and video files.
    """
    
    ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".mp4", ".webm", ".flac"}

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
