"""
01_Ingest.py — Stage 1: PDF ingestion.
Extracts text + tables per page. Handles OCR fallback.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

REDUCE_FRAME_PX_START = 0
REDUCE_FRAME_PX_END   = 60
MINIMUM_TEXT_CHAR_EXTRACT  = 50

class StageIngest:
    """Ingest PDF pages -> [(page_num, text, tables)]."""
    name = "ingest"

    def __init__(self, page_limit: Optional[int] = None):
        self._page_limit = page_limit

    def _ingest_page(self, page, page_num: int) -> Tuple[str, List[str]]:
        page_width, page_height = page.width, page.height
        
        crop = page.within_bbox((REDUCE_FRAME_PX_START, REDUCE_FRAME_PX_END, page_width, page_height - REDUCE_FRAME_PX_END))
        text = crop.extract_text() or ""
        length_text = len(text.strip())
        # log.info(f"[Ingest] Width: {page_width}, Height : {page_height}")
        # log.info(f"[Ingest] Page_Num : {page_num} Text : {text} \n\n Text Length : {len(text.strip())} \n")

        # OCR fallback
        if length_text < MINIMUM_TEXT_CHAR_EXTRACT:
            try:
                import pytesseract
                img = crop.to_image(resolution=300).original
                ocr = pytesseract.image_to_string(img)
                if ocr.strip():
                    text = ocr
                    log.info(f"[Ingest] [OCR] Page_Num : {page_num} Text : {text} \n\n Text Length : {len(text.strip())} \n")
            except Exception:
                pass
        table_blocks: List[str] = []
        try:
            for table in crop.extract_tables():
                rows = []
                for row in table:
                    cells = [str(c).replace('\n', ' ').strip() for c in row if c is not None]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    table_blocks.append("\n".join(rows))
        except Exception:
            pass
        return text, table_blocks

    async def process(self, pdf_path: str, context: Dict[str, Any] | None = None) -> List[Tuple[int, str, List[str]]]:
        import pdfplumber
        if context is None:
            context = {}
        pages: List[Tuple[int, str, List[str]]] = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    if self._page_limit and page_num > self._page_limit:
                        log.info(f"[Ingest] Stopped at page {self._page_limit}")
                        break
                    text, tables = self._ingest_page(page, page_num=page_num)
                    pages.append((page_num, text, tables))
                    page.flush_cache()
        except Exception as exc:
            log.error(f"[Ingest] PDF read error: {exc}")
            return []
        context["_ingest_count"] = len(pages)
        log.info(f"[Ingest] {len(pages)} pages loaded from {Path(pdf_path).name}")
        return pages
