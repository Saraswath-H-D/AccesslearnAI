import json
import logging
from typing import Any, Dict

from app.services.gemini_service import gemini_service, GeminiUnavailableError

logger = logging.getLogger("accesslearn.content_gen")


class ContentGenerationService:
    """
    Generates Summary and Key Points from the structured video
    representation. These are deliberately DIFFERENT artifacts from the
    Simplified Notes (detailed, A-Z) and the Transcript (verbatim speech) --
    see Section 43/44 of the brief: each format serves a different purpose
    and must not just be a copy of another.
    """

    def generate_summary(self, structure: Dict[str, Any]) -> Dict[str, str]:
        sections_text = "\n\n".join(
            f"Section: {s.get('title')}\nConcepts: {', '.join(s.get('concepts', []))}\n"
            f"Important points: {'; '.join(s.get('importantPoints', []))}"
            for s in structure["sections"]
        )
        prompt = f"""Based on this structured breakdown of an educational video, write:
1. A "shortSummary": 3-4 sentences capturing the overall idea of the WHOLE video.
2. A "detailedSummary": a compact but complete paragraph-form explanation covering every major concept and how they connect, representing the entire video (not just the first part).

Do not invent anything beyond what's in the data below. Do not simply repeat the transcript verbatim -- synthesize it.

VIDEO STRUCTURE:
{sections_text}

Return ONLY valid JSON: {{"shortSummary": "...", "detailedSummary": "..."}}"""

        try:
            data = gemini_service.generate_json(prompt)
            if data.get("shortSummary"):
                return data
        except GeminiUnavailableError as e:
            logger.error(f"Summary generation failed: {e}")

        fallback = " ".join(s.get("title", "") for s in structure["sections"])
        return {"shortSummary": f"This video covers: {fallback}.", "detailedSummary": fallback}

    def generate_key_points(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        sections_text = "\n\n".join(
            f"Section: {s.get('title')}\nConcepts: {', '.join(s.get('concepts', []))}\n"
            f"Important points: {'; '.join(s.get('importantPoints', []))}\n"
            f"Process steps: {'; '.join(s.get('processSteps', []))}"
            for s in structure["sections"]
        )
        prompt = f"""Based on this structured breakdown of an educational video, create a REVISION sheet: only
the most important facts a student should remember before an exam -- definitions, key
concepts, processes/steps, formulas, comparisons, important examples, conclusions.

Do NOT include trivial statements. Do NOT write another summary -- this is a quick-scan
checklist, so keep each point short (one line each). Only use information present below.

VIDEO STRUCTURE:
{sections_text}

Return ONLY valid JSON: {{"keyPoints": ["point 1", "point 2", ...]}}"""

        try:
            data = gemini_service.generate_json(prompt)
            if data.get("keyPoints"):
                return data
        except GeminiUnavailableError as e:
            logger.error(f"Key points generation failed: {e}")

        fallback_points = []
        for s in structure["sections"]:
            fallback_points.extend(s.get("importantPoints", []))
        return {"keyPoints": fallback_points or [s.get("title", "") for s in structure["sections"]]}


content_generation_service = ContentGenerationService()
