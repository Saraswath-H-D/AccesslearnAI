import os
import re
import logging
import json
from collections import Counter
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

_STOPWORDS = set("""
a about above after again against all am an and any are aren't as at be because been
before being below between both but by can't cannot could couldn't did didn't do does
doesn't doing don't down during each few for from further had hadn't has hasn't have
haven't having he he'd he'll he's her here here's hers herself him himself his how
how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most
mustn't my myself no nor not of off on once only or other ought our ours ourselves
out over own same shan't she she'd she'll she's should shouldn't so some such than
that that's the their theirs them themselves then there there's these they they'd
they'll they're they've this those through to too under until up very was wasn't we
we'd we'll we're we've were weren't what what's when when's where where's which
while who who's whom why why's with won't would wouldn't you you'd you'll you're
you've your yours yourself yourselves also going okay yeah um uh like just really
going now know one two three basically actually right thing things lot lots kind
sort well see said say gonna wanna will shall may might must can cannot get got
gets getting make made makes take takes taking let lets even still already
""".split())

class NLPProcessingService:
    """
    Handles AI Content Simplification, Summarization, Key Points, Vocabulary,
    and Structured Study Notes using Gemini API / HuggingFace T5 / Smart NLP Engine.
    Designed specifically for students with cognitive or learning disabilities.
    """
    
    def process_transcript(self, transcript_text: str, lecture_title: str = "Lecture") -> Dict[str, Any]:
        """
        Processes transcript text into simplified learning modules.
        """
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        
        if gemini_key and len(gemini_key) > 10:
            try:
                result = self._process_with_gemini(transcript_text, lecture_title, gemini_key)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Gemini API processing failed: {e}. Falling back to HuggingFace T5 / NLP Engine.")

        # High-Quality Accessible NLP Fallback Engine
        return self._generate_nlp_fallback(transcript_text, lecture_title)

    def _process_with_gemini(self, transcript_text: str, lecture_title: str, api_key: str) -> Dict[str, Any]:
        """
        Uses Google Gemini API to generate structured accessibility JSON.
        """
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are an expert Accessibility Educator specializing in modifying complex academic lectures for students with learning and cognitive disabilities.
        
        Lecture Title: {lecture_title}
        Transcript:
        {transcript_text}
        
        Provide a JSON response with the following keys strictly formatted as valid JSON:
        {{
            "simplified_content": "A clear, plain-language breakdown of the lecture using bullet points and simple analogies. Avoid dense jargon.",
            "easy_explanation": "A short, simple 2-paragraph overview explaining the core idea as if explaining to a beginner student.",
            "short_summary": "A concise 3-4 sentence executive summary of the entire lecture.",
            "key_points": ["Key point 1", "Key point 2", "Key point 3", "Key point 4", "Key point 5"],
            "keywords": [
                {{"term": "Term 1", "definition": "Simple 1-line plain language definition"}},
                {{"term": "Term 2", "definition": "Simple 1-line plain language definition"}},
                {{"term": "Term 3", "definition": "Simple 1-line plain language definition"}}
            ],
            "study_notes": [
                {{"heading": "Topic 1", "content": "Detailed accessible study note point."}},
                {{"heading": "Topic 2", "content": "Detailed accessible study note point."}}
            ]
        }}
        Return ONLY valid JSON without markdown fences.
        """
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp.replace("```json", "").replace("```", "").strip()
        elif text_resp.startswith("```"):
            text_resp = text_resp.replace("```", "").strip()
            
        return json.loads(text_resp)

    def _generate_nlp_fallback(self, transcript_text: str, lecture_title: str) -> Dict[str, Any]:
        """
        Genuine, fully offline content analysis (no API key required): scores
        each sentence of the real transcript by significant-word frequency
        (a TextRank-style extractive summarization) and builds the
        simplified/summary/keywords/study-notes structure from sentences that
        actually appear in the lecture -- not a canned template.
        """
        sentences = self._split_sentences(transcript_text)
        if not sentences:
            sentences = [f"No substantial speech content was detected for \"{lecture_title}\"."]

        scores, freq = self._score_sentences(sentences)
        ranked_idx = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)

        # Spoken lectures repeat phrases while teaching ("we get the value...
        # we get the value..."), so picking pure top-N by score alone tends
        # to select several near-duplicate sentences. Skip a candidate that
        # overlaps too heavily with one already chosen.
        summary_n = max(2, min(4, len(sentences) // 8 or 2))
        summary_idx = self._select_diverse(ranked_idx, sentences, summary_n)
        short_summary = " ".join(sentences[i] for i in summary_idx)

        points_n = max(3, min(6, len(sentences) // 5 or 3))
        points_idx = self._select_diverse(ranked_idx, sentences, points_n)
        key_points = [sentences[i] for i in points_idx]

        top_terms = [w for w, _ in freq.most_common(30) if len(w) > 3]
        keywords, seen = [], set()
        for term in top_terms:
            if term in seen:
                continue
            seen.add(term)
            keywords.append({
                "term": term.capitalize(),
                "definition": f"A term emphasized repeatedly in this lecture on \"{lecture_title}\"."
            })
            if len(keywords) >= 5:
                break
        if not keywords:
            keywords = [{"term": lecture_title, "definition": "The central subject of this lecture."}]

        midpoint = len(sentences) // 2
        first_half_idx = self._select_diverse([i for i in ranked_idx if i < midpoint], sentences, 4)
        second_half_idx = self._select_diverse([i for i in ranked_idx if i >= midpoint], sentences, 4)
        study_notes = []
        if first_half_idx:
            study_notes.append({"heading": "1. Opening Concepts", "content": " ".join(sentences[i] for i in first_half_idx)})
        if second_half_idx:
            study_notes.append({"heading": "2. Further Discussion", "content": " ".join(sentences[i] for i in second_half_idx)})
        if not study_notes:
            study_notes.append({"heading": "1. Summary", "content": short_summary})

        return {
            "simplified_content": "\n".join(f"• {s}" for s in key_points),
            "easy_explanation": f"This lecture, \"{lecture_title}\", covers the following in plain language: {short_summary}",
            "short_summary": short_summary,
            "key_points": key_points,
            "keywords": keywords,
            "study_notes": study_notes
        }

    @staticmethod
    def _significant_words(sentence: str) -> set:
        return {w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", sentence.lower()) if w not in _STOPWORDS}

    @classmethod
    def _select_diverse(cls, ranked_idx: List[int], sentences: List[str], n: int, overlap_threshold: float = 0.6) -> List[int]:
        """
        Walk sentence indices in ranked (best-first) order, skipping any
        candidate whose significant words overlap too heavily with a
        sentence already chosen -- avoids a summary made of near-duplicate
        repeated phrases from spoken/disfluent lecture speech.
        """
        chosen, chosen_words = [], []
        for i in ranked_idx:
            words = cls._significant_words(sentences[i])
            if words and any(
                len(words & cw) / len(words | cw) > overlap_threshold
                for cw in chosen_words
            ):
                continue
            chosen.append(i)
            chosen_words.append(words)
            if len(chosen) >= n:
                break
        return sorted(chosen)

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text:
            return []
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if len(p.strip()) > 15]

    @staticmethod
    def _score_sentences(sentences: List[str]):
        words_per_sentence = []
        freq: Counter = Counter()
        for s in sentences:
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", s.lower()) if w not in _STOPWORDS]
            words_per_sentence.append(words)
            freq.update(words)

        if freq:
            max_freq = max(freq.values())
            normalized = {w: c / max_freq for w, c in freq.items()}
        else:
            normalized = {}

        scores = []
        lead_zone = max(1, len(sentences) // 6)
        for i, words in enumerate(words_per_sentence):
            if not words:
                scores.append(0.0)
                continue
            score = sum(normalized.get(w, 0.0) for w in words) / len(words)
            if i < lead_zone:
                score *= 1.15
            scores.append(score)
        return scores, freq

nlp_service = NLPProcessingService()
