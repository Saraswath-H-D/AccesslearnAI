import json
import logging
from typing import Any, Dict

from app.services.gemini_service import gemini_service, GeminiUnavailableError

logger = logging.getLogger("accesslearn.translation")

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
}

_TRANSLATION_INSTRUCTIONS = """Translate the JSON content below into natural, student-friendly {language}.

Rules:
- Preserve the exact same JSON keys and structure -- translate only the human-readable string VALUES.
- The translation must be NATURAL and educational, not a robotic word-for-word conversion. Keep the same meaning.
- Common technical/English terms may be kept in English if that is how students normally encounter them (e.g., variable names, "CPU", "array"), but briefly clarify them in {language} the first time they appear if it helps understanding.
- Inside any "mermaid" field: keep the Mermaid syntax (flowchart TD, arrows -->, brackets [ ]) EXACTLY as is -- only translate the human-readable label text inside the brackets.
- Do NOT translate numbers, timestamps, or field names.
- Do not add or remove any concepts -- meaning must stay identical to the English source.

Return ONLY the translated JSON, same structure, no markdown fences, no commentary.

JSON TO TRANSLATE:
{content}"""


class TranslationService:
    """
    Translates already-generated English content (notes/summary/key points)
    into Hindi or Kannada via Gemini, rather than reprocessing the source
    video per language (Section 40's caching rule) -- the underlying meaning
    stays grounded in the one English structure built from the video.
    """

    def translate_content(self, content: Dict[str, Any], target_lang: str) -> Dict[str, Any]:
        if target_lang == "en":
            return content
        if target_lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {target_lang}")

        prompt = _TRANSLATION_INSTRUCTIONS.format(
            language=SUPPORTED_LANGUAGES[target_lang],
            content=json.dumps(content, ensure_ascii=False, indent=2),
        )

        try:
            translated = gemini_service.generate_json(prompt)
            if translated:
                return translated
        except GeminiUnavailableError as e:
            logger.error(f"Translation to {target_lang} failed: {e}")
            raise

        raise RuntimeError(f"Translation to {target_lang} returned empty content.")


translation_service = TranslationService()
