"""
stage_3_llm_detect.py — Stage 3: Agent-Based Candidate Detection.

Replaces the fragile regex-based _is_boilerplate() and _rule_score() with a
Claude Haiku agent that evaluates each segmented chunk for:

  1. Is it a real requirement or boilerplate/distractor?
  2. What directive strength does it have? (strong/moderate/none)
  3. Does it contain technical units/measurements?
  4. Does it mention protocols/interfaces?

Output shape matches the existing StageDetect contract:
  (page_num, [(original_text, rule_score)], tables)

Rule score mapping (Haiku returns a 0-10 score):
  5+  = passes (like DIRECTIVE_STRONG search, score >= RULE_THR=4)
  3-4 = may pass if has technical units (like TECH_UNIT_RE, score >= UNIT_ONLY_THR=3)
  <3  = rejected as boilerplate
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    from ..llm_api_handler import llm_request
except ImportError:
    from llm_api_handler import llm_request

try:
    from .stage_3_Detect import StageDetect
except ImportError:
    from stage_3_Detect import StageDetect

# Import the prompts engine
try:
    from ..prompts import prompts
except ImportError:
    from prompts import prompts

try:
    from .constant_data import DEFAULT_LLM_CONCURRENCY
except ImportError:
    from constant_data import DEFAULT_LLM_CONCURRENCY

log = logging.getLogger("Stage_3.LLM_Detect")

DEFAULT_MAX_CHUNKS = 10
LLM_MODEL_OPUS = "opus46"
LLM_MODEL_SONNET = "sonnet46"
LLM_MAX_TOKENS_STAGE_3_SCORE = 4000
LLM_MAX_TOKENS_STAGE_3_VALIDATION = 200
LLM_TEMPERATURE = 0.1
LLM_SYSTEM_PROMPT_STAGE_3 = "stage_3"
LLM_SYSTEM_PROMPT_STAGE_3_VALIDATE = "stage_3_validate"


async def _run_scoring_agent(
    segments: List[str],
    page_num: int,
    semaphore: asyncio.Semaphore,
) -> Optional[List[Dict[str, Any]]]:
    """Stage 1: LLM scores all segments in one call."""
    len_segment = len([segment for segment in segments if segment.strip()])
    user_content = "YOU MUST RETURN EXACTLY A JSON ARRAY. " \
                   f"Input has {len_segment} segments. Output MUST have {len_segment} entries. " \
                   "Entry N matches segment N by position. NO other text, no explanation.\n\n" \
                   "Evaluate each segment:\n\n"
    for index, seg_data in enumerate(segments, 1):
        clean = seg_data.strip()
        if clean:
            user_content += f"{index}. {clean}\n"

    async with semaphore:
        result = await llm_request(
            model=LLM_MODEL_OPUS,
            system_prompt=prompts.render(LLM_SYSTEM_PROMPT_STAGE_3),
            messages=[{"role": "user", "content": user_content}],
            max_tokens=LLM_MAX_TOKENS_STAGE_3_SCORE,
            temperature=LLM_TEMPERATURE,
            fallback_chain=[LLM_MODEL_SONNET],
            # No response_format="json" — it forces json_object mode which makes
            # Claude emit a single dict instead of the expected JSON array.
        )

    if result is None:
        log.info(f"[LLM_Detect] Page {page_num}: Scoring returned None (all retries exhausted)")
        return None
    raw = result.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    bracket_start = raw.find("[")
    bracket_end = raw.rfind("]") + 1
    if bracket_start != -1 and bracket_end > bracket_start:
        raw = raw[bracket_start:bracket_end]

    try:
        batch_results = json.loads(raw)
    except json.JSONDecodeError as e:
        log.info(f"[LLM_Detect] Page {page_num}: Scoring JSON parse error: {e}")
        log.info(f"[LLM_Detect] Page {page_num}: Raw (first 300): {raw[:300]}")
        async with semaphore:
            result = await llm_request(
                model=LLM_MODEL_OPUS,
                system_prompt=prompts.render(LLM_SYSTEM_PROMPT_STAGE_3),
                messages=[{"role": "user", "content": user_content}],
                max_tokens=LLM_MAX_TOKENS_STAGE_3_SCORE,
                temperature=LLM_TEMPERATURE,
                fallback_chain=[LLM_MODEL_SONNET]
            )

        if result is None:
            log.info(f"[LLM_Detect] Page {page_num}: Correction retry returned None")
            return None
        raw = result.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])
        bracket_start = raw.find("[")
        bracket_end = raw.rfind("]") + 1
        if bracket_start != -1 and bracket_end > bracket_start:
            raw = raw[bracket_start:bracket_end]
        batch_results = json.loads(raw)

    if not isinstance(batch_results, list):
        log.info(f"[LLM_Detect] Page {page_num}: Scoring returned non-list type={type(batch_results).__name__}")
        return None

    return batch_results


async def _run_validation_agent(
    segments: List[str],
    scored_results: List[Dict[str, Any]],
    page_num: int,
    semaphore: asyncio.Semaphore,
) -> List[Tuple[str, int]]:
    """Stage 2: LLM validates which segments are ACTUALLY requirements."""
    # Build segment list with LLM scores for context
    user_content = "Which of these segments are ACTUALLY requirements? Return a JSON array of 0-based indices.\n\n"
    for item_num, segment in enumerate(segments):
        clean = segment.strip()
        if not clean:
            continue
        score_info = ""
        if item_num < len(scored_results) and isinstance(scored_results[item_num], dict):
            score_data = scored_results[item_num]
            is_req = score_data.get("isRequirement", "?")
            score = score_data.get("score", "?")
            reason = score_data.get("reason", "")
            score_info = f" [LLM: isReq={is_req}, score={score}, reason: {reason}]"
        user_content += f"{item_num}. {clean}{score_info}\n"

    # log.info(f"[LLM_Detect] [User_content] : {user_content}")

    async with semaphore:
        result = await llm_request(
            model=LLM_MODEL_OPUS,
            system_prompt=prompts.render(LLM_SYSTEM_PROMPT_STAGE_3_VALIDATE),
            messages=[{"role": "user", "content": user_content}],
            max_tokens=LLM_MAX_TOKENS_STAGE_3_VALIDATION,
            temperature=LLM_TEMPERATURE,
            fallback_chain=[LLM_MODEL_SONNET]
        )

    # log.info(f"[LLM_Detect] [PageNum] : {page_num} [Validation Result] : {result}")

    # Extract JSON array
    raw = result.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    bracket_start = raw.find("[")
    bracket_end = raw.rfind("]") + 1
    if bracket_start != -1 and bracket_end > bracket_start:
        raw = raw[bracket_start:bracket_end]

    try:
        pass_indices = json.loads(raw)
    except json.JSONDecodeError:
        log.info(f"[LLM_Detect] Page {page_num}: Validation agent returned non-JSON, using scoring results")
        return _extract_from_scoring(segments, scored_results, page_num)

    if not isinstance(pass_indices, list):
        log.info(f"[LLM_Detect] Page {page_num}: Validation agent returned non-array, using scoring results")
        return _extract_from_scoring(segments, scored_results, page_num)

    # Build passed segments from validated indices
    passed: List[Tuple[str, int]] = []
    for idx in pass_indices:
        try:
            idx = int(idx)
        except (ValueError, TypeError):
            continue
        if 0 <= idx < len(segments) and segments[idx].strip():
            # Get score from scoring results if available
            score = 5  # default
            if idx < len(scored_results) and isinstance(scored_results[idx], dict):
                score = int(round(scored_results[idx].get("score", 5)))
            passed.append((segments[idx].strip(), score))

    # log.info(f"[LLM_Detect] [PageNum] : {page_num} [Passed Results] : {passed}")

    return passed


def _extract_from_scoring(
    segments: List[str],
    scored_results: List[Dict[str, Any]],
    page_num: int = 0,
) -> List[Tuple[str, int]]:
    """Fallback: extract from scoring results if validation fails."""
    passed: List[Tuple[str, int]] = []
    for i, entry in enumerate(scored_results):
        if not isinstance(entry, dict):
            continue
        if not entry.get("isRequirement"):
            continue
        if i < len(segments) and segments[i].strip():
            score = int(round(entry.get("score", 0)))
            log.info(f"[LLM_Detect] Page {page_num} seg {i+1}: PASSED (score={entry.get('score')})")
            passed.append((segments[i].strip(), score))
    return passed


async def detect_with_llm(
    segments: List[str],
    page_num: int,
    semaphore: asyncio.Semaphore,
) -> List[Tuple[str, int]]:
    """
    Two-stage detection: scoring agent + validation agent.

    Stage 1: Scoring LLM assigns per-segment scores (opus46)
    Stage 2: Validation LLM selects only the true requirements (opus46)

    Returns list of (original_text, rule_score) tuples — matching the
    existing StageDetect output contract.
    """
    if not segments:
        return []

    # Stage 1: Scoring
    scored_results = await _run_scoring_agent(segments, page_num, semaphore)
    if scored_results is None:
        log.info(f"[LLM_Detect] [PageNum] {page_num}: Scoring failed, falling back to Default Detect function")
        return []

    # Stage 2: Validation
    validation_result = await _run_validation_agent(segments, scored_results, page_num, semaphore)
    return validation_result


class StageLLMDetect:
    """
    LLM-powered detection stage.

    Replaces StageDetect from stage_3_Detect.py.
    Input:  (page_num, [segments], tables)
    Output: (page_num, [(original_text, rule_score)], tables)
    """
    name = "llm_detect"

    def __init__(self, enable_llm: bool = True):
        self.enable_llm = enable_llm

    async def process(
        self,
        item: Tuple[int, List[str], List[str]],
        context: Dict[str, Any] = None,
    ) -> Tuple[int, List[Tuple[str, int]], List[str]]:
        """
        Gate candidates using LLM detection.

        If enable_llm is True:
          Uses Haiku agent to evaluate each segment concurrently.
        If enable_llm is False:
          Falls back to original regex-based StageDetect.
        """
        page_num, segments, tables = item
        if context is None:
            context = {}
        semaphore = context.get("_llm_semaphore", asyncio.Semaphore(DEFAULT_LLM_CONCURRENCY))

        if self.enable_llm:
            try:
                LLM_response = await detect_with_llm(segments, page_num, semaphore)
            except Exception as e:
                log.error(f"[LLM_Detect] LLM detection failed: {e}, using Default Detect Function")
                LLM_response = await self._Default_Detect_Callback(segments, page_num)
        else:
            LLM_response = await self._Default_Detect_Callback(segments, page_num)

        log.info(f"[LLM_Detect] [PageNum] : {page_num} => {len(LLM_response)} of {len(segments)} Passed")
        return (page_num, LLM_response, tables)

    async def _Default_Detect_Callback(
        self, segments: List[str], page_num: int
    ) -> List[Tuple[str, int]]:
        """Fallback to original regex-based detection."""
        detector = StageDetect()
        try:
            from .constant_data import TECH_UNIT_RE, RULE_THR, UNIT_ONLY_THR
        except ImportError:
            from constant_data import TECH_UNIT_RE, RULE_THR, UNIT_ONLY_THR
        passed: List[Tuple[str, int]] = []
        for seg in segments:
            seg_clean = seg.strip()
            if not seg_clean:
                continue
            if detector._is_boilerplate(seg_clean):
                continue
            rs = detector._rule_score(seg_clean)
            has_unit = bool(TECH_UNIT_RE.search(seg_clean))
            thr = UNIT_ONLY_THR if has_unit else RULE_THR
            if rs >= thr:
                passed.append((seg_clean, rs))
        return passed
