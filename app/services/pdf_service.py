import io
import re
import logging
from pathlib import Path
from typing import Dict, Any, List

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, ListFlowable, ListItem
)

logger = logging.getLogger(__name__)


def _md_bold_to_html(text: str) -> str:
    """Converts simple **bold** markdown into ReportLab's inline <b> tags."""
    if not text:
        return ""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


class NotesPDFService:
    """
    Renders a lecture's simplified study notes -- easy explanation, key
    takeaways, structured notes, keywords, and related illustrative images --
    into a single downloadable, print-friendly PDF, so students can study
    offline with visuals attached to the text.
    """

    def build_pdf(
        self,
        lecture_title: str,
        simplified: Dict[str, Any],
        summary: Dict[str, Any],
        key_points: List[str],
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=LETTER,
            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        )
        styles = getSampleStyleSheet()

        brand_style = ParagraphStyle("Brand", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
        title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=22, textColor=colors.HexColor("#1d4ed8"), spaceAfter=6)
        heading_style = ParagraphStyle("HeadingStyle", parent=styles["Heading2"], textColor=colors.HexColor("#3b82f6"), spaceBefore=16, spaceAfter=8)
        note_heading_style = ParagraphStyle("NoteHeading", parent=styles["Heading3"], textColor=colors.HexColor("#1e293b"), spaceBefore=10, spaceAfter=4)
        body_style = ParagraphStyle("BodyStyle", parent=styles["BodyText"], fontSize=11, leading=16)
        caption_style = ParagraphStyle("CaptionStyle", parent=styles["BodyText"], fontSize=8.5, textColor=colors.grey, alignment=1, spaceBefore=4)

        story = []
        story.append(Paragraph("AccessLearn AI &mdash; Simplified Study Notes", brand_style))
        story.append(Paragraph(lecture_title or "Lecture Notes", title_style))
        story.append(Spacer(1, 10))

        if summary.get("short_summary"):
            story.append(Paragraph("Executive Summary", heading_style))
            story.append(Paragraph(summary["short_summary"], body_style))

        if simplified.get("easy_explanation"):
            story.append(Paragraph("Easy Explanation", heading_style))
            story.append(Paragraph(simplified["easy_explanation"], body_style))

        # Related visuals, placed early so readers get visual context
        # alongside the text right from the start of the document.
        images = simplified.get("images") or []
        valid_images = [img for img in images if img.get("local_path") and Path(img["local_path"]).exists()]
        if valid_images:
            story.append(Paragraph("Related Visuals", heading_style))
            row_cells = []
            for img in valid_images[:4]:
                try:
                    rl_img = RLImage(img["local_path"], width=1.55 * inch, height=1.0 * inch)
                except Exception as e:
                    logger.warning(f"Skipping image in PDF ({img.get('local_path')}): {e}")
                    continue
                caption_text = img.get("caption", "")
                row_cells.append([rl_img, Paragraph(caption_text, caption_style)])
            if row_cells:
                table = Table([row_cells], colWidths=[1.65 * inch] * len(row_cells))
                table.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]))
                story.append(table)
            story.append(Spacer(1, 6))

        if simplified.get("simplified_content"):
            story.append(Paragraph("Plain-Language Breakdown", heading_style))
            for line in simplified["simplified_content"].split("\n"):
                line = line.strip().lstrip("•").strip()
                if line:
                    story.append(Paragraph(f"&bull; {_md_bold_to_html(line)}", body_style))
                    story.append(Spacer(1, 4))

        if key_points:
            story.append(Paragraph("Key Takeaways", heading_style))
            items = [ListItem(Paragraph(_md_bold_to_html(kp), body_style)) for kp in key_points]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=16))

        if simplified.get("study_notes"):
            story.append(Paragraph("Structured Study Notes", heading_style))
            for note in simplified["study_notes"]:
                story.append(Paragraph(note.get("heading", ""), note_heading_style))
                story.append(Paragraph(_md_bold_to_html(note.get("content", "")), body_style))

        if summary.get("keywords"):
            story.append(Paragraph("Important Keywords", heading_style))
            for kw in summary["keywords"]:
                story.append(Paragraph(f"<b>{kw.get('term', '')}</b>: {kw.get('definition', '')}", body_style))
                story.append(Spacer(1, 4))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()


notes_pdf_service = NotesPDFService()
