import logging
from typing import Any, Dict, List

from app.services.gemini_service import gemini_service, GeminiUnavailableError

logger = logging.getLogger("accesslearn.structure")

# Long-video safety net (Section 35 of the brief): don't send an unbounded
# transcript into one Gemini call. Gemini's context window is large enough
# that most lecture-length videos fit in a single call anyway, but very long
# recordings are split into time-bounded chunks first. Chunks are built from
# non-overlapping, contiguous time ranges, so concatenating each chunk's
# sections in order reconstructs the full timeline with nothing dropped.
MAX_CHARS_PER_CHUNK = 15000


def _chunk_segments(segments: List[Dict[str, Any]], max_chars: int) -> List[List[Dict[str, Any]]]:
    chunks: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_len = 0
    for seg in segments:
        seg_len = len(seg.get("text", ""))
        if current and current_len + seg_len > max_chars:
            chunks.append(current)
            current, current_len = [], 0
        current.append(seg)
        current_len += seg_len
    if current:
        chunks.append(current)
    return chunks or [[]]


def _visuals_in_range(visuals: List[Dict[str, Any]], start: float, end: float) -> List[Dict[str, Any]]:
    return [v for v in visuals if start <= v["timestamp_seconds"] < end]


class VideoStructureService:
    """
    Builds the structured intermediate representation of a video (Section 3
    of the brief) by combining Whisper's transcript segments with Gemini's
    visual-frame analysis. This structure is the single source every
    downstream generator (notes, flowcharts, summary, key points,
    translations) reads from -- it's what keeps generated content
    traceable back to actual moments in the video.
    """

    def build_structure(
        self,
        segments: List[Dict[str, Any]],
        visual_observations: List[Dict[str, Any]],
        duration_seconds: float,
        language: str = "en",
    ) -> Dict[str, Any]:
        chunks = _chunk_segments(segments, MAX_CHARS_PER_CHUNK)
        logger.info(f"Building video structure from {len(segments)} transcript segments in {len(chunks)} chunk(s).")

        all_sections: List[Dict[str, Any]] = []
        for chunk in chunks:
            if not chunk:
                continue
            chunk_start = chunk[0]["start"]
            chunk_end = chunk[-1]["end"]
            chunk_visuals = _visuals_in_range(visual_observations, chunk_start, chunk_end)
            sections = self._structure_one_chunk(chunk, chunk_visuals)
            all_sections.extend(sections)

        if not all_sections:
            # Gemini unavailable or produced nothing usable -- fall back to
            # one section covering the whole video from the raw transcript,
            # so the rest of the pipeline still has something to work with.
            full_text = " ".join(s.get("text", "") for s in segments)
            all_sections = [{
                "title": "Full Lecture",
                "startTime": 0,
                "endTime": duration_seconds,
                "concepts": [],
                "visuals": [v["description"] for v in visual_observations],
                "examples": [],
                "importantPoints": [],
                "hasProcess": False,
                "processSteps": [],
                "transcriptText": full_text,
            }]

        return {
            "video": {"duration": duration_seconds, "language": language},
            "sections": all_sections,
        }

    def _structure_one_chunk(self, segments: List[Dict[str, Any]], visuals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        transcript_block = "\n".join(f"[{s['start']:.0f}s-{s['end']:.0f}s] {s['text']}" for s in segments)
        visuals_block = "\n".join(f"[{v['timestamp_seconds']:.0f}s] {v['description']}" for v in visuals) or "(no notable on-screen visuals detected in this range)"

        prompt = f"""You are analyzing a segment of an educational lecture video to build a structured representation.

TRANSCRIPT (with timestamps in seconds):
{transcript_block}

VISUAL CONTENT DETECTED ON SCREEN (slides/diagrams/code/text, with timestamps):
{visuals_block}

Break this segment into logical sections based on what is ACTUALLY discussed (do not force generic sections; the number and titles of sections must reflect the real content). For each section, extract ONLY information present in the transcript or visuals above -- do not invent anything.

Return ONLY valid JSON (no markdown fences) with this exact structure:
{{
  "sections": [
    {{
      "title": "short descriptive title for this section",
      "startTime": <number, seconds>,
      "endTime": <number, seconds>,
      "concepts": ["key concept 1", "key concept 2"],
      "visuals": ["relevant visual descriptions from above that belong to this section, verbatim"],
      "examples": ["any example given by the speaker, verbatim or closely paraphrased"],
      "importantPoints": ["important point the student should remember"],
      "hasProcess": true or false (true only if this section describes a genuine step-by-step process/algorithm/workflow),
      "processSteps": ["step 1", "step 2", ...] (empty array if hasProcess is false),
      "transcriptText": "the relevant transcript text for this section, verbatim"
    }}
  ]
}}"""

        try:
            data = gemini_service.generate_json(prompt)
            sections = data.get("sections", [])
            if sections:
                return sections
        except GeminiUnavailableError as e:
            logger.warning(f"Structure generation failed for this chunk: {e}")

        # Fallback for this chunk only: one section holding the raw text,
        # so a transient failure on one chunk doesn't erase that time range.
        return [{
            "title": f"Segment ({segments[0]['start']:.0f}s - {segments[-1]['end']:.0f}s)",
            "startTime": segments[0]["start"],
            "endTime": segments[-1]["end"],
            "concepts": [],
            "visuals": [v["description"] for v in visuals],
            "examples": [],
            "importantPoints": [],
            "hasProcess": False,
            "processSteps": [],
            "transcriptText": " ".join(s["text"] for s in segments),
        }]


video_structure_service = VideoStructureService()
