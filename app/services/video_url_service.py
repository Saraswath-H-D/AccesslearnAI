import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Substrings yt-dlp commonly raises when a video needs the requester to be
# signed in (private/unlisted-restricted, age-gated, members-only) or when
# the platform's bot-check is blocking anonymous requests. In every case the
# fix is the same: retry using cookies from a browser the user is signed
# into, so we bucket them all under "authentication required".
_AUTH_REQUIRED_HINTS = [
    "sign in", "log in", "login required", "private video", "members-only",
    "member-only", "age-restricted", "age restricted", "not a bot",
    "cookies", "premium", "paid content", "requires payment",
]

SUPPORTED_BROWSERS = ["chrome", "edge", "firefox", "brave", "vivaldi", "opera", "safari"]


class AuthRequiredError(Exception):
    """Raised when a video cannot be fetched anonymously and needs sign-in."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class VideoUrlService:
    """
    Fetches the audio track of an educator's video from a URL (YouTube or
    any of the hundreds of other sites yt-dlp supports) so it can be run
    through the same accessibility pipeline as an uploaded file.

    Downloads audio-only when available (no ffmpeg needed - the native
    container, e.g. .webm/.m4a, is saved as-is).
    """

    MAX_FILESIZE_BYTES = 500 * 1024 * 1024  # matches the direct-upload limit

    def fetch_audio(self, url: str, dest_dir: Path, lecture_id: str, browser: Optional[str] = None) -> Dict[str, Any]:
        """
        Downloads the given video URL's audio to dest_dir/{lecture_id}.<ext>.
        Returns {"filename": ..., "title": ..., "duration": ...}.
        Raises AuthRequiredError if the video needs sign-in and no working
        browser cookies were supplied; raises ValueError for other failures.
        """
        import yt_dlp

        if not re.match(r"^https?://", url.strip(), re.IGNORECASE):
            raise ValueError("Please paste a full video URL starting with http:// or https://")

        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": str(dest_dir / f"{lecture_id}.%(ext)s"),
            "max_filesize": self.MAX_FILESIZE_BYTES,
            "restrictfilenames": True,
        }

        if browser:
            if browser not in SUPPORTED_BROWSERS:
                raise ValueError(f"Unsupported browser '{browser}'. Choose one of: {', '.join(SUPPORTED_BROWSERS)}")
            ydl_opts["cookiesfrombrowser"] = (browser,)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            msg = str(e)
            lower_msg = msg.lower()
            if not browser and any(hint in lower_msg for hint in _AUTH_REQUIRED_HINTS):
                raise AuthRequiredError(
                    "This video needs you to be signed in to watch it (private, age-restricted, "
                    "members-only, or the site is asking to verify you're not a bot)."
                )
            logger.error(f"Video URL fetch failed for {url}: {msg}")
            raise ValueError(f"Could not fetch that video: {msg[:300]}")

        ext = info.get("ext", "mp4")
        saved_filename = f"{lecture_id}.{ext}"
        saved_path = dest_dir / saved_filename
        if not saved_path.exists():
            raise ValueError("The video was processed but no audio/video file was saved. Try a different link.")

        return {
            "filename": saved_filename,
            "title": info.get("title") or "Untitled Video",
            "duration": info.get("duration"),
            "source_url": url,
        }


video_url_service = VideoUrlService()
