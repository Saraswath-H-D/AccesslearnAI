import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger("accesslearn.gemini")

# Transient server-side errors worth retrying (model overload, rate limit).
# A 404 (bad model name) or 400 (bad request) is NOT retried -- retrying a
# permanently broken request just wastes quota and time.
_RETRYABLE_STATUS_CODES = {429, 500, 503}

# Observed during development: the free tier enforces a hard
# GenerateRequestsPerDayPerProjectPerModel quota (as low as 20/day on some
# models for this key) -- confirmed via the API's own 429 error body, not
# guessed. This is a genuine per-MODEL daily cap, not a rate/overload issue
# retrying can fix: once a model's quota is spent, every call to it fails
# until the next day regardless of backoff. The fallback model below has
# its own separate quota bucket, so trying it after the primary is
# exhausted is the one thing that actually helps within the same day.
_FALLBACK_MODEL = "gemini-3.1-flash-lite"


class GeminiUnavailableError(Exception):
    """Raised when Gemini is not configured or fails after all retries."""


class GeminiService:
    """
    Thin wrapper around the Gemini API for every reasoning-heavy task in the
    video-learning pipeline: structured video understanding, concept
    extraction, A-Z note generation, flowchart extraction, translation, and
    video-frame (visual) analysis.

    This exists because the project's local models (Whisper, flan-t5-small)
    were empirically verified (during development) to be incapable of this
    level of structured reasoning -- flan-t5-small barely restructures a
    handful of sentences, let alone produces teacher-quality, dynamically
    structured notes grounded in a full lecture. There is no honest local
    substitute for this specific set of features.
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        if not settings.has_gemini:
            raise GeminiUnavailableError(
                "GEMINI_API_KEY is not set. This feature requires a Gemini API key "
                "(https://aistudio.google.com/apikey) in backend/.env."
            )
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    def _call_with_retry(self, model_fn, *, max_attempts: int = 5, base_delay: float = 4.0):
        """
        `model_fn` takes a model name and performs the call. Retries the
        configured primary model with backoff, then makes one more retry
        cycle against `_FALLBACK_MODEL` if the primary is still failing --
        see the module-level note on why a fallback model is worth having.
        """
        from google.genai import errors as genai_errors

        for model_name in (settings.GEMINI_MODEL_NAME, _FALLBACK_MODEL):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return model_fn(model_name)
                except genai_errors.APIError as e:
                    status = getattr(e, "code", None) or getattr(e, "status_code", None)
                    last_exc = e
                    if status in _RETRYABLE_STATUS_CODES and attempt < max_attempts - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Gemini call to {model_name} failed ({status}), retrying in {delay:.0f}s (attempt {attempt + 1}/{max_attempts})...")
                        time.sleep(delay)
                        continue
                    break  # exhausted retries on this model; try the fallback model (if any left)
            if model_name != _FALLBACK_MODEL:
                logger.warning(f"Primary model {model_name} exhausted retries ({last_exc}); trying fallback model {_FALLBACK_MODEL}.")
        raise GeminiUnavailableError(f"Gemini API error after retrying both primary and fallback models: {last_exc}")

    def generate_json(self, prompt: str, images: Optional[List[bytes]] = None) -> Dict[str, Any]:
        """
        Sends a prompt (optionally with images) and parses the response as
        JSON. Raises GeminiUnavailableError if the key is missing, the call
        fails after retries, or the response isn't valid JSON.
        """
        client = self._get_client()
        from google.genai import types

        contents: List[Any] = []
        if images:
            for img_bytes in images:
                contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
        contents.append(prompt)

        def _do_call(model_name: str):
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )

        response = self._call_with_retry(_do_call)
        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, AttributeError) as e:
            raise GeminiUnavailableError(f"Gemini returned invalid JSON: {e}") from e

    def generate_text(self, prompt: str, images: Optional[List[bytes]] = None) -> str:
        """Sends a prompt (optionally with images) and returns the raw text response."""
        client = self._get_client()
        from google.genai import types

        contents: List[Any] = []
        if images:
            for img_bytes in images:
                contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
        contents.append(prompt)

        def _do_call(model_name: str):
            return client.models.generate_content(model=model_name, contents=contents)

        response = self._call_with_retry(_do_call)
        return (response.text or "").strip()

    def analyze_frame(self, image_bytes: bytes, timestamp_hint: str = "") -> Optional[str]:
        """
        Describes notable visual content (slides, diagrams, code, charts,
        text) in a single video frame. Returns None if nothing educational
        is visible, so uninteresting frames (e.g. a talking-head shot with
        no on-screen content) don't pollute the analysis.
        """
        prompt = (
            "This is a frame from an educational lecture video"
            f"{f' at timestamp {timestamp_hint}' if timestamp_hint else ''}. "
            "If it shows a slide, diagram, chart, code, table, or important on-screen text, "
            "describe exactly what it shows in 1-2 factual sentences (transcribe key text/labels "
            "verbatim where legible). If it's just a person talking with no meaningful on-screen "
            "content, respond with exactly: NONE"
        )
        try:
            result = self.generate_text(prompt, images=[image_bytes])
        except GeminiUnavailableError as e:
            logger.warning(f"Frame analysis failed: {e}")
            return None
        if result.strip().upper() == "NONE" or not result.strip():
            return None
        return result.strip()


gemini_service = GeminiService()
