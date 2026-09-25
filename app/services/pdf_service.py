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
    Renders a lecture's Simplified Notes (dynamic sections, flowcharts,
    real video-frame visuals), Summary, and Key Points into a single
    downloadable, print-friendly PDF, so students can study offline.
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
        mono_style = ParagraphStyle("MonoStyle", parent=styles["BodyText"], fontName="Courier", fontSize=9, leading=13, textColor=colors.HexColor("#334155"))

        story = []
        story.append(Paragraph("AccessLearn AI &mdash; AI Video Learning Notes", brand_style))
        story.append(Paragraph(lecture_title or simplified.get("title") or "Lecture Notes", title_style))
        story.append(Spacer(1, 10))

        if summary.get("shortSummary"):
            story.append(Paragraph("Executive Summary", heading_style))
            story.append(Paragraph(summary["shortSummary"], body_style))

        if key_points:
            story.append(Paragraph("Key Takeaways", heading_style))
            items = [ListItem(Paragraph(_md_bold_to_html(kp), body_style)) for kp in key_points]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=16))

        # Simplified Notes: dynamic per-video sections, each with its own
        # optional flowchart (accessible text form, for a print medium) and
        # optional real video-frame visual -- grounded content, not a fixed
        # template (Section 6 of the brief).
        sections = simplified.get("sections") or []
        if sections:
            story.append(Paragraph("Simplified Notes", heading_style))
            for section in sections:
                story.append(Paragraph(section.get("heading", ""), note_heading_style))
                story.append(Paragraph(_md_bold_to_html(section.get("content", "")), body_style))

                visual_path = section.get("visualFramePath")
                if visual_path and Path(visual_path).exists():
                    try:
                        rl_img = RLImage(visual_path, width=2.6 * inch, height=1.6 * inch)
                        story.append(Spacer(1, 4))
                        story.append(rl_img)
                        if section.get("visualCaption"):
                            story.append(Paragraph(section["visualCaption"], caption_style))
                    except Exception as e:
                        logger.warning(f"Skipping visual in PDF ({visual_path}): {e}")

                flowchart = section.get("flowchart")
                if flowchart:
                    story.append(Spacer(1, 6))
                    story.append(Paragraph(f"<b>{flowchart.get('title', 'Process Flowchart')}</b>", body_style))
                    story.append(Paragraph(
                        (flowchart.get("accessibleText", "") or "").replace("\n", "<br/>"),
                        mono_style,
                    ))
                story.append(Spacer(1, 8))

        if summary.get("detailedSummary"):
            story.append(Paragraph("Detailed Summary", heading_style))
            story.append(Paragraph(summary["detailedSummary"], body_style))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()


notes_pdf_service = NotesPDFService()
