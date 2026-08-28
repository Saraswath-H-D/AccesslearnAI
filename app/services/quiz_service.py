import os
import json
import random
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Generic, neutral filler options used only when there isn't enough real
# lecture-derived material to build 4 honest options for a question.
_GENERIC_FILLERS = [
    "This was not mentioned anywhere in the lecture.",
    "The lecture explicitly states the opposite of this.",
    "This is an unrelated topic not covered in the recording.",
    "This detail does not appear in the transcript.",
]


class QuizGenerationService:
    """
    Builds a short multiple-choice quiz from a processed lecture so students
    can immediately check their understanding. Uses Gemini when an API key
    is configured; otherwise builds honest, lecture-grounded questions
    directly from the keywords / key points already extracted by the NLP
    service (no invented facts).
    """

    def generate_quiz(self, transcript_text: str, nlp_data: Dict[str, Any], lecture_title: str = "Lecture") -> List[Dict[str, Any]]:
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

        if gemini_key and len(gemini_key) > 10:
            try:
                result = self._generate_with_gemini(transcript_text, nlp_data, lecture_title, gemini_key)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Gemini quiz generation failed: {e}. Falling back to rule-based quiz builder.")

        return self._generate_fallback_quiz(nlp_data, lecture_title)

    # ------------------------------------------------------------------
    # Gemini-backed generation
    # ------------------------------------------------------------------
    def _generate_with_gemini(self, transcript_text: str, nlp_data: Dict[str, Any], lecture_title: str, api_key: str) -> List[Dict[str, Any]]:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""
        You are an accessible-education quiz writer. Create a multiple-choice quiz
        strictly based on the lecture content below, written in short, simple
        language suitable for students with cognitive or learning disabilities.

        Lecture Title: {lecture_title}
        Lecture Transcript (may be partial):
        {transcript_text[:6000]}

        Return ONLY a valid JSON array (no markdown fences) of 5 to 8 questions,
        each shaped exactly like this:
        {{
            "question": "Simple, clear question text",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": 0,
            "explanation": "One simple sentence explaining why that answer is correct."
        }}
        Every question must be answerable from the transcript. Keep sentences short.
        """

        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp.replace("```json", "").replace("```", "").strip()
        elif text_resp.startswith("```"):
            text_resp = text_resp.replace("```", "").strip()

        parsed = json.loads(text_resp)
        return self._validate_quiz(parsed)

    def _validate_quiz(self, quiz: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        for i, q in enumerate(quiz):
            options = q.get("options") or []
            if len(options) != 4:
                continue
            correct_index = q.get("correct_index")
            if not isinstance(correct_index, int) or not (0 <= correct_index < 4):
                continue
            cleaned.append({
                "id": f"q{i+1}",
                "question": q.get("question", "").strip(),
                "options": [str(o).strip() for o in options],
                "correct_index": correct_index,
                "explanation": q.get("explanation", "").strip()
            })
        if len(cleaned) < 3:
            raise ValueError("Gemini quiz response did not contain enough valid questions.")
        return cleaned

    # ------------------------------------------------------------------
    # Deterministic, lecture-grounded fallback (no API key required)
    # ------------------------------------------------------------------
    def _generate_fallback_quiz(self, nlp_data: Dict[str, Any], lecture_title: str) -> List[Dict[str, Any]]:
        keywords = nlp_data.get("keywords") or []
        key_points = nlp_data.get("key_points") or []
        rng = random.Random(lecture_title)  # stable shuffle per lecture

        questions: List[Dict[str, Any]] = []

        # --- Keyword-definition questions -------------------------------
        all_definitions = [kw.get("definition", "") for kw in keywords if kw.get("definition")]
        for kw in keywords[:5]:
            term = kw.get("term", "").strip()
            definition = kw.get("definition", "").strip()
            if not term or not definition:
                continue

            distractor_pool = [d for d in all_definitions if d != definition]
            rng.shuffle(distractor_pool)
            distractors = distractor_pool[:3]
            while len(distractors) < 3:
                filler = _GENERIC_FILLERS[len(distractors) % len(_GENERIC_FILLERS)]
                if filler not in distractors:
                    distractors.append(filler)

            options = distractors + [definition]
            rng.shuffle(options)
            questions.append({
                "id": f"q{len(questions)+1}",
                "question": f"According to the lecture, what does \"{term}\" mean?",
                "options": options,
                "correct_index": options.index(definition),
                "explanation": f"\"{term}\" means: {definition}"
            })

        # --- Key-point true-statement questions --------------------------
        for kp in key_points[:5]:
            kp = kp.strip()
            if not kp:
                continue
            distractor_pool = [p.strip() for p in key_points if p.strip() != kp]
            rng.shuffle(distractor_pool)
            distractors = distractor_pool[:3]
            while len(distractors) < 3:
                filler = _GENERIC_FILLERS[len(distractors) % len(_GENERIC_FILLERS)]
                if filler not in distractors:
                    distractors.append(filler)

            options = distractors + [kp]
            rng.shuffle(options)
            questions.append({
                "id": f"q{len(questions)+1}",
                "question": "Which statement is TRUE according to this lecture?",
                "options": options,
                "correct_index": options.index(kp),
                "explanation": kp
            })

        rng.shuffle(questions)
        # Re-number ids after shuffle, cap at 8 questions for a short, low-fatigue quiz
        questions = questions[:8]
        for i, q in enumerate(questions):
            q["id"] = f"q{i+1}"

        if not questions:
            questions.append({
                "id": "q1",
                "question": f"What is the main subject of this lecture?",
                "options": [lecture_title, "Unrelated topic A", "Unrelated topic B", "Unrelated topic C"],
                "correct_index": 0,
                "explanation": f"This lecture is titled \"{lecture_title}\"."
            })

        return questions


quiz_service = QuizGenerationService()
