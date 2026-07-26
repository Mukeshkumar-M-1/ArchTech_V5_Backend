"""
stage_2_llm_segment.py — Stage 2: Agentic PDF Text Segmentation.

Replaces the heuristic-only _smart_segment / _is_toc_page / _is_cover_page
with an LLM agent that understands semantic relationships in raw PDF text.

Flow:
  1. Haiku (fast, cheap) tries to segment the page and return JSON chunks.
  2. If Haiku's JSON output is malformed or confidence is low → Sonnet retries.
  3. If both LLM calls fail → falls back to the original heuristic pipeline.

Uses llm_api_handler.py for:
  - Provider-based model resolution (claude-haiku-4-5 format)
  - Retry with exponential backoff
  - Empty-content retry detection
  - Model fallback chain (Haiku → Sonnet → Opus)

Output shape matches the existing StageSegment contract:
  (page_num, [segments], tables)
"""

from __future__ import annotations

import json
import re
import logging
import asyncio
from typing import Any, Dict, List, Tuple, Optional

# Use CCB-style API handler for all LLM calls
try:
    from ..llm_api_handler import (
        llm_request
    )
except ImportError:
    from llm_api_handler import (
        llm_request
    )

try:
    from .constant_data import DEFAULT_LLM_CONCURRENCY
except ImportError:
    from constant_data import DEFAULT_LLM_CONCURRENCY

try:
    from .stage_2_Segment import StageSegment
except ImportError:
    from stage_2_Segment import StageSegment

# Import the prompts engine
try:
    from ..prompts import prompts
except ImportError:
    from prompts import prompts

log = logging.getLogger(__name__)


# ─── Segmentation result type ─────────────────────────────────────────────────
LLMSegmentResult = Dict[str, Any]

# Default Datas
LLM_MODEL_OPUS = "opus46"
LLM_MODEL_SONNET = "sonnet46"
LLM_MAX_TOKENS_STAGE_2 = 4096
LLM_TEMPERATURE = 0.1
LLM_SYSTEM_PROMPT_STAGE_2 = "stage_2"


def _parse_llm_output(raw: str, page_num: int = 0) -> Optional[LLMSegmentResult]:
    """
    Parse LLM text output into a validated SegmentationResult.
    Returns None if the output is not valid JSON or missing required fields.

    Mirrors CCB's response validation — strips markdown fences, validates schema.
    """
    raw = raw.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning(f"[LLM_Segment] Page {page_num}: JSON decode error: {e}. Raw (first 300 chars): {raw[:300]}")
        return None

    # Validate required fields
    if not isinstance(data, dict):
        log.warning(f"[LLM_Segment] Page {page_num}: Expected dict, got {type(data).__name__}")
        return None
    if "isCoverPage" not in data:
        log.warning(f"[LLM_Segment] Page {page_num}: Missing 'isCoverPage'. Keys: {list(data.keys())}")
        return None
    if "chunks" not in data:
        log.warning(f"[LLM_Segment] Page {page_num}: Missing 'chunks'. Keys: {list(data.keys())}")
        return None
    if not isinstance(data["chunks"], list):
        log.warning(f"[LLM_Segment] Page {page_num}: 'chunks' is not a list, got {type(data['chunks']).__name__}")
        return None

    # Validate each chunk has required fields
    for i, chunk in enumerate(data["chunks"]):
        if not isinstance(chunk, dict):
            log.warning(f"[LLM_Segment] Page {page_num}: chunk[{i}] is not a dict, got {type(chunk).__name__}")
            return None
        if "text" not in chunk:
            log.warning(f"[LLM_Segment] Page {page_num}: chunk[{i}] missing 'text'. Keys: {list(chunk.keys())}")
            return None
        # Sanitize text
        chunk["text"] = chunk["text"].strip()
        if not chunk["text"]:
            chunk["text"] = ""

    return data


