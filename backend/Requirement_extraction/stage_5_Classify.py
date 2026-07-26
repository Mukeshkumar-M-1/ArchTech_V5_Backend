"""
05_Classify.py — Stage 5: Hybrid classification (keyword + semantic embedding).
Combines keyword-bucket matching with SentenceTransformer cosine similarity.
Optionally uses an LLM for higher-accuracy classification.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from sentence_transformers import SentenceTransformer

import numpy as np

try:
    from .constant_data import (
        CAT_ANCHORS, EMBEDDING_MODEL_PATH, KW_BUCKETS,
        _EXECUTOR, DEFAULT_LLM_CONCURRENCY,
    )
except ImportError:
    from constant_data import (
        CAT_ANCHORS, EMBEDDING_MODEL_PATH, KW_BUCKETS,
        _EXECUTOR, DEFAULT_LLM_CONCURRENCY,
    )

try:
    from ..llm_api_handler import llm_request
except ImportError:
    from llm_api_handler import llm_request

try:
    from ..prompts import prompts
except ImportError:
    from prompts import prompts

log = logging.getLogger("Stage_5.Classify")

SEM_CONF_THRESHOLD = 0.55
SEM_CONF_WEIGHT    = 0.7
KW_CONF_WEIGHT     = 0.3

# LLM classification constants
LLM_MODEL_OPUS = "opus46"
LLM_MODEL_HAIKU = "haiku45"
LLM_MAX_TOKENS_STAGE_5 = 256
LLM_TEMPERATURE = 0.1
LLM_SYSTEM_PROMPT_STAGE_5 = "stage_5"

# Shared singleton state (set once by warm_up)
_cat_embs: Dict[str, np.ndarray] | None = None


def warm_up_category_embeddings() -> Dict[str, np.ndarray]:
    """Pre-build category embeddings. Must be called once before classify."""
    global _cat_embs
    if _cat_embs is not None:
        return _cat_embs
    try:
        enc = SentenceTransformer(str(EMBEDDING_MODEL_PATH))
    except Exception as e:
        log.error(f"[Classify] Encoder failed: {e} -- falling back to keywords")
        _cat_embs = {}
        return _cat_embs
    _cat_embs = {
        cat: enc.encode([sentence], show_progress_bar=False)[0]
        for cat, sentence in CAT_ANCHORS.items()
    }
    log.info(f"[Classify] Category embeddings ready ({len(_cat_embs)} classes)")
    return _cat_embs


def _keyword_classify_sync(text: str) -> Tuple[str, float]:
    """Fast keyword-bucket classification. CPU-bound."""
    lower = text.lower()
    best_cat, best_hits = "Functional", 0
    for cat, kws in KW_BUCKETS.items():
        hits = sum(1 for kw in kws if re.search(r'\b' + re.escape(kw) + r'\b', lower))
        if hits > best_hits:
            best_hits, best_cat = hits, cat
    return best_cat, min(best_hits / 3.0, 1.0)


def _semantic_classify_sync(text: str, kw_cat: str) -> Tuple[str, float]:
    """Semantic classification via cosine similarity. CPU-bound."""
    enc = None
    try:
        from sentence_transformers import SentenceTransformer
        from .constant_data import EMBEDDING_MODEL_PATH
        enc = SentenceTransformer(str(EMBEDDING_MODEL_PATH))
    except Exception:
        pass
    if enc is None or _cat_embs is None or len(_cat_embs) == 0:
        return kw_cat, 0.0
    vec = enc.encode([text], show_progress_bar=False)[0]
    best_cat, best_sim = kw_cat, -1.0
    for cat, anchor in _cat_embs.items():
        sim = float(np.dot(vec, anchor) / (np.linalg.norm(vec) * np.linalg.norm(anchor) + 1e-9))
        if sim > best_sim:
            best_sim, best_cat = sim, cat
    return best_cat, max(best_sim, 0.0)


class StageClassify:
    """Hybrid keyword + semantic classification stage."""
    name = "classify"

    def __init__(self, enable_llm: bool = False):
        self.enable_llm = enable_llm

    async def _classify_batch_llm(
        self,
        normalized_texts: List[str],
        semaphore: asyncio.Semaphore,
    ) -> Optional[List[Tuple[str, str, float]]]:
        """Classify ALL segments in a single LLM call (batched).

        Returns list of (category, subcategory, confidence) — one per input text,
        in order. Returns None if LLM call or parsing fails.
        """
        user_content = "YOU MUST RETURN EXACTLY A JSON ARRAY. " \
                       f"Input has {len(normalized_texts)} texts. Output MUST have exactly {len(normalized_texts)} entries. " \
                       "Entry N matches text N by position. NO other text, no explanation.\n\n" \
                       "Classify each text:\n\n"
        for index, text in enumerate(normalized_texts, 1):
            clean = text.strip()
            if clean:
                user_content += f"{index}. {clean}\n"

        async with semaphore:
            result = await llm_request(
                model=LLM_MODEL_OPUS,
                messages=[{"role": "user", "content": user_content}],
                system_prompt=prompts.render(LLM_SYSTEM_PROMPT_STAGE_5),
                max_tokens=LLM_MAX_TOKENS_STAGE_5,
                temperature=LLM_TEMPERATURE,
                fallback_chain=[LLM_MODEL_OPUS],
                response_format="json"
            )

        if result is None:
            log.warning("[Classify] LLM batch classification returned None")
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
            log.warning(f"[Classify] LLM batch JSON parse error: {e}, raw: {raw[:200]}")
            return None

        if not isinstance(batch_results, list) or len(batch_results) != len(normalized_texts):
            log.warning(f"[Classify] LLM batch returned wrong count: got {len(batch_results)}, expected {len(normalized_texts)}")
            return None

        classifications = []
        for entry in batch_results:
            if not isinstance(entry, dict):
                continue
            cat = entry.get("category", "Functional")
            sub = entry.get("subcategory", "General")
            conf = float(entry.get("confidence", 0.0))
            classifications.append((cat, sub, conf))

        return classifications

    async def _classify_text(self, text: str) -> Tuple[str, str, float]:
        """Fallback: keyword + semantic classification only (no LLM)."""
        loop = asyncio.get_event_loop()
        kw_cat, kw_conf = await loop.run_in_executor(_EXECUTOR, _keyword_classify_sync, text)
        sem_cat, sem_conf = await loop.run_in_executor(
            _EXECUTOR, _semantic_classify_sync, text, kw_cat
        )
        if sem_conf > SEM_CONF_THRESHOLD:
            final = sem_cat
            blend = (sem_conf * SEM_CONF_WEIGHT) + (kw_conf * KW_CONF_WEIGHT)
        else:
            final = kw_cat
            blend = (kw_conf * KW_CONF_WEIGHT) + (sem_conf * SEM_CONF_WEIGHT)
        parts = final.split("/", 1)
        return parts[0], parts[1] if len(parts) > 1 else "General", round(blend, 3)

    async def process(
        self,
        item: Tuple[int, List[Tuple[str, int, str]], List[str]],
        context: Dict[str, Any],
    ) -> Tuple[int, List[Tuple[str, str, float, float, str]], List[str]]:
        """Classify each normalized segment using a single batched LLM call.
        Input:  (page_num, [(orig, score, normalized)], tables)
        Output: (page_num, [(category, subcat, sem_conf, kw_conf, orig)], tables)
        """
        page_num, normalized_list, tables = item
        loop = asyncio.get_event_loop()
        semaphore = context.get("_llm_semaphore", asyncio.Semaphore(DEFAULT_LLM_CONCURRENCY))

        results = []
        if self.enable_llm and semaphore is not None:
            # Batch: single LLM call for all segments
            normalized_texts = [norm for _, _, norm in normalized_list]
            batch_results = await self._classify_batch_llm(normalized_texts, semaphore)
            if batch_results is not None and len(batch_results) == len(normalized_list):
                for idx, (_, _, norm) in enumerate(normalized_list):
                    cat, sub, sem_conf = batch_results[idx]
                    _, kw_conf = await loop.run_in_executor(
                        _EXECUTOR, _keyword_classify_sync, norm
                    )
                    results.append((cat, sub, round(sem_conf, 3), round(kw_conf, 3), norm))
                log.info(f"[Classify] {len(results)} classifications (batched LLM) for page {page_num}")
                return (page_num, results, tables)
            else:
                log.warning("[Classify] Batch LLM failed, falling back to per-segment classification")

        # Fallback: classify each segment individually
        for orig, score, norm in normalized_list:
            cat, sub, sem_conf = await self._classify_text(norm)
            _, kw_conf = await loop.run_in_executor(_EXECUTOR, _keyword_classify_sync, norm)
            results.append((cat, sub, sem_conf, kw_conf, orig))

        log.info(f"[Classify] {len(results)} classifications for page {page_num}")
        return (page_num, results, tables)
