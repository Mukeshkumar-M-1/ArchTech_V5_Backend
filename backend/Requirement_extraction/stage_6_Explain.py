"""
06_Explain.py — Stage 6: Explanation generation.
Adds human-readable explanations to each classified segment.
Supports batched LLM-based explanations with regex-based fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    from .constant_data import DIRECTIVE_STRONG, DIRECTIVE_MODERATE, DEFAULT_LLM_CONCURRENCY
except ImportError:
    from constant_data import DIRECTIVE_STRONG, DIRECTIVE_MODERATE, DEFAULT_LLM_CONCURRENCY

try:
    from ..llm_api_handler import llm_request
except ImportError:
    from llm_api_handler import llm_request

try:
    from ..prompts import prompts
except ImportError:
    from prompts import prompts

log = logging.getLogger("Stage_6.explain")

# LLM explanation constants
LLM_MODEL_OPUS = "opus46"
LLM_MODEL_SONNET = "sonnet46"
LLM_MODEL_HAIKU = "haiku45"
LLM_MAX_TOKENS_STAGE_6 = 4096
LLM_TEMPERATURE = 0.1
LLM_SYSTEM_PROMPT_STAGE_6 = "stage_6"


class StageExplain:
    """Generate explanations for classified requirements."""
    name = "explain"

    def __init__(self, enable_llm: bool = False):
        self.enable_llm = enable_llm

    async def _explain_batch_llm(
        self,
        classified_items: List[Tuple[str, str, str]],
        semaphore: asyncio.Semaphore,
    ) -> Optional[List[str]]:
        """Generate explanations for ALL segments in a single LLM call (batched).

        Input:  [(category, subcategory, orig), ...]
        Output: [explanation_text, ...] — one per item, in order.
        Returns None if LLM call or parsing fails.
        """
        input_parts = []
        for idx, (cat, sub, orig) in enumerate(classified_items, 1):
            clean = orig.strip()
            input_parts.append(f"{idx}. {cat}/{sub} — \"{clean}\"")

        system_prompt = prompts.render(LLM_SYSTEM_PROMPT_STAGE_6)
        user_content = "\n".join(input_parts)

        async with semaphore:
            result = await llm_request(
                model=LLM_MODEL_OPUS,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                max_tokens=LLM_MAX_TOKENS_STAGE_6,
                temperature=LLM_TEMPERATURE,
                fallback_chain=[LLM_MODEL_OPUS],
                response_format="json"
            )

        if result is None:
            log.warning("[Explain] LLM batch explanation returned None")
            return None

        raw = result.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])
        else:
            bracket_start = raw.find("[")
            bracket_end = raw.rfind("]") + 1
            if bracket_start != -1 and bracket_end > bracket_start:
                raw = raw[bracket_start:bracket_end]

        try:
            batch_results = json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning(f"[Explain] LLM batch JSON parse error: {e}, raw: {raw[:200]}")
            return None

        if not isinstance(batch_results, list) or len(batch_results) != len(classified_items):
            log.warning(f"[Explain] LLM batch returned wrong count: got {len(batch_results)}, expected {len(classified_items)}")
            return None

        explanations = []
        for entry in batch_results:
            if isinstance(entry, dict):
                parts = []
                for key, value in entry.items():
                    if isinstance(value, list):
                        data = " ".join(str(v) for v in value if v is not None)
                    else:
                        data = str(value).strip()
                    if data:
                        parts.append(data)
                expl = "\n\n".join(parts)
                
            elif isinstance(entry, str):
                expl = entry.strip()
            else:
                continue
            if expl:
                explanations.append(expl)
                # log.info(f"[Explain] [Content] {explanations}")

        return explanations if len(explanations) == len(classified_items) else None

    async def _explain_single(
        self,
        category: str,
        subcategory: str,
        orig: str,
        semaphore: asyncio.Semaphore,
    ) -> Optional[str]:
        """Fallback: explain a single segment with LLM."""
        user_content = (
            f"category={category}, subcategory={subcategory}\n"
            f"text: \"{orig}\"\n"
        )
        async with semaphore:
            result = await llm_request(
                model=LLM_MODEL_OPUS,
                messages=[{"role": "user", "content": user_content}],
                system_prompt=prompts.render(LLM_SYSTEM_PROMPT_STAGE_6),
                max_tokens=LLM_MAX_TOKENS_STAGE_6,
                temperature=LLM_TEMPERATURE,
                fallback_chain=[LLM_MODEL_OPUS],
            )

        if result is None:
            return None

        raw = result.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]).strip()

        # If LLM wraps in a JSON object with explanation fields
        field_order = ["meaning", "components", "parameters", "purpose"]
        if raw.startswith("{"):
            try:
                data = json.loads(raw)
                parts = []
                for field in field_order:
                    raw_val = data.get(field, "")
                    value = " ".join(raw_val) if isinstance(raw_val, list) else str(raw_val).strip()
                    if value:
                        parts.append(value)
                if parts:
                    return "\n\n".join(parts) or None
                expl_val = data.get("explanation", raw)
                return (" ".join(expl_val) if isinstance(expl_val, list) else str(expl_val).strip()) or None
            except json.JSONDecodeError:
                return raw or None

        return raw or None

    def _explain_regex(self, cat: str, sub: str, orig: str, kw_conf: Any) -> str:
        """Regex-based fallback explanation."""
        kw_str = kw_conf
        if isinstance(kw_conf, str):
            kw_words = kw_conf.split()[:3] if kw_conf else ["embedded", "domain", "terms"]
            kw_str = ", ".join(kw_words)
        elif isinstance(kw_conf, (list, tuple)):
            kw_str = ", ".join(str(k) for k in kw_conf[:3])

        if "[TABLE DATA]" in orig:
            return f"Structured specification table for {sub.lower()} parameters ({kw_str})."

        verb = (
            "mandates" if DIRECTIVE_STRONG.search(orig)
            else "specifies" if DIRECTIVE_MODERATE.search(orig)
            else "describes"
        )
        expl_map = {
            "Hardware": f"This {sub.lower()} requirement {verb} measurable hardware parameters ({kw_str}).",
            "Software": f"This {sub.lower()} requirement {verb} software/firmware behaviour ({kw_str}).",
            "Non-Functional": f"This {sub.lower()} quality attribute {verb} system constraints ({kw_str}).",
            "Functional": f"This functional requirement {verb} system behaviour involving ({kw_str}).",
        }
        return expl_map.get(cat, f"This requirement {verb} system behaviour ({kw_str}).")

    async def process(
        self,
        item: Tuple[int, List[Tuple[str, str, float, float, str]], List[str]],
        context: Dict[str, Any],
    ) -> Tuple[int, List[Tuple[str, str, float, float, str, str]], List[str]]:
        """Add explanation to each classified segment.
        Input:  (page_num, [(category, subcat, sem_conf, kw_conf, orig)], tables)
        Output: (page_num, [(category, subcat, sem_conf, kw_conf, orig, explanation)], tables)
        """
        if context is None:
            context = {}
        page_num, classified_list, tables = item
        semaphore = context.get("_llm_semaphore", asyncio.Semaphore(DEFAULT_LLM_CONCURRENCY))

        results = []
        if self.enable_llm:
            # Batch: single LLM call for all segments
            classified_items = [
                (cat, sub, orig) for cat, sub, _, _, orig in classified_list
            ]
            explanations = await self._explain_batch_llm(classified_items, semaphore)
            if explanations is not None:
                for (cat, sub, sem_conf, kw_conf, orig), expl in zip(classified_list, explanations):
                    results.append((cat, sub, sem_conf, kw_conf, orig, expl))
                log.info(f"[Explain] {len(results)} explanations (batched LLM) for page {page_num}")
                return (page_num, results, tables)
            else:
                log.warning("[Explain] Batch LLM failed, falling back to per-segment explanation")
                # Try individual LLM calls as intermediate fallback
                for cat, sub, sem_conf, kw_conf, orig in classified_list:
                    expl = await self._explain_single(cat, sub, orig, semaphore)
                    if expl is not None:
                        results.append((cat, sub, sem_conf, kw_conf, orig, expl))
                        continue
                    results.append((cat, sub, sem_conf, kw_conf, orig, self._explain_regex(cat, sub, orig, kw_conf)))

                if results:
                    log.info(f"[Explain] {len(results)} explanations (individual LLM fallback) for page {page_num}")
                    return (page_num, results, tables)

        # Final fallback: regex-based only
        for cat, sub, sem_conf, kw_conf, orig in classified_list:
            expl = self._explain_regex(cat, sub, orig, kw_conf)
            results.append((cat, sub, sem_conf, kw_conf, orig, expl))

        log.info(f"[Explain] {len(results)} explanations for page {page_num}")
        return (page_num, results, tables)
