"""
02_Segment.py — Stage 2: Smart Text Segmentation.
Merges bullets/numbered lists, splits long paragraphs, detects ToC/cover pages.
Imports patterns from constant_data.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Tuple

try:
    from .constant_data import BULLET_RE, NUMBERED_RE, TOC_LINE_RE, TOC_CONTENT_DATA
except ImportError:
    from constant_data import BULLET_RE, NUMBERED_RE, TOC_LINE_RE, TOC_CONTENT_DATA

log = logging.getLogger("Stage_2.Segment")

MIN_SCORE_TOC_VALID = 0.35 # 35%
MIN_TOC_HITS_COUNT  = 3
MIN_COVERPAGE_LEN   = 10
MIN_COVERPAGE_LINES = 4
MIN_COVERPAGE_PERCENTAGE = 0.60 # 60

class StageSegment:
    """Smart segmentation stage."""
    name = "segment"

    # Check the Page is Table of content or Not
    def _is_toc_page(self, text: str) -> bool:
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return False
        hits = sum(1 for line in lines if TOC_LINE_RE.search(line))
        toc_score = hits / len(lines)

        if toc_score > MIN_SCORE_TOC_VALID:
            return True
        return bool(TOC_CONTENT_DATA.search(text)) and hits >= MIN_TOC_HITS_COUNT

    # Check the Page is Cover Page or Not
    def _is_cover_page(self, text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        length_lines = len(lines)
        if length_lines < MIN_COVERPAGE_LEN:
            return True
        caps = sum(1 for line in lines if line.isupper() or len(line.split()) <= MIN_COVERPAGE_LEN)
        average_caps = caps / len(lines)
        return average_caps > MIN_COVERPAGE_PERCENTAGE

    def _smart_segment(self, text: str) -> List[str]:
        text = text.replace('\r', '').replace('\xa0', ' ')
        paragraphs: List[str] = []
        buffer = ""
        for line in text.split('\n'):
            line = line.rstrip()
            if BULLET_RE.match(line) or NUMBERED_RE.match(line):
                buffer = (buffer.rstrip() + " " + line.strip()) if buffer else line.strip()
                continue
            if not line.strip():
                if buffer.strip():
                    paragraphs.append(buffer.strip())
                    buffer = ""
                continue
            if buffer and len(buffer) > 0 and buffer[0].islower():
                buffer += " " + line.strip()
            else:
                if buffer:
                    paragraphs.append(buffer.strip())
                buffer = line.strip()
        if buffer.strip():
            paragraphs.append(buffer.strip())
        final: List[str] = []
        for para in paragraphs:
            if len(para) > 400:
                final.extend(re.split(r'(?<=[.!?])\s+(?=[A-Z])', para))
            else:
                final.append(para)
        return final

    async def process(self, item: Tuple[int, str, List[str]], context: Dict[str, Any]) -> Tuple[int, List[str], List[str]]:
        """Segment page text into paragraphs.
        Input:  (page_num, raw_text, table_blocks)
        Output: (page_num, [paragraphs], table_blocks)
        """
        page_num, text, tables = item
        if self._is_toc_page(text) or self._is_cover_page(text):
            log.info(f"[Segment] Page {page_num}: skipped (ToC/cover)")
            return (page_num, [], tables)
        segments = self._smart_segment(text)
        log.info(f"[Segment] Page {page_num}: {len(segments)} segments")
        return (page_num, segments, tables)
