"""
07_Score.py — Stage 7: Scoring, keyword extraction, and ID assignment.
Supports LLM-based keyword extraction with regex/KeyBERT fallback.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    from .constant_data import (
        DIRECTIVE_STRONG, DIRECTIVE_MODERATE, TECH_UNIT_RE,
        DOC_SIGNALS, PREFIX_MAP, CONF_RULE_WEIGHT, CONF_SEM_WEIGHT, CONF_KW_WEIGHT,
        DEFAULT_MAX_KEYWORDS, DEFAULT_YAKE_DEDUP_LIM, DEFAULT_YAKE_TOP_N,
        DEFAULT_MIN_CONFIDENCE, PROTOCOLS, ALL_DOMAIN_KW, KW_BUCKETS,
        _EXECUTOR, DEFAULT_LLM_CONCURRENCY,
    )
except ImportError:
    from constant_data import (
        DIRECTIVE_STRONG, DIRECTIVE_MODERATE, TECH_UNIT_RE,
        DOC_SIGNALS, PREFIX_MAP, CONF_RULE_WEIGHT, CONF_SEM_WEIGHT, CONF_KW_WEIGHT,
        DEFAULT_MAX_KEYWORDS, DEFAULT_YAKE_DEDUP_LIM, DEFAULT_YAKE_TOP_N,
        DEFAULT_MIN_CONFIDENCE, PROTOCOLS, ALL_DOMAIN_KW, KW_BUCKETS,
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

log = logging.getLogger("Stage_7.score")

# LLM scoring constants
LLM_MODEL_OPUS = "opus46"
LLM_MODEL_SONNET = "sonnet46"
LLM_MODEL_HAIKU = "haiku45"
LLM_MAX_TOKENS_STAGE_7 =512
LLM_TEMPERATURE = 0.1
LLM_SYSTEM_PROMPT_STAGE_7 = "stage_7"




async def _llm_extract_keywords_sync(
    text: str,
    semaphore: asyncio.Semaphore,
) -> Optional[Dict[str, Any]]:
    """Call LLM to extract keywords and confidence from requirement text."""
    async with semaphore:
        result = await llm_request(
            model=LLM_MODEL_OPUS,
            messages=[{"role": "user", "content": text}],
            system_prompt=prompts.render(LLM_SYSTEM_PROMPT_STAGE_7),
            max_tokens=LLM_MAX_TOKENS_STAGE_7,
            temperature=LLM_TEMPERATURE,
            fallback_chain=[LLM_MODEL_OPUS],
            response_format="json"
        )

    if result is None:
        return None

    raw = result.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    else:
        bracket_start = raw.find("{")
        bracket_end = raw.rfind("}") + 1
        if bracket_start != -1 and bracket_end > bracket_start:
            raw = raw[bracket_start:bracket_end]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning(f"[Score] LLM JSON parse error: {e}, raw: {raw[:200]}")
        return None

    if not isinstance(data, dict):
        log.warning(f"[Score] LLM returned non-dict: {type(data).__name__}")
        return None

    return data


class StageScore:
    """Score, extract keywords, assign IDs, produce final requirement dicts."""
    name = "score"

    def _extract_keywords_sync(self, text: str, max_kw: int = DEFAULT_MAX_KEYWORDS) -> List[str]:
        """Extract keywords: protocol/domain match -> KeyBERT -> YAKE fallback."""
        keywords: List[str] = []
        lower = text.lower()

        # Protocol/domain match (fast, sync)
        for kw in sorted(PROTOCOLS | ALL_DOMAIN_KW):
            if re.search(r'\b' + re.escape(kw) + r'\b', lower):
                keywords.append(kw)
                if len(keywords) >= max_kw:
                    break

        # KeyBERT
        try:
            from keybert import KeyBERT
            from .constant_data import EMBEDDING_MODEL_PATH
            kb = KeyBERT(model=EMBEDDING_MODEL_PATH)
            if len(keywords) < max_kw:
                raw = kb.extract_keywords(text, keyphrase_ngram_range=(1, 2),
                                          top_n=6, stop_words="english")
                for kw, _ in raw:
                    clean = kw.lower().strip()
                    if len(clean) > 2 and clean not in keywords:
                        keywords.append(clean)
                        if len(keywords) >= max_kw:
                            break
        except Exception:
            pass

        # YAKE fallback
        try:
            import yake as _yake
            if not any(kw in KW_BUCKETS.get("Functional", []) for kw in keywords):
                yk = _yake.KeywordExtractor(lan="en", n=3, dedupLim=DEFAULT_YAKE_DEDUP_LIM, top_n=DEFAULT_YAKE_TOP_N, features=None)
                for kw, _ in yk.extract_keywords(text)[:10]:
                    clean = kw.lower().strip()
                    if len(clean) > 3 and clean not in keywords:
                        keywords.append(clean)
                        if len(keywords) >= max_kw:
                            break
        except Exception:
            pass

        return list(dict.fromkeys(keywords))[:max_kw]

    def __init__(self, enable_llm: bool = False):
        self.enable_llm = enable_llm

    async def process(
        self,
        item: Tuple[int, List[Tuple[str, str, float, float, str, str]], List[str]],
        context: Dict[str, Any],
    ) -> List[Tuple[int, List[Dict[str, Any]], List[str]]]:
        """Score, extract keywords, assign IDs, produce final requirement dicts.
        Input:  (page_num, [(cat, sub, sem_conf, kw_conf, orig, expl)], tables)
        Output: [(page_num, [req_dicts], tables)]
        """
        if context is None:
            context = {}
        page_num, classified_list, tables = item
        min_conf = context.get("min_confidence", DEFAULT_MIN_CONFIDENCE)
        id_lock = context.get("_id_lock", asyncio.Lock())
        counters = context.get("_counters", {})
        doc_type = context.get("doc_type", "TechSpec")
        semaphore = context.get("_llm_semaphore", asyncio.Semaphore(DEFAULT_LLM_CONCURRENCY))

        results: List[Dict[str, Any]] = []
        loop = asyncio.get_event_loop()

        for cat, sub, sem_conf, kw_conf, orig, expl in classified_list:
            keywords: List[str] = []
            llm_confidence: Optional[float] = None

            # Try LLM keyword extraction first
            if self.enable_llm:
                llm_result = await _llm_extract_keywords_sync(orig, semaphore)
                if llm_result is not None:
                    keywords = [
                        kw.lower().strip()
                        for kw in llm_result.get("keywords", [])
                        if len(kw.strip()) > 2
                    ][:DEFAULT_MAX_KEYWORDS]
                    llm_confidence = llm_result.get("confidence")

            # Fallback: regex/KeyBERT/YAKE
            if not keywords:
                keywords = await loop.run_in_executor(
                    _EXECUTOR, self._extract_keywords_sync, orig
                )

            # Confidence score
            rule_norm = min(kw_conf / 10.0, 1.0)
            if llm_confidence is not None:
                conf = (rule_norm * CONF_RULE_WEIGHT) + (llm_confidence * CONF_SEM_WEIGHT)
            else:
                conf = (rule_norm * CONF_RULE_WEIGHT) + (sem_conf * CONF_SEM_WEIGHT) + (kw_conf * CONF_KW_WEIGHT)

            if any(kw in orig.lower() for kw in DOC_SIGNALS.get(doc_type, [])):
                conf += 0.05
            conf = round(min(conf, 1.0), 3)

            if conf < min_conf:
                continue

            # Assign ID under lock
            pfx = PREFIX_MAP.get(cat, "REQ")
            async with id_lock:
                counters[pfx] = counters.get(pfx, 0) + 1
                req_id = f"{pfx}-{counters[pfx]:04d}"

            results.append({
                "id": req_id,
                "type": doc_type,
                "category": cat,
                "sub_category": sub,
                "priority": "High" if DIRECTIVE_STRONG.search(orig) else "Normal",
                "text": orig,
                "source": context.get("doc_name", ""),
                "page": page_num,
                "keywords": keywords,
                "extracted_at": datetime.datetime.now().isoformat(),
                "confidence": conf,
                "explanation": expl,
                "has_unit": bool(TECH_UNIT_RE.search(orig)),
                "has_directive": bool(DIRECTIVE_STRONG.search(orig) or DIRECTIVE_MODERATE.search(orig)),
                "char_count": len(orig),
                "rule_score": kw_conf,
                "related_ids": [],
            })

        return [(page_num, results, tables)]
