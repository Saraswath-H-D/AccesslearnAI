import json
import logging
from typing import Any, Dict

from app.services.gemini_service import gemini_service, GeminiUnavailableError

logger = logging.getLogger("accesslearn.quality")


class QualityValidationService:
    """
    Checks generated Simplified Notes against the source video structure for
    hallucination, coverage gaps, and structural issues (Section 31). This
    is a best-effort check, not a hard gate: if Gemini is unavailable or the
    check itself fails, processing still completes with the notes as
    generated rather than getting stuck -- a validation step failing must
    never be worse than not validating at all.
    """

    def validate_notes(self, structure: Dict[str, Any], notes: Dict[str, Any]) -> Dict[str, Any]:
        structure_summary = "\n".join(
            f"- {s.get('title')}: concepts={s.get('concepts', [])}" for s in structure["sections"]
        )
        notes_summary = "\n\n".join(
            f"## {s.get('heading')}\n{s.get('content', '')[:500]}" for s in notes.get("sections", [])
        )

        prompt = f"""You are reviewing AI-generated study notes against the original video's structured data,
to check for problems before showing them to a student.

ORIGINAL VIDEO SECTIONS (source of truth):
{structure_summary}

GENERATED NOTES:
{notes_summary}

Check for:
1. Coverage: does every original section's topic appear somewhere in the notes?
2. Hallucination: do the notes mention any concept NOT present in the original sections?
3. Structure: is the explanation logically ordered?

Return ONLY valid JSON: {{"passed": true/false, "issues": ["issue description", ...]}}
("passed" should be false only for real problems, not minor wording differences.)"""

        try:
            result = gemini_service.generate_json(prompt)
            passed = bool(result.get("passed", True))
            issues = result.get("issues", [])
            if not passed:
                logger.warning(f"Quality validation flagged issues: {issues}")
            else:
                logger.info("Quality validation passed.")
            return {"passed": passed, "issues": issues}
        except GeminiUnavailableError as e:
            logger.warning(f"Quality validation could not run (proceeding without it): {e}")
            return {"passed": True, "issues": [], "skipped": True}


quality_service = QualityValidationService()
