import json
import logging
from typing import Any, Dict, List

from app.services.gemini_service import gemini_service, GeminiUnavailableError

logger = logging.getLogger("accesslearn.notes")

NOTES_SYSTEM_PROMPT = """You are an excellent teacher who just watched a student's complete lecture video and is now writing personalized study notes explaining EVERYTHING from A to Z, so the student never needs to rewatch the video.

STRICT GROUNDING RULES (violating these makes the notes useless and dishonest):
- Every concept, example, and process you explain MUST come from the structured video data given below. Do not invent facts, examples, or concepts that are not present in it.
- If the speaker gave a specific example, use that exact example. Do not substitute a generic one.
- Do not pretend outside/supplemental knowledge was taught in the video.

STRUCTURE RULES:
- Choose section headings that fit THIS video's actual content and flow. Do not force a fixed template (no generic "Introduction/Advantages/Disadvantages/Conclusion" unless the video actually has that shape).
- Only reference a visual for a section if one of the provided AVAILABLE VISUALS genuinely helps explain that section's concept. Do not force a visual into every section.
- Write in short, clear sentences a college student can follow. Simplify the LANGUAGE, never the technical KNOWLEDGE -- keep every important technical detail.

DIAGRAM RULES (important -- diagrams make the notes genuinely easier to understand, so look actively for a reason to include one):
- Include a simple diagram for a section whenever it would help a student visualize that section's content. This is NOT limited to step-by-step processes/algorithms -- also create one for:
  * a comparison (e.g. two things contrasted -- use a flowchart with two labeled branches),
  * a hierarchy or classification (e.g. "X contains A, B, C" -- use a flowchart with one node branching to several),
  * a cause-and-effect or relationship chain (e.g. "A leads to B which causes C"),
  * scale/structure relationships (e.g. "the universe contains galaxies, which contain stars, which contain planets").
- Base every node/label strictly on what THIS section actually says -- never invent a relationship or fact not present in the content.
- Keep each diagram simple: 3-6 nodes, short labels (2-4 words each), one clear diagram per section at most.
- Use Mermaid `flowchart TD` syntax for all diagram types (arrows show the relationship direction, whatever it represents -- sequence, hierarchy, or cause/effect).
- Skip the diagram only when a section is pure narrative, opinion, or reflection with no structure, comparison, or relationship that a diagram could usefully show (e.g. a closing philosophical remark). When in doubt and the section names 3+ related concepts, prefer including a simple diagram over skipping it.

Return ONLY valid JSON (no markdown fences) with this exact structure:
{
  "title": "a short, accurate title for the overall video topic",
  "sections": [
    {
      "heading": "section heading (numbering + name, chosen by you based on the content)",
      "content": "the A-Z explanation for this section in flowing prose/short paragraphs, simple student-friendly language, grounded only in the given data",
      "startTime": <number, seconds, from the section's data>,
      "endTime": <number, seconds>,
      "flowchart": null OR {
        "title": "short diagram title",
        "mermaid": "flowchart TD\\n  A[Concept 1] --> B[Concept 2]\\n  B --> C[Concept 3]",
        "accessibleText": "Plain-language description of what the diagram shows and how the parts relate, written so a screen reader user gets the same understanding as someone looking at it."
      },
      "visualTimestamp": null OR <number, seconds -- MUST exactly match one of the AVAILABLE VISUALS timestamps below, if and only if it genuinely helps this section>,
      "visualCaption": null OR "a short caption explaining what the visual shows and why it's relevant here"
    }
  ]
}"""


class NotesService:
    """
    Generates the primary "Simplified Notes" learning experience from the
    already-structured video representation (see video_structure_service.py)
    -- teacher-quality, A-Z, video-grounded, with flowcharts and visual
    references included only where the video's actual content supports them.
    """

    def generate_notes(self, structure: Dict[str, Any], available_visuals: List[Dict[str, Any]]) -> Dict[str, Any]:
        visuals_block = "\n".join(
            f"- timestamp {v['timestamp_seconds']:.0f}s: {v['description']}" for v in available_visuals
        ) or "(none available)"

        sections_for_prompt = [
            {k: v for k, v in s.items() if k != "transcriptText"} | {"transcriptExcerpt": s.get("transcriptText", "")[:800]}
            for s in structure["sections"]
        ]

        prompt = (
            f"{NOTES_SYSTEM_PROMPT}\n\n"
            f"VIDEO STRUCTURE DATA:\n{json.dumps(sections_for_prompt, indent=2)}\n\n"
            f"AVAILABLE VISUALS (only reference these exact timestamps if genuinely useful):\n{visuals_block}"
        )

        try:
            data = gemini_service.generate_json(prompt)
            if data.get("sections"):
                return self._attach_visual_paths(data, available_visuals)
        except GeminiUnavailableError as e:
            logger.error(f"Notes generation failed: {e}")

        # Fallback: bare-bones notes directly from the structure, so the
        # student still gets something grounded rather than nothing.
        return self._fallback_notes(structure)

    def _attach_visual_paths(self, notes: Dict[str, Any], available_visuals: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_timestamp = {v["timestamp_seconds"]: v for v in available_visuals}
        for section in notes.get("sections", []):
            ts = section.get("visualTimestamp")
            if ts is not None:
                # Match to the closest available visual within a small tolerance,
                # since the model may echo back a slightly rounded timestamp.
                closest = min(by_timestamp.keys(), key=lambda t: abs(t - ts), default=None)
                if closest is not None and abs(closest - ts) <= 3:
                    section["visualFramePath"] = by_timestamp[closest]["frame_path"]
                else:
                    section["visualTimestamp"] = None
                    section["visualCaption"] = None
        return notes

    def _fallback_notes(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        sections = []
        for s in structure["sections"]:
            sections.append({
                "heading": s.get("title", "Section"),
                "content": s.get("transcriptText", "") or " ".join(s.get("importantPoints", [])),
                "startTime": s.get("startTime", 0),
                "endTime": s.get("endTime", 0),
                "flowchart": None,
                "visualTimestamp": None,
                "visualCaption": None,
            })
        return {"title": "Lecture Notes", "sections": sections}


notes_service = NotesService()
