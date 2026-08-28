import os
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "what", "why", "how",
    "does", "do", "did", "of", "in", "on", "to", "for", "and", "or", "it",
    "this", "that", "explain", "please", "can", "you", "me", "about", "with",
    "lecture", "i", "my", "your", "so", "tell", "mean", "means", "define"
}


class DoubtSolvingChatService:
    """
    Answers a student's question about a specific lecture. Uses Gemini when
    available, grounded strictly in that lecture's transcript and notes.
    Falls back to a keyword-overlap retrieval engine so the doubt-solving
    session still works with no API key configured.
    """

    def answer_question(self, question: str, lecture_data: Dict[str, Any], lecture_title: str = "Lecture") -> str:
        question = (question or "").strip()
        if not question:
            return "Go ahead and type your question about this lecture — I'm ready to help!"

        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        if gemini_key and len(gemini_key) > 10:
            try:
                answer = self._answer_with_gemini(question, lecture_data, lecture_title, gemini_key)
                if answer:
                    return answer
            except Exception as e:
                logger.warning(f"Gemini chat answer failed: {e}. Falling back to retrieval engine.")

        return self._answer_with_fallback(question, lecture_data, lecture_title)

    # ------------------------------------------------------------------
    def _answer_with_gemini(self, question: str, lecture_data: Dict[str, Any], lecture_title: str, api_key: str) -> str:
        from google import genai
        client = genai.Client(api_key=api_key)

        transcript_text = (lecture_data.get("transcript") or {}).get("full_text", "")
        simplified = lecture_data.get("simplified") or {}
        summary = lecture_data.get("summary") or {}

        prompt = f"""
        You are a patient, encouraging AI teaching assistant helping a student
        who may have a hearing, speech, or cognitive/learning disability
        understand a lecture. Answer ONLY using the lecture material below.
        Use short sentences, plain everyday language, and avoid jargon. If the
        answer truly isn't in the material, say so honestly and suggest what
        part of the lecture to re-read instead of guessing.

        Lecture Title: {lecture_title}
        Executive Summary: {summary.get('short_summary', '')}
        Easy Explanation: {simplified.get('easy_explanation', '')}
        Simplified Notes: {simplified.get('simplified_content', '')}
        Transcript (partial): {transcript_text[:6000]}

        Student's question: {question}

        Reply with just the answer text (2-5 short sentences max), no markdown headers.
        """

        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.strip()

    # ------------------------------------------------------------------
    def _answer_with_fallback(self, question: str, lecture_data: Dict[str, Any], lecture_title: str) -> str:
        knowledge_items = self._build_knowledge_base(lecture_data)
        q_tokens = self._tokenize(question)

        if not q_tokens:
            return "Could you rephrase your question with a few more words? I want to make sure I find the right part of the lecture for you."

        best_item, best_score = None, 0
        for item in knowledge_items:
            score = len(q_tokens & item["tokens"])
            if score > best_score:
                best_item, best_score = item, score

        if best_item and best_score > 0:
            return (
                f"Here's what the lecture says about that ({best_item['label']}): "
                f"{best_item['text']}"
            )

        topic_hints = [item["label"] for item in knowledge_items[:5]]
        hint_text = ", ".join(topic_hints) if topic_hints else "the Simplified Notes tab"
        return (
            f"I couldn't find that specific detail in \"{lecture_title}\". "
            f"Try asking about one of these instead: {hint_text}. "
            f"You can also check the Simplified Notes or Transcript tab for more detail."
        )

    def _build_knowledge_base(self, lecture_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        simplified = lecture_data.get("simplified") or {}
        summary = lecture_data.get("summary") or {}
        key_points = lecture_data.get("key_points") or []
        transcript = lecture_data.get("transcript") or {}

        if summary.get("short_summary"):
            items.append({"label": "Summary", "text": summary["short_summary"]})

        if simplified.get("easy_explanation"):
            items.append({"label": "Easy Explanation", "text": simplified["easy_explanation"]})

        for kw in summary.get("keywords") or []:
            term = kw.get("term", "")
            definition = kw.get("definition", "")
            if term and definition:
                items.append({"label": term, "text": f"{term} — {definition}"})

        for kp in key_points:
            if kp:
                items.append({"label": "Key Point", "text": kp})

        for note in simplified.get("study_notes") or []:
            heading = note.get("heading", "")
            content = note.get("content", "")
            if content:
                items.append({"label": heading or "Study Note", "text": content})

        for seg in (transcript.get("segments") or [])[:40]:
            text = seg.get("text", "")
            if text:
                items.append({"label": f"Transcript @ {seg.get('timestamp', '')}", "text": text})

        for item in items:
            item["tokens"] = self._tokenize(item["label"] + " " + item["text"])

        return items

    def _tokenize(self, text: str) -> set:
        words = re.findall(r"[a-zA-Z']+", text.lower())
        return {w for w in words if w not in _STOPWORDS and len(w) > 2}


chat_service = DoubtSolvingChatService()
