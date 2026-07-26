"""
04_Normalize.py — Stage 4: Text Normalization.
Converts modal verbs to 'shall', removes ambiguous qualifiers, optional LLM batch.
"""

from __future__ import annotations

import logging
import re
import asyncio 
from typing import Any, Dict, List, Tuple

try:
    from .constant_data import (
        MODAL_RE, AMBIG_RE, DIRECTIVE_STRONG, DEFAULT_BATCH_SIZE,
        DEFAULT_LLM_CONCURRENCY,
    )
except ImportError:
    from constant_data import (
        MODAL_RE, AMBIG_RE, DIRECTIVE_STRONG, DEFAULT_BATCH_SIZE,
        DEFAULT_LLM_CONCURRENCY,
    )

# Import the prompts engine
try:
    from ..prompts import prompts
except ImportError:
    from prompts import prompts

try:
    from ..llm_api_handler import llm_request
except ImportError:
    from llm_api_handler import llm_request

try:
    from ..system_config import NORMALIZATION_ENABLE_LLM
except ImportError:
    try:
        from system_config import NORMALIZATION_ENABLE_LLM
    except ImportError:
        NORMALIZATION_ENABLE_LLM = False

log = logging.getLogger("Stage_4.Normalize")


# ─── Constants ────────────────────────────────────────────────────────────────
LLM_MODEL_OPUS = "opus46"
LLM_MODEL_HAIKU = "haiku45"
LLM_MODEL_SONNET = "sonnet46"
LLM_MAX_TOKENS_NORMALIZE = 512
LLM_TEMPERATURE = 0.1
LLM_SYSTEM_PROMPT_NORMALIZE = "stage_4_normalize"

def _get_formalize_prompt() -> str:
    return prompts.render(LLM_SYSTEM_PROMPT_NORMALIZE)


def _normalize_local(text: str) -> str:
    """Fast regex-based normalization -- no LLM needed."""
    if "[TABLE DATA]" in text:
        return text
    if not DIRECTIVE_STRONG.search(text):
        text = MODAL_RE.sub('shall', text)
    text = AMBIG_RE.sub('', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return (text[0].upper() + text[1:]) if text else text


class StageNormalize:
    """Normalize detected candidates to formal requirement language."""
    name = "normalize"

    async def process(
        self,
        item: Tuple[int, List[Tuple[str, int]], List[str]],
        context: Dict[str, Any] | None = None,
    ) -> Tuple[int, List[Tuple[str, int, str]], List[str]]:
        """Normalize segments.
        Input:  (page_num, [(orig, score)], tables)
        Output: (page_num, [(orig, score, normalized)], tables)
        """
        if context is None:
            context = {}
        page_num, passed, tables = item
        
        if NORMALIZATION_ENABLE_LLM:
            llm_sem = context.get("_llm_semaphore", asyncio.Semaphore(DEFAULT_LLM_CONCURRENCY))
            batch_size = context.get("batch_size", DEFAULT_BATCH_SIZE)
            normalized_list: List[str] = []

            for i in range(0, len(passed), batch_size):
                batch = passed[i:i + batch_size]
                batch_texts = [s for s, _ in batch]
                results = []

                # log.info(f"[LLM_Normalize] [PageNum]: {page_num} [Batch_Text] : {batch_texts}")

                for text in batch_texts:
                    if llm_sem:
                        async with llm_sem:
                            try:
                                result = await llm_request(
                                    model=LLM_MODEL_OPUS,
                                    system_prompt=_get_formalize_prompt(),
                                    messages=[{"role": "user", "content": text}],
                                    max_tokens=LLM_MAX_TOKENS_NORMALIZE,
                                    temperature=LLM_TEMPERATURE,
                                    fallback_chain=[LLM_MODEL_SONNET, LLM_MODEL_OPUS],
                                    response_format="json"
                                )
                                norm_text = result.strip() if result and result.strip() else None
                            except Exception:
                                norm_text = None

                            results.append(norm_text or _normalize_local(text))
                    else:
                        results.append(_normalize_local(text))

                normalized_list.extend(results)

                # log.info(f"[LLM_Normalize] [PageNum]: {page_num} [Result] : {results}")
        else:
            normalized_list = [_normalize_local(s) for s, _ in passed]

        result: List[Tuple[str, int, str]] = [
            (orig, score, norm) for (orig, score), norm in zip(passed, normalized_list)
        ]
        return (page_num, result, tables)