async def segment_page_with_llm(
    raw_text: str,
    page_num: int,
    semaphore: asyncio.Semaphore,
    tables: Any
) -> LLMSegmentResult:
    """
    Segment a single page of raw PDF text using Haiku with Sonnet fallback.

    Uses llm_api_handler.llm_request() which handles:
      - Model name resolution
      - Retry with exponential backoff on empty responses
      - Model fallback chain (Haiku → Sonnet → Opus)

    Returns a dict with keys:
      - isCoverPage (bool)
      - isTocPage (bool)
      - chunks (list of {text, type, originalLineRange})
    """
    log.info(f"[LLM_Segment] Page {page_num}: attempting LLM segmentation...")

    if tables is not None:
        user_content = f"Raw Text : {raw_text}\n\n Table Data (clear view for content): {tables}"
    else:
        user_content = raw_text


    async with semaphore: 
        llm_response = await llm_request(
            model=LLM_MODEL_OPUS,
            system_prompt=prompts.render(LLM_SYSTEM_PROMPT_STAGE_2),
            messages=[{"role": "user", "content": user_content}],
            max_tokens=LLM_MAX_TOKENS_STAGE_2,
            temperature=LLM_TEMPERATURE,
            fallback_chain=[LLM_MODEL_SONNET],
            response_format="json"
        )
        parsed = _parse_llm_output(llm_response, page_num) if llm_response else None
        # parsed = llm_response
        if parsed:
            log.info(f"[LLM_Segment] chunk_text : {parsed}")
            return parsed
        log.info(f"[LLM_Segment] Page {page_num}: Failed (result={llm_response is not None}, parsed={parsed is not None})")

        
    log.info(f"[LLM_Segment] Page {page_num}: Failed (result={llm_response is not None}, parsed={parsed is not None})")

    # Step 3: Both LLM calls failed — heuristic fallback
    log.warning(f"[LLM_Segment] Page {page_num}: LLM models failed, using Default Segment fallback")
    return _Default_Segment_fallback(raw_text, page_num)


def _Default_Segment_fallback(raw_text: str, page_num: int) -> LLMSegmentResult:
    """
    Deterministic fallback when LLM calls are unavailable.
    Uses the original regex-based heuristics.
    """
    try:
        segment = StageSegment()
        is_toc = segment._is_toc_page(raw_text)
        is_cover = segment._is_cover_page(raw_text)
        segments = segment._smart_segment(raw_text)

    except Exception as e:
        log.error(f"[LLM_Segment] Default Segment fallback failed: {e}")
        segments = [raw_text.strip()]
        is_toc = False
        is_cover = False

    return {
        "isCoverPage": is_cover,
        "isTocPage": is_toc,
        "chunks": [
            {"text": seg, "type": "requirement", "originalLineRange": [0, 0]}
            for seg in segments
            if seg.strip()
        ],
    }


class StageLLM_Segment:
    """
    Haiku-powered segmentation stage.

    Replaces StageSegment from stage_2_Segment.py.
    Input:  (page_num, raw_text, table_blocks)
    Output: (page_num, [segments], table_blocks)
    """

    def __init__(self, enable_llm: bool = True):
        self.enable_llm = enable_llm

    async def process(
        self,
        item: Tuple[int, str, List[str]],
        context: Dict[str, Any] = None,
    ) -> Tuple[int, List[str], List[str]]:
        """
        Segment page text into semantic chunks.

        If enable_llm is True:
          1. Call Haiku → Sonnet fallback for LLM-powered segmentation
          2. If both fail → heuristic fallback
        If enable_llm is False:
          Uses original StageSegment (regex-only heuristics).
        """
        page_num, text, tables = item
        if context is None:
            context = {}
        semaphore = context.get("_llm_semaphore", asyncio.Semaphore(DEFAULT_LLM_CONCURRENCY))


        if self.enable_llm:
            # LLM-powered segmentation (Haiku → Sonnet → heuristic fallback)
            llm_response = await segment_page_with_llm(text, page_num=page_num, semaphore=semaphore, tables=tables)
            is_toc = llm_response.get("isTocPage", False)
            is_cover = llm_response.get("isCoverPage", False)

            if is_toc or is_cover:
                log.info(f"[LLM_Segment] Page {page_num}: skipped (ToC/cover)")
                return (page_num, [], tables)

            # Extract chunks as plain text strings (matches existing pipeline contract)
            segments = [
                chunk["text"]
                for chunk in llm_response.get("chunks", [])
                if chunk.get("text", "").strip()
            ]
            log.info(f"[LLM_Segment] Page {page_num}: {len(segments)} segments")
            return (page_num, segments, tables)
