"""
03_Detect.py — Stage 3: Candidate Detection (boilerplate gate + rule scoring).
Rejects boilerplate / ToC / cover pages. Scores remaining segments.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Tuple

try:
    from .constant_data import (
        BOILERPLATE_PATTERNS, DIRECTIVE_STRONG, DIRECTIVE_MODERATE,
        PROTOCOLS, TECH_UNIT_RE, RULE_THR, UNIT_ONLY_THR,
    )
except ImportError:
    from constant_data import (
        BOILERPLATE_PATTERNS, DIRECTIVE_STRONG, DIRECTIVE_MODERATE,
        PROTOCOLS, TECH_UNIT_RE, RULE_THR, UNIT_ONLY_THR,
    )

log = logging.getLogger("[Stage_3.Detect]")

DEFAULT_BOILERPLATE_DATA_LENGTH = 5
DEFAULT_MIN_TEXT_LEN = 80
DEFAULT_FIVE = 5
DEFAULT_THREE = 3
DEFAULT_TWO = 2
DEFAULT_ONE = 1

class StageDetect:
    """Boilerplate gate + rule-score stage."""
    name = "detect"

    def _is_boilerplate(self, text: str) -> bool:
        data = text.strip()
        length_data = len(data.strip())
        if length_data < DEFAULT_BOILERPLATE_DATA_LENGTH:
            if not TECH_UNIT_RE.search(data):
                return True
        return any(boiler_data.search(data) for boiler_data in BOILERPLATE_PATTERNS)

    def _rule_score(self, text: str) -> int:
        """Composite score from directive strength, tech units, protocols, length."""
        score = 0
        lower = text.lower()
        if DIRECTIVE_STRONG.search(lower):
            score += DEFAULT_FIVE
        elif DIRECTIVE_MODERATE.search(lower):
            score += DEFAULT_THREE
        if TECH_UNIT_RE.search(text):
            score += DEFAULT_THREE
        if any(p in lower for p in PROTOCOLS):
            score += DEFAULT_TWO
        if "[table data]" in lower:
            score += DEFAULT_THREE
        if len(text.strip()) > DEFAULT_MIN_TEXT_LEN:
            score += DEFAULT_ONE
        if re.search(r'^(the following|this document|this specification|this section)', lower):
            score -= DEFAULT_TWO
        if re.search(r'\b(e\.g\.|i\.e\.|etc\.)\b', lower):
            score -= DEFAULT_ONE
        return score

    async def process(self, item: Tuple[int, List[str], List[str]], context: Dict[str, Any] | None = None) -> Tuple[int, List[Tuple[str, int]], List[str]]:
        """Gate candidates. Returns (page_num, [(original_text, rule_score)], tables)."""
        if context is None:
            context = {}
        page_num, segments, tables = item
        passed: List[Tuple[str, int]] = []
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            if self._is_boilerplate(seg):
                continue
            rs = self._rule_score(seg)
            has_unit = bool(TECH_UNIT_RE.search(seg))
            thr = UNIT_ONLY_THR if has_unit else RULE_THR
            if rs >= thr:
                passed.append((seg, rs))
        log.info(f"[Detect] Page {page_num}: {len(passed)} of {len(segments)} passed gate")
        return (page_num, passed, tables)
