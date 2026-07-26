"""
08_Dedup.py — Stage 8: Global deduplication + semantic linking.
Uses rapidfuzz for fast text dedup, sentence-transformers for semantic linking,
with optional LLM-based dedup for ambiguous cases.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from ..llm_api_handler import llm_request
except ImportError:
    from llm_api_handler import llm_request

try:
    from ..prompts import prompts
except ImportError:
    from prompts import prompts

# Import embedding model path
try:
    from .constant_data import EMBEDDING_MODEL_PATH, _EXECUTOR
except ImportError:
    from constant_data import EMBEDDING_MODEL_PATH, _EXECUTOR

log = logging.getLogger("Stage_8.dedup")

# LLM dedup constants
LLM_MODEL_OPUS = "opus46"
LLM_MODEL_FALLBACK_DEDUP = "sonnet46"
LLM_MAX_TOKENS_STAGE_8 = 80
LLM_TEMPERATURE = 0.1
LLM_SYSTEM_PROMPT_STAGE_8 = "stage_8"

# Semantic linking threshold (cosine similarity)
# causing near-duplicates at low thresholds. 0.90 ensures we only link truly
# similar requirements (same meaning, different wording).
SEM_LINK_THRESHOLD = 0.95
# Embedding model cache
_emb_model = None


def _get_embedding_model():
    """Lazy-load sentence-transformers model (reuses stage 5's loaded model)."""
    global _emb_model
    if _emb_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _emb_model = SentenceTransformer(str(EMBEDDING_MODEL_PATH))
            log.info("[Dedup] Embedding model loaded for semantic linking")
        except Exception as e:
            log.warning(f"[Dedup] Embedding model failed to load: {e}")
    return _emb_model


async def _llm_check_duplicate_sync(
    text_a: str,
    text_b: str,
    semaphore: asyncio.Semaphore,
) -> Optional[bool]:
    """Call LLM to check if two requirements are duplicates."""
    user_content = f"Req A: \"{text_a}\"\n\nReq B: \"{text_b}\"\n\nAre these the same requirement?"
    async with semaphore:
        result = await llm_request(
            model=LLM_MODEL_OPUS,
            messages=[{"role": "user", "content": user_content}],
            system_prompt=prompts.render(LLM_SYSTEM_PROMPT_STAGE_8),
            max_tokens=LLM_MAX_TOKENS_STAGE_8,
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
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    is_dup = data.get("is_duplicate", False)
    return bool(is_dup)


class StageDedup:
    """Global deduplication + semantic linking across all requirements."""
    name = "dedup"

    def __init__(self, enable_llm: bool = False):
        self.enable_llm = enable_llm

    def _link_similar_with_embeddings(self, all_reqs: List[Dict[str, Any]]) -> None:
        """Embed all requirement texts and link semantically similar pairs."""
        model = _get_embedding_model()
        if model is None:
            return

        # Filter out requirements with empty text
        valid_reqs = [r for r in all_reqs if r.get("text", "").strip()]
        if len(valid_reqs) < 2:
            return

        texts = [r["text"].strip() for r in valid_reqs]
        ids = [r["id"] for r in valid_reqs]

        # Batch encode all texts
        embs = model.encode(texts, show_progress_bar=False)
        embs = np.array(embs)

        # Normalize for cosine similarity
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms[norms == 0] = 1e-9
        normalized = embs / norms

        # Compute cosine similarity (upper triangle only)
        sim_matrix = normalized @ normalized.T

        # Link similar pairs (skip diagonal)
        n = len(valid_reqs)
        for i in range(n):
            for j in range(i + 1, n):
                sim = sim_matrix[i][j]
                if sim >= SEM_LINK_THRESHOLD:
                    req_a = valid_reqs[i]
                    req_b = valid_reqs[j]
                    req_a.setdefault("related_ids", []).append(req_b["id"])
                    req_b.setdefault("related_ids", []).append(req_a["id"])

        log.info(f"[Dedup] Embedded {n} requirements, semantic links computed")

    def _renumber_ids(self, kept: List[Dict[str, Any]]) -> None:
        """Renumber IDs sequentially and update all related_ids references."""
        for idx, req in enumerate(kept, 1):
            old_id = req["id"]
            # Extract prefix and new number
            parts = old_id.split("-", 1)
            prefix = parts[0] if len(parts) > 1 else "REQ"
            new_id = f"{prefix}-{idx:04d}"
            req["id"] = new_id

        # Now update all related_ids to reflect new IDs
        old_to_new = {r["id"].split("-", 1)[0] + "-" + str(i).zfill(4) for i, r in enumerate(kept)}  # noqa

        # Build a mapping: old_id → new_id (using original index)
        # Since we already renamed, we need the original prefix mapping
        # Rebuild: collect prefix for each position
        for idx, req in enumerate(kept):
            parts = req["id"].split("-", 1)
            prefix = parts[0] if len(parts) > 1 else "REQ"
            old_id_candidate = parts[0] + "-" + str(idx + 1).zfill(4)
            # Build map from old IDs to new IDs
            old_id_candidate = req["id"]

    def _renumber_ids_clean(self, kept: List[Dict[str, Any]]) -> None:
        """Renumber IDs sequentially and fix all related_ids references."""
        # First pass: collect all new IDs and build old → new map
        new_ids = []
        for idx, req in enumerate(kept, 1):
            parts = req["id"].split("-", 1)
            prefix = parts[0] if len(parts) > 1 else "REQ"
            new_id = f"{prefix}-{idx:04d}"
            new_ids.append(new_id)

        # Build mapping: keep the first occurrence's prefix per original prefix group
        old_id_set = set()
        for req in kept:
            old_id_set.add(req["id"])

        # Since we already changed IDs in first pass, build map from position
        for idx, req in enumerate(kept):
            req["id"] = new_ids[idx]

        # Second pass: update all related_ids references
        # Build position → ID map
        pos_to_id = {i: new_ids[i] for i in range(len(kept))}

        # We need to find which req each related_id pointed to before renumbering.
        # Strategy: search by text matching (since IDs are now changed)
        # Instead, do a two-pass approach:
        # Pass 1: store old_ids before renaming
        for req in kept:
            req["_old_id"] = req["id"]

        old_id_to_new_id = {}
        for idx, req in enumerate(kept):
            parts = req["_old_id"].split("-", 1)
            prefix = parts[0] if len(parts) > 1 else "REQ"
            old_id_to_new_id[req["_old_id"]] = new_ids[idx]
            del req["_old_id"]

        # Now update related_ids
        for req in kept:
            new_rels = []
            for rel_id in req.get("related_ids", []):
                new_id = old_id_to_new_id.get(rel_id)
                if new_id and new_id != req["id"]:
                    new_rels.append(new_id)
            req["related_ids"] = list(set(new_rels))

    async def process(
        self,
        reqs: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Global dedup + semantic linking across all requirements.
        1. Sort by confidence descending (highest first)
        2. Rapidfuzz dedup for near-identical text
        3. LLM review for ambiguous near-misses
        4. Embedding-based semantic linking for related requirements
        5. Renumber IDs sequentially
        Input:  list of requirement dicts
        Output: deduplicated + linked list
        """
        if context is None:
            context = {}
        from rapidfuzz import fuzz
        dedup_thr = context.get("dedup_threshold", 88)
        link_thr = context.get("link_threshold", 70)
        semaphore = context.get("_llm_semaphore", asyncio.Semaphore(2))

        # Sort by confidence descending (highest first)
        all_reqs: List[Dict[str, Any]] = list(reqs) if isinstance(reqs, list) else []
        all_reqs.sort(key=lambda r: -r.get("confidence", 0))

        kept: List[Dict[str, Any]] = []
        for req in all_reqs:
            is_dup = False
            for ex in kept:
                ratio = fuzz.token_sort_ratio(req["text"], ex["text"])
                if ratio >= dedup_thr:
                    is_dup = True
                    break
                if ratio >= link_thr:
                    # LLM review for ambiguous cases
                    if self.enable_llm:
                        llm_result = await _llm_check_duplicate_sync(
                            req["text"], ex["text"], semaphore
                        )
                        if llm_result is not None and llm_result:
                            is_dup = True
                            break
                    # Link near-miss pairs (regardless of LLM path)
                    ex.setdefault("related_ids", []).append(req["id"])
                    req.setdefault("related_ids", []).append(ex["id"])
            if not is_dup:
                kept.append(req)

        # Embedding-based semantic linking (catches same-meaning different-wording)
        self._link_similar_with_embeddings(kept)

        # Renumber IDs sequentially
        self._renumber_ids_clean(kept)

        removed = len(all_reqs) - len(kept)
        log.info(f"[Dedup] {len(all_reqs)} -> {len(kept)} ({removed} removed)")
        return kept
