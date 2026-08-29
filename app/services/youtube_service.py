import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Matches standard watch links, shortened youtu.be links, /shorts/ and
# /embed/ URLs, with or without scheme/www, and pulls out the 11-char
# video id for validation and logging.
YOUTUBE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?"
    r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)


class YouTubeIngestService:
    """
    Validates YouTube lecture links and downloads their audio track so
    videos can flow through the same accessibility pipeline as directly
    uploaded files.
    """

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        if not url:
            return None
        match = YOUTUBE_URL_RE.search(url.strip())
        return match.group(1) if match else None

    @classmethod
    def is_valid_youtube_url(cls, url: str) -> bool:
        return cls.extract_video_id(url) is not None

    def download_audio(self, url: str, lecture_id: str, output_dir: Path) -> Dict[str, Any]:
        """
        Downloads the best available audio-only stream for the given video
        (no ffmpeg/re-encoding required) and returns metadata about the
        result. Raises ValueError for a bad URL and RuntimeError for
        download/environment failures.
        """
        try:
            import yt_dlp
        except ImportError as e:
            raise RuntimeError("The yt-dlp package is not installed on the server.") from e

        video_id = self.extract_video_id(url)
        if not video_id:
            raise ValueError("Invalid or unsupported YouTube URL. Please provide a youtube.com or youtu.be link.")

        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(output_dir / f"{lecture_id}.%(ext)s")

        ydl_opts = {
            # Audio-only formats download as a single stream with no video
            # track to merge, so no ffmpeg/postprocessing is required.
            "format": "bestaudio/worstaudio",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
            "socket_timeout": 30,
            "retries": 3,
        }

        logger.info(f"Downloading YouTube audio for video_id={video_id}")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_path = Path(ydl.prepare_filename(info))
        except Exception as e:
            raise RuntimeError(f"Could not download audio for this video: {e}") from e

        if not downloaded_path.exists():
            # yt-dlp can finalize with a slightly different extension than
            # prepare_filename predicted; fall back to a directory scan.
            candidates = sorted(output_dir.glob(f"{lecture_id}.*"))
            if not candidates:
                raise RuntimeError("YouTube download completed but no output file was found.")
            downloaded_path = candidates[0]

        return {
            "file_path": downloaded_path,
            "title": info.get("title") or "YouTube Lecture",
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "video_id": video_id,
            "webpage_url": info.get("webpage_url", url),
        }


youtube_service = YouTubeIngestService()
