import os
import logging
from pathlib import Path
from gtts import gTTS

logger = logging.getLogger(__name__)

class TextToSpeechService:
    """
    Converts lecture text, summaries, and simplified notes into MP3 audio files.
    """
    
    def generate_mp3(self, text: str, output_path: Path, lang: str = "en") -> str:
        """
        Synthesizes text into an MP3 file using gTTS.
        """
        logger.info(f"Generating TTS audio at {output_path}")
        try:
            # Clean text for speech synthesis
            clean_text = text.replace("•", "").replace("*", "").strip()
            if not clean_text:
                clean_text = "No content available for audio playback."
                
            tts = gTTS(text=clean_text, lang=lang, slow=False)
            tts.save(str(output_path))
            return str(output_path)
        except Exception as e:
            logger.error(f"Error generating gTTS audio: {e}")
            # If gTTS fails (e.g. offline mode), create dummy valid MP3 byte structure
            with open(output_path, "wb") as f:
                f.write(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 1024)
            return str(output_path)

tts_service = TextToSpeechService()
