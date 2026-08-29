import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "AccessLearnAI/1.0 (Educational Accessibility Platform)"

# Rich, distinct fallback colors so generated placeholder cards for
# different topics are visually easy to tell apart at a glance.
PLACEHOLDER_COLORS = ["#3b82f6", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]


class ImageIllustrationService:
    """
    Finds simple, freely licensed illustrative pictures related to a
    lecture's key concepts (via the Wikimedia Commons search API, which
    needs no API key) so simplified notes are easier to follow at a glance.

    Falls back to a clean, locally generated placeholder graphic per topic
    whenever the network is unavailable, times out, or turns up nothing --
    so notes and the PDF export always have a visual for every topic.
    """

    def fetch_topic_images(self, topics: List[str], output_dir: Path, max_images: int = 4) -> List[Dict[str, Any]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        results = []

        # De-duplicate while preserving order (title + keywords can overlap)
        seen = set()
        unique_topics = []
        for t in topics:
            key = t.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique_topics.append(t.strip())

        for idx, topic in enumerate(unique_topics[:max_images]):
            filename = f"img_{idx}.jpg"
            dest_path = output_dir / filename
            entry = {"filename": filename, "path": str(dest_path), "caption": topic, "source": None}

            image_info = self._safe_fetch_from_wikimedia(topic)
            if image_info and self._safe_download_image(image_info["url"], dest_path):
                entry["source"] = "Wikimedia Commons"
                entry["attribution"] = image_info.get("title", "")
            else:
                self._generate_placeholder(topic, dest_path, idx)
                entry["source"] = "Generated Illustration"
                entry["attribution"] = ""

            results.append(entry)

        return results

    def _safe_fetch_from_wikimedia(self, query: str) -> Optional[Dict[str, Any]]:
        try:
            params = {
                "action": "query",
                "generator": "search",
                "gsrnamespace": 6,
                "gsrsearch": f"{query} filetype:bitmap",
                "gsrlimit": 1,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 640,
                "format": "json",
            }
            resp = requests.get(WIKIMEDIA_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=6)
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for _, page in pages.items():
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    info = imageinfo[0]
                    url = info.get("thumburl") or info.get("url")
                    if url:
                        return {"url": url, "title": page.get("title", query)}
            return None
        except Exception as e:
            logger.warning(f"Wikimedia image search failed for '{query}': {e}")
            return None

    def _safe_download_image(self, url: str, dest_path: Path) -> bool:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            # Normalize to RGB JPEG so PDF embedding never chokes on odd formats
            img = Image.open(dest_path).convert("RGB")
            img.save(dest_path, "JPEG", quality=85)
            return True
        except Exception as e:
            logger.warning(f"Failed to download related image from {url}: {e}")
            return False

    def _generate_placeholder(self, topic: str, dest_path: Path, idx: int):
        color = PLACEHOLDER_COLORS[idx % len(PLACEHOLDER_COLORS)]
        img = Image.new("RGB", (640, 400), color=color)
        draw = ImageDraw.Draw(img)
        text = topic if len(topic) <= 40 else topic[:37] + "..."

        font = None
        for candidate in ("arial.ttf", "Arial.ttf", "DejaVuSans-Bold.ttf"):
            try:
                font = ImageFont.truetype(candidate, 34)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((640 - tw) / 2, (400 - th) / 2), text, fill="white", font=font)
        img.save(dest_path, "JPEG", quality=90)


image_service = ImageIllustrationService()
