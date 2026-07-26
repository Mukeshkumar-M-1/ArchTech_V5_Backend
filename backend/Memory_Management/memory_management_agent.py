"""
memory_management_agent.py — LLM-Powered Memory Enrichment for Project Memory.

After requirement extraction, this agent transforms raw JSON requirements
into structured markdown memory files using LLM calls. The enriched .md
files serve as background knowledge for the Content Knowledge Agent during
document generation.

Execution model:
- Launched as a background asyncio task (fire-and-forget) after extraction
- Runs 75 LLM calls (57+8+8+1+1) with bounded concurrency (Semaphore=5)
- Each call has retry+backoff, model fallback, and empty-content detection

Usage:
    from Memory_Management.memory_management_agent import MemoryManagementAgent
    _spawn_background_task(MemoryManagementAgent().run, project_id)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from system_config import get_knowledge_source_dir
from Requirement_extraction.constant_data import DEFAULT_LLM_CONCURRENCY
from llm_api_handler import llm_request
from prompts import prompts

log = logging.getLogger(__name__)
LLM_OPUS = "opus46"
LLM_TOKENS = 8192
LLM_TEMPERATURE = 0.1

class MemoryManagementAgent:
    """
    Transforms raw requirement JSON into structured markdown memory files.

    Pipeline after extraction:
      Phase A: LLM-enrich 57 individual requirements → requirements/*.md
      Phase B: LLM-enrich 8 categories → categories/*.md
      Phase C: LLM-enrich 8 sub-categories → subcategories/*.md
      Phase D: Rule-based relationships → relationships.md
      Phase E: LLM-enrich project overview → overview.md
      Phase F: Update MEMORY.md index
    """

    def __init__(self, progress_callback=None):
        self.prompt_engine = prompts
        self.progress_callback = progress_callback
        self._cancelled = asyncio.Event()
        self._total_requirements = 0
        self.phase_A_completed   = 0
        self.phase_B_completed   = 0
        self.phase_B_category_list = 0
        self.phase_C_sub_category_list = 0        
        self.phase_C_completed   = 0
        self.CONCURRENCY_LIMIT = DEFAULT_LLM_CONCURRENCY

    def _check_cancelled(self):
        """Raise CancelledError if cancellation was requested."""
        if self._cancelled.is_set():
            raise asyncio.CancelledError("Memory generation cancelled by user")

    def cancel(self):
        """Signal cancellation — wakes up _check_cancelled and any awaits."""
        self._cancelled.set()

    def _report_progress(self, phase: str, current: int, total: int):
        """Report progress to the callback (if provided)."""
        if self.progress_callback and total > 0:
            self.progress_callback(phase, current, total)

    def get_all_requirements(self, project_id: str) -> list[dict]:
        """Return all requirements from ALL documents in the project."""
        from system_config import get_req_dir

        req_folder_path = get_req_dir(project_id)
        kb_path = req_folder_path / "requirements.json"
        if not kb_path.exists():
            return []
        all_reqs = json.loads(kb_path.read_text(encoding="utf-8"))

        # Remove duplicates by requirement ID (last occurrence wins)
        seen: set[str] = set()
        unique: list[dict] = []
        for req_item in all_reqs:
            rid = req_item.get("id")
            if rid and rid not in seen:
                seen.add(rid)
                unique.append(req_item)
        removed = len(all_reqs) - len(unique)
        if removed:
            log.warning(f"[MemoryManagementAgent] Removed {removed} duplicate requirement(s) — {len(all_reqs)} → {len(unique)}")
        return unique

    async def run(self, project_id: str, progress_callback=None) -> dict:
        """Entry point — runs all enrichment phases. Returns progress stats."""

        # Allow overriding progress_callback
        if progress_callback:
            self.progress_callback = progress_callback

        exracted_requirement_data = self.get_all_requirements(project_id)
        if not exracted_requirement_data:
            log.warning(f"[MemoryManagementAgent] {project_id}: no requirements to enrich")
            return {"error": "no requirements"}

        knowledge_dir = get_knowledge_source_dir(project_id=project_id)
        knowledge_dir.mkdir(parents=True, exist_ok=True)

        stats: dict[str, Any] = {"project_id": project_id}
        reqs_count = len(exracted_requirement_data)

        # Phase A: LLM calls for individual requirements
        stats["phase_a"] = await self._enrich_requirement_memories(
            project_id, exracted_requirement_data, knowledge_dir
        )
        self._report_progress("Phase A — Requirements", reqs_count, reqs_count)
        self._check_cancelled()

        # Phase B: LLM calls for category summaries
        categories = self._group_by_category(exracted_requirement_data)
        stats["phase_b"] = await self._enrich_category_memories(
            project_id, exracted_requirement_data, knowledge_dir
        )
        self._report_progress("Phase B — Categories", len(categories), len(categories))
        self._check_cancelled()

        # Phase C: LLM calls for sub-category summaries
        sub_cats = self._group_by_subcategory(exracted_requirement_data)
        stats["phase_c"] = await self._enrich_subcategory_memories(
            project_id, exracted_requirement_data, knowledge_dir
        )
        self._report_progress("Phase C — Subcategories", len(sub_cats), len(sub_cats))
        self._check_cancelled()

        # Phase D: Relationships
        stats["phase_d"] = await self._create_relationships(
            project_id, exracted_requirement_data, knowledge_dir
        )
        self._report_progress("Phase D — Relationships", 1, 1)

        # Phase E: Project Overview
        stats["phase_e"] = await self._enrich_project_overview(
            project_id, exracted_requirement_data, knowledge_dir
        )
        self._report_progress("Phase E — Overview", 1, 1)
        self._check_cancelled()

        # Phase F: MEMORY.md Index
        stats["phase_f"] = await self._update_memory_index(project_id, knowledge_dir, stats)
        self._report_progress("Phase F — Index", 1, 1)
        self._check_cancelled()

        return stats

    # ── Phase A: Individual Requirement Enrichment ──────────────────────────

    async def _enrich_requirement_memories(
        self, project_id: str, exracted_requirement_data: list, knowledge_dir: Path
    ) -> dict:
        """Enrich all requirements using bounded parallel LLM calls."""
        req_dir = knowledge_dir / "requirements"
        req_dir.mkdir(parents=True, exist_ok=True)
        self._total_requirements = len(exracted_requirement_data)

        # Build index maps for context
        req_by_id = {req_item["id"]: req_item for req_item in exracted_requirement_data}
        categories = self._group_by_category(exracted_requirement_data)
        cat_counts = {cat: len(rlist) for cat, rlist in categories.items()}

        semaphore = asyncio.Semaphore(self.CONCURRENCY_LIMIT)
        tasks = []
        completed = 0

        # Report initial progress
        self._report_progress("Phase A — Requirements", 0, len(exracted_requirement_data))

        # DEBUG: Process only first 5 requirements
        for req in exracted_requirement_data:
            task = asyncio.create_task(
                self._enrich_single_requirement(
                    req, req_by_id, cat_counts, project_id, req_dir, semaphore
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, str) and result.strip():
                completed += 1

        written = 0
        failed = []
        for req, result in zip(exracted_requirement_data, results):
            if isinstance(result, str) and result.strip():
                written += 1
            elif isinstance(result, Exception):
                failed.append({"id": req["id"], "error": str(result)})
            else:
                failed.append({"id": req["id"], "error": "empty response"})

        return {"written": written, "failed": failed}

    async def _enrich_single_requirement(
        self,
        req: dict,
        req_by_id: dict,
        cat_counts: dict,
        project_id: str,
        req_dir: Path,
        semaphore: asyncio.Semaphore,
    ) -> str:
        async with semaphore:
            self._check_cancelled()
            system_prompt = self.prompt_engine.render("enrich_requirement_memory")
            context = self._build_requirement_context(req, req_by_id, cat_counts)
            result = await llm_request(
                model=LLM_OPUS,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": context}],
                max_tokens=LLM_TOKENS,
                temperature=LLM_TEMPERATURE,
                fallback_chain=[LLM_OPUS],
            )
            (req_dir / f"{req['id']}.md").write_text(result or "", encoding="utf-8")
            log.info(f" [Phase A] [{req['id']}] created success... \n")
            self.phase_A_completed += 1
            self._report_progress("Phase A — Requirements", self.phase_A_completed, self._total_requirements)
            return result

    def _build_requirement_context(self, req: dict, req_by_id: dict, cat_counts: dict) -> str:
        """Build prompt context for a single requirement."""
        # Gather related requirements
        related = []
        for rid in (req.get("related_ids") or []):
            if rid in req_by_id:
                req_item = req_by_id[rid]
                related.append(f"  {req_item['id']}: {req_item['text']}")
        related_text = "\n".join(related) if related else "(none explicitly linked)"

        # Category peers (up to 3 for context)
        cat = req.get("category", "")
        cat_count = cat_counts.get(cat, 0)

        return (
            f"Requirement ID: {req['id']}\n"
            f"Category: {cat}\n"
            f"Sub-Category: {req.get('sub_category', 'N/A')}\n"
            f"Priority: {req.get('priority', 'N/A')}\n"
            f"Confidence: {req.get('confidence', 0)}\n"
            f"Category peer count: {cat_count}\n"
            f"\nOriginal Text:\n{req['text']}\n"
            f"\nOriginal Explanation:\n{req.get('explanation', 'N/A')}\n"
            f"\nKeywords: {', '.join(req.get('keywords', []))}\n"
            f"\nSource: {req.get('source', 'N/A')} (page {req.get('page', 'N/A')})\n"
            f"Related Requirements:\n{related_text}\n"
            f"\nAttributes:\n"
            f"  has_unit: {req.get('has_unit')}\n"
            f"  has_directive: {req.get('has_directive')}\n"
            f"  rule_score: {req.get('rule_score')}\n"
            f"  char_count: {req.get('char_count')}"
        )

    # ── Phase B: Category Enrichment ────────────────────────────────────────

    async def _enrich_category_memories(
        self, project_id: str, exracted_requirement_data: list, knowledge_dir: Path
    ) -> dict:
        """Enrich all category summaries using bounded parallel LLM calls."""
        cat_dir = knowledge_dir / "categories"
        cat_dir.mkdir(parents=True, exist_ok=True)
        categories = self._group_by_category(exracted_requirement_data)
        semaphore = asyncio.Semaphore(self.CONCURRENCY_LIMIT)
        categories_list = list(categories.items())
        self.phase_B_category_list = len(categories_list)
        tasks = []

        self._report_progress("Phase B — Categories", 0, self.phase_B_category_list)
        completed = 0

        for idx, (cat, cat_reqs) in enumerate(categories_list):
            task = asyncio.create_task(
                self._enrich_single_category(cat, cat_reqs, project_id, cat_dir, semaphore)
            )
            tasks.append(task)
            # Report progress after each task is dispatched
            completed += 1

        results = await asyncio.gather(*tasks, return_exceptions=True)

        written = 0
        failed = []
        for cat, result in zip(categories.keys(), results):
            if isinstance(result, str) and result.strip():
                written += 1
            elif isinstance(result, Exception):
                failed.append({"category": cat, "error": str(result)})
            else:
                failed.append({"category": cat, "error": "empty response"})

        return {"written": written, "failed": failed}

    async def _enrich_single_category(
        self,
        cat: str,
        cat_reqs: list,
        project_id: str,
        cat_dir: Path,
        semaphore: asyncio.Semaphore,
    ) -> str:
        async with semaphore:
            self._check_cancelled()
            system_prompt = self.prompt_engine.render("enrich_category_memory")
            context = self._build_category_context(cat, cat_reqs)
            max_tokens = max(LLM_TOKENS, len(cat_reqs) * 128)  # ~128 tokens per requirement
            log.info(f"[{cat}] {len(cat_reqs)} exracted_requirement_data -> max_tokens={max_tokens}")
            result = await llm_request(
                model=LLM_OPUS,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": context}],
                max_tokens=max_tokens,
                temperature=LLM_TEMPERATURE,
                fallback_chain=[LLM_OPUS],
            )
            (cat_dir / f"category_{cat}.md").write_text(result or "", encoding="utf-8")
            log.info(f"[Phase B] [{cat}] completed success ... \n")
            self.phase_B_completed += 1
            self._report_progress("Phase B — Categories", self.phase_B_completed, self.phase_B_category_list)

            return result

    def _build_category_context(self, cat: str, cat_reqs: list) -> str:
        """Build prompt context for a category."""
        sub_counts = defaultdict(int)
        for req_item in cat_reqs:
            sub_counts[req_item.get("sub_category", "General")] += 1

        sub_table = "\n".join(f"- {sub}: {count}" for sub, count in sorted(sub_counts.items()))

        reqs_text = ""
        for req_item in cat_reqs:
            reqs_text += (
                f"\n### {req_item['id']}\n"
                f"Text: {req_item['text']}\n"
                f"Explanation: {req_item.get('explanation', 'N/A')}\n"
                f"Priority: {req_item.get('priority')}, Confidence: {req_item.get('confidence')}\n"
            )

        return (
            f"Category: {cat}\n"
            f"Total requirements: {len(cat_reqs)}\n"
            f"Sub-category distribution:\n{sub_table}\n"
            f"\nRequirements:\n{reqs_text}"
        )

    # ── Phase C: Sub-Category Enrichment ────────────────────────────────────

    async def _enrich_subcategory_memories(
        self, project_id: str, exracted_requirement_data: list, knowledge_dir: Path
    ) -> dict:
        """Enrich all sub-category summaries using bounded parallel LLM calls."""
        sub_dir = knowledge_dir / "subcategories"
        sub_dir.mkdir(parents=True, exist_ok=True)
        sub_categories = self._group_by_subcategory(exracted_requirement_data)
        semaphore = asyncio.Semaphore(self.CONCURRENCY_LIMIT)
        sub_cats_list = list(sub_categories.items())
        self.phase_C_sub_category_list = len(sub_cats_list)
        tasks = []

        self._report_progress("Phase C — Subcategories", 0, self.phase_C_sub_category_list)
        completed = 0

        for sub_cat, sub_reqs in sub_cats_list:
            task = asyncio.create_task(
                self._enrich_single_subcategory(sub_cat, sub_reqs, project_id, sub_dir, semaphore)
            )
            tasks.append(task)
            completed += 1

        results = await asyncio.gather(*tasks, return_exceptions=True)

        written = 0
        failed = []
        for sub_cat, result in zip(sub_categories.keys(), results):
            if isinstance(result, str) and result.strip():
                written += 1
            elif isinstance(result, Exception):
                failed.append({"sub_category": sub_cat, "error": str(result)})

        return {"written": written, "failed": failed}

    async def _enrich_single_subcategory(
        self,
        sub_cat: str,
        sub_reqs: list,
        project_id: str,
        sub_dir: Path,
        semaphore: asyncio.Semaphore,
    ) -> str:
        async with semaphore:
            self._check_cancelled()
            system_prompt = self.prompt_engine.render("enrich_subcategory_memory")
            context = self._build_subcategory_context(sub_cat, sub_reqs)
            max_tokens = max(LLM_TOKENS, len(sub_reqs) * 128)  # ~128 tokens per requirement
            result = await llm_request(
                model=LLM_OPUS,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": context}],
                max_tokens=max_tokens,
                temperature=LLM_TEMPERATURE,
                fallback_chain=[LLM_OPUS],
            )
            (sub_dir / f"subcategory_{sub_cat}.md").write_text(result or "", encoding="utf-8")
            log.info(f"[Phase C] [{sub_cat}] completed success ... \n")
            self.phase_C_completed += 1
            self._report_progress("Phase C — Subcategories", self.phase_C_completed, self.phase_C_sub_category_list)
            return result

    def _build_subcategory_context(self, sub_cat: str, sub_reqs: list) -> str:
        """Build prompt context for a sub-category."""
        reqs_text = ""
        for req_item in sub_reqs:
            reqs_text += (
                f"\n### {req_item['id']}\n"
                f"Text: {req_item['text']}\n"
                f"Explanation: {req_item.get('explanation', 'N/A')}\n"
                f"Keywords: {', '.join(req_item.get('keywords', []))}\n"
            )

        return (
            f"Sub-Category: {sub_cat}\n"
            f"Total requirements: {len(sub_reqs)}\n"
            f"\nRequirements:\n{reqs_text}"
        )

    # ── Phase D: Relationships (LLM with keyword overlap fallback) ─────────

    async def _create_relationships(
        self, project_id: str, exracted_requirement_data: list, knowledge_dir: Path
    ) -> dict:
        """Build relationships graph using LLM to find semantic links between requirements."""
        req_by_id = {req_item["id"]: req_item for req_item in exracted_requirement_data}
        explicit_links = []
        for req_item in exracted_requirement_data:
            for req_item_id in (req_item.get("related_ids") or []):
                if req_item_id in req_by_id:
                    explicit_links.append((req_item["id"], req_item_id))
        

        kw_pairs = []
        for req_item in exracted_requirement_data:
            kw = [k.lower().strip() for k in req_item.get("keywords", []) if k]
            if kw:
                kw_pairs.append((req_item["id"], kw))

        context = (
            f"Project ID: {project_id}\n"
            f"Total requirements: {len(exracted_requirement_data)}\n"
            f"Explicit links (from related_ids): {len(explicit_links)}\n"
        )
        for a, b in explicit_links:
            ra, rb = req_by_id.get(a, {}), req_by_id.get(b, {})
            text_a = (ra.get("text") or "")[:300]
            text_b = (rb.get("text") or "")[:300]
            context += (
                f"- {a} ({ra.get('sub_category', 'N/A')}): {text_a}\n"
                f"  ↔ {b} ({rb.get('sub_category', 'N/A')}): {text_b}\n"
            )

        context += "\nKeywords per requirement:\n"
        for rid, kws in kw_pairs:
            context += f"- {rid}: {', '.join(kws)}\n"

        context += "\nRequirements (for semantic analysis):\n"
        for req_item in exracted_requirement_data:
            text = (req_item.get("text") or "")[:300]
            context += (
                f"- {req_item['id']} ({req_item.get('category', '')}/{req_item.get('sub_category', '')}): "
                f"{text}\n"
            )

        self._report_progress("Phase D — Relationships", 1, 1)
        system_prompt = self.prompt_engine.render("enrich_relationships")
        phase_d_max_tokens = min(max(4096, len(exracted_requirement_data) * 64), 8192)
        result = await asyncio.wait_for(
            llm_request(
                model=LLM_OPUS,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": context}],
                max_tokens=phase_d_max_tokens,
                temperature=LLM_TEMPERATURE,
                fallback_chain=["sonnet46", "haiku"],
                timeout=600,
            ),
            timeout=600,
        )

        if result and result.strip():
            (knowledge_dir / "relationships.md").write_text(result, encoding="utf-8")
            log.info(f"[Phase D] [relationships.md] completed success ... \n")
            return {"status": "ok"}
        else:
            return await self._create_relationships_fallback(exracted_requirement_data, knowledge_dir)

    async def _create_relationships_fallback(
        self, exracted_requirement_data: list, knowledge_dir: Path
    ) -> dict:
        """Fallback rule-based relationships if LLM call fails."""
        req_by_id = {req_item["id"]: req_item for req_item in exracted_requirement_data}
        links: dict[str, list[str]] = defaultdict(list)

        for req_item in exracted_requirement_data:
            for rid in (req_item.get("related_ids") or []):
                if rid in req_by_id:
                    links[req_item["id"]].append(rid)

        keyword_map = {}
        for req_item in exracted_requirement_data:
            kw = set(k.lower().strip() for k in req_item.get("keywords", []) if k)
            if kw:
                keyword_map[req_item["id"]] = kw

        for rid1, kw1 in keyword_map.items():
            for rid2, kw2 in keyword_map.items():
                if rid1 >= rid2:
                    continue
                overlap = kw1 & kw2
                if len(overlap) >= 3:
                    if rid2 not in links[rid1]:
                        links[rid1].append(rid2)

        lines = [
            "# Requirement Relationships",
            f"Total requirements: {len(exracted_requirement_data)}",
            "",
            "## Explicit Links (from related_ids)",
            "",
        ]
        for rid, linked in sorted(links.items()):
            if rid in req_by_id:
                req = req_by_id[rid]
                linked_text = [f"  - [{l}]({l}.md)" for l in linked if l in req_by_id]
                lines.append(f"### {rid} — {req.get('text', '')}")
                lines.extend(linked_text)
                lines.append("")

        (knowledge_dir / "relationships.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"status": "fallback"}

    # ── Phase E: Project Overview ───────────────────────────────────────────

    async def _enrich_project_overview(
        self, project_id: str, exracted_requirement_data: list, knowledge_dir: Path
    ) -> dict:
        """Chunked LLM calls for project overview — splits requirements into batches of 25."""
        CHUNK_SIZE = 25
        batches = [
            exracted_requirement_data[i : i + CHUNK_SIZE]
            for i in range(0, len(exracted_requirement_data), CHUNK_SIZE)
        ]

        partial_results = await asyncio.gather(
            *(
                self._enrich_overview_chunk(chunk, idx, len(batches))
                for idx, chunk in enumerate(batches)
            ),
            return_exceptions=True,
        )

        # Aggregate partial results
        overview_parts = []
        failed_chunks = 0
        for i, result in enumerate(partial_results):
            if isinstance(result, str) and result.strip():
                overview_parts.append(f"## Chunk {i + 1}/{len(batches)}\n\n{result}")
            elif isinstance(result, Exception):
                log.error(f"[Phase E] Chunk {i + 1} failed: {result}")
                failed_chunks += 1
            else:
                log.warning(f"[Phase E] Chunk {i + 1} returned empty response")
                failed_chunks += 1

        if failed_chunks == len(batches):
            return {"status": "failed", "failed_chunks": failed_chunks, "total_chunks": len(batches)}

        combined = "\n\n---\n\n".join(overview_parts)
        overview_full = f"# Project Overview — {project_id}\n\n{combined}\n"
        (knowledge_dir / "overview.md").write_text(overview_full, encoding="utf-8")
        log.info(f"[Phase E] [overview.md] completed with {len(batches)} chunks ({failed_chunks} failed) ... \n")
        return {"status": "ok", "chunks": len(batches), "failed_chunks": failed_chunks}

    async def _enrich_overview_chunk(
        self,
        chunk: list,
        chunk_idx: int,
        total_chunks: int,
    ) -> str:
        """Enrich a single chunk of requirements for the project overview."""
        # Build per-requirement detail for this chunk only
        req_detail_lines = []
        for req in chunk:
            req_id = req.get("id", "UNKNOWN")
            req_text = (req.get("text") or "N/A")[:300]
            explanation = (req.get("explanation") or "N/A")[:300]
            req_detail_lines.append(
                f"### {req_id}\n"
                f"Category: {req.get('category', 'N/A')}\n"
                f"Sub-Category: {req.get('sub_category', 'N/A')}\n"
                f"Priority: {req.get('priority', 'N/A')}\n"
                f"Requirement: {req_text}\n"
                f"Explanation: {explanation}\n"
                f"Keywords: {', '.join(req.get('keywords', []))}\n"
                f"Source: {req.get('source', 'N/A')} (page {req.get('page', 'N/A')})\n"
                f"Attributes:\n"
                f"  has_unit: {req.get('has_unit')}\n"
                f"  has_directive: {req.get('has_directive')}\n"
                f"  rule_score: {req.get('rule_score')}\n"
                f"  char_count: {req.get('char_count')}\n"
                f"Related: {', '.join(req.get('related_ids') or [])}"
            )

        context = (
            f"Chunk {chunk_idx + 1}/{total_chunks} of project overview\n"
            f"Requirements in this chunk: {len(chunk)}\n"
            f"\nRequirements Detail:\n" + "\n".join(req_detail_lines)
        )

        system_prompt = self.prompt_engine.render("enrich_project_overview")
        chunk_max_tokens = min(max(4096, len(chunk) * 128), 8192)
        result = await asyncio.wait_for(
            llm_request(
                model=LLM_OPUS,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": context}],
                max_tokens=chunk_max_tokens,
                temperature=LLM_TEMPERATURE,
                fallback_chain=["sonnet46", "haiku"],
                timeout=600,
            ),
            timeout=600,
        )
        return result or ""

    # ── Phase F: MEMORY.md Index ────────────────────────────────────────────

    async def _update_memory_index(
        self, project_id: str, knowledge_dir: Path, stats: dict
    ) -> dict:
        """Update MEMORY.md index with LLM-enriched content."""
        memory_md = knowledge_dir / "MEMORY.md"

        # Build detailed file listing with descriptions
        file_list = []
        for subdir in ["requirements", "categories", "subcategories"]:
            dir_path = knowledge_dir / subdir
            if dir_path.exists():
                for file_item in sorted(dir_path.glob("*.md")):
                    desc = file_item.stem.replace("_", " ").replace("-", " ")
                    file_list.append(f"- {subdir}/{file_item.name} — {desc}")

        context = (
            f"Project ID: {project_id}\n"
            f"Knowledge files:\n" + "\n".join(file_list) + "\n"
            f"Stats: {json.dumps(stats, indent=2)}"
        )

        system_prompt = self.prompt_engine.render("enrich_memory_index")
        result = await llm_request(
            model=LLM_OPUS,
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": context}],
            max_tokens=LLM_TOKENS,
            temperature=LLM_TEMPERATURE,
            fallback_chain=[LLM_OPUS],
        )

        if result and result.strip():
            memory_md.write_text(result, encoding="utf-8")
            log.info(f"[Phase G] [MEMORY.md] completed success ... \n")
        else:
            await self._update_memory_index_fallback(project_id, knowledge_dir, stats)

        return {"status": "ok" if result else "failed"}
    
    async def _update_memory_index_fallback(
        self, project_id: str, knowledge_dir: Path, stats: dict
    ) -> None:
        """Fallback static MEMORY.md if LLM call fails."""
        memory_md = knowledge_dir / "MEMORY.md"
        parts = [f"# Project Memory Index — {project_id}", ""]

        for subdir in ["requirements", "categories", "subcategories"]:
            dir_path = knowledge_dir / subdir
            if dir_path.exists():
                files = sorted(file_item.name for file_item in dir_path.glob("*.md"))
                if files:
                    parts.append(f"## {subdir}")
                    parts.append("")
                    for file_item in files[:100]:
                        parts.append(f"- [{file_item}]({subdir}/{file_item})")
                    if len(files) > 100:
                        parts.append(f"- ... and {len(files) - 100} more")
                    parts.append("")

        enriched = stats.get("phase_a", {}).get("written", 0)
        parts.append("## Status")
        parts.append("")
        parts.append(f"- Enriched requirements: {enriched}")
        parts.append(f"- Last updated: {datetime.utcnow().isoformat()}Z")
        parts.append("")

        memory_md.write_text("\n".join(parts), encoding="utf-8")

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _group_by_category(exracted_requirement_data: list) -> dict[str, list]:
        """Group requirements by top-level category."""
        groups: dict[str, list] = defaultdict(list)
        for req_item in exracted_requirement_data:
            cat = req_item.get("category", "Uncategorized")
            groups[cat].append(req_item)
        return dict(groups)

    @staticmethod
    def _group_by_subcategory(exracted_requirement_data: list) -> dict[str, list]:
        """Group requirements by sub_category."""
        groups: dict[str, list] = defaultdict(list)
        for req_item in exracted_requirement_data:
            sub = req_item.get("sub_category", "General")
            groups[sub].append(req_item)
        return dict(groups)
