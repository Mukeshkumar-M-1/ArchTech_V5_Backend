"""
extraction_event_loop.py — ArchTech RAG v5 (modular stages)
============================================================
Orchestrates the 8-stage extraction pipeline by importing from individual
stage modules. All shared constants live in constant_data.py.

Usage:
    from Requirement_extraction.extraction_event_loop import ExtractionEventLoop
    loop = ExtractionEventLoop()
    results = loop.run_sync("doc.pdf", doc_type="HRS")
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import sys
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ─── Fix import paths for various run scenarios ───────────────────────────────
_script_dir = Path(__file__).resolve().parent  # backend/Requirement_extraction/
_backend_dir = _script_dir.parent              # backend/
_repo_root = _backend_dir = _script_dir.parent     # backend/
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))  # constant_data, stage_*, etc.
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))  # system_config, llm_api_handler, prompts
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))  # for `from backend.Requirement_extraction` imports

log = logging.getLogger(__name__)

# ─── Import shared constants from constant_data.py ──────────────────────────
try:
    from .constant_data import (
        DEFAULT_PAGE_CONCURRENCY, DEFAULT_LLM_CONCURRENCY, DEFAULT_BATCH_SIZE,
        DEFAULT_MIN_CONFIDENCE, DEFAULT_DEDUP_THRESHOLD, DEFAULT_LINK_THRESHOLD,
        DEBUG_PAGE_LIMIT
    )
    from backend.system_config import ( 
        SEGMENTATION_ENABLE_LLM, 
        DETECTION_ENABLE_LLM, CLASSIFICATION_ENABLE_LLM, EXPLAIN_ENABLE_LLM, 
        SCORING_ENABLE_LLM, DEDUP_ENABLE_LLM
    )
    from .stage_base import PipelineEvent
    from .stage_1_Ingest import StageIngest
    from .stage_2_Segment import StageSegment
    from .stage_2_llm_segment import StageLLM_Segment
    from .stage_3_Detect import StageDetect
    from .stage_3_llm_detect import StageLLMDetect
    from .stage_4_Normalize import StageNormalize
    from .stage_5_Classify import StageClassify, warm_up_category_embeddings
    from .stage_6_Explain import StageExplain
    from .stage_7_Score import StageScore
    from .stage_8_Dedup import StageDedup
except ImportError:
    try:
        from backend.system_config import (
            SEGMENTATION_ENABLE_LLM,
            DETECTION_ENABLE_LLM, CLASSIFICATION_ENABLE_LLM, EXPLAIN_ENABLE_LLM,
            SCORING_ENABLE_LLM, DEDUP_ENABLE_LLM
        )
    except ImportError:
        from system_config import (
            SEGMENTATION_ENABLE_LLM,
            DETECTION_ENABLE_LLM, CLASSIFICATION_ENABLE_LLM, EXPLAIN_ENABLE_LLM,
            SCORING_ENABLE_LLM, DEDUP_ENABLE_LLM
        )
    from constant_data import (
        DEFAULT_PAGE_CONCURRENCY, DEFAULT_LLM_CONCURRENCY, DEFAULT_BATCH_SIZE,
        DEFAULT_MIN_CONFIDENCE, DEFAULT_DEDUP_THRESHOLD, DEFAULT_LINK_THRESHOLD,
        DEBUG_PAGE_LIMIT
    )
    from stage_base import PipelineEvent
    from stage_1_Ingest import StageIngest
    from stage_2_Segment import StageSegment
    from stage_2_llm_segment import StageLLM_Segment
    from stage_3_Detect import StageDetect
    from stage_3_llm_detect import StageLLMDetect

    from stage_4_Normalize import StageNormalize
    from stage_5_Classify import StageClassify, warm_up_category_embeddings
    from stage_6_Explain import StageExplain
    from stage_7_Score import StageScore
    from stage_8_Dedup import StageDedup

# ─── Worker Pool ────────────────────────────────────────────────────────────
class WorkerPool:
    """Semaphore-throttled async worker pool."""

    def __init__(self, max_concurrency: int = DEFAULT_PAGE_CONCURRENCY):
        self._sem = asyncio.Semaphore(max_concurrency)
        self._active = 0
        self._lock = asyncio.Lock()
        self._stats = {"completed": 0, "failed": 0, "total_time": 0.0}

    async def submit(self, coro) -> Any:
        async with self._sem:
            async with self._lock:
                self._active += 1
            try:
                start = time.monotonic()
                result = await coro
                elapsed = time.monotonic() - start
                async with self._lock:
                    self._stats["completed"] += 1
                    self._stats["total_time"] += elapsed
                return result
            except Exception:
                async with self._lock:
                    self._stats["failed"] += 1
                raise
            finally:
                async with self._lock:
                    self._active -= 1

    @property
    def active_workers(self) -> int:
        return self._active

    @property
    def stats(self) -> Dict[str, Any]:
        return dict(self._stats)


# ─── Pipeline Coordinator ───────────────────────────────────────────────────
class PipelineCoordinator:
    """Orchestrates the 8-stage pipeline across pages."""

    def __init__(
        self,
        page_concurrency: int = DEFAULT_PAGE_CONCURRENCY,
        llm_concurrency: int = DEFAULT_LLM_CONCURRENCY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
        link_threshold: float = DEFAULT_LINK_THRESHOLD,
    ):
        self._pool = WorkerPool(max_concurrency=page_concurrency)
        self._llm_sem = asyncio.Semaphore(llm_concurrency)
        self._id_lock = asyncio.Lock()
        self._counters: Dict[str, int] = {}
        self._batch_size = batch_size
        self._min_confidence = min_confidence
        self._dedup_threshold = dedup_threshold
        self._link_threshold = link_threshold
        self._progress_callbacks: List[Callable] = []
        self._warm_started = False

    # ── Progress callbacks ───────────────────────────────────────────────
    def on_progress(self, callback: Callable) -> None:
        self._progress_callbacks.append(callback)

    async def _emit(self, stage: str, status: str, message: str = "", **kwargs) -> None:
        event = PipelineEvent(stage=stage, status=status, message=message, **kwargs)
        log.info(f"[Progress] {stage}: {status} {message} \n\n")
        for cb in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event.to_dict())
                else:
                    cb(event.to_dict())
            except Exception as e:
                log.error(f"[Progress callback error: {e}]")

    # ── Full pipeline ────────────────────────────────────────────────────
    async def run(
        self,
        pdf_path: str,
        doc_type: str = "TechSpec",
        doc_name: str = "",
        use_llm_norm: bool = False,
    ) -> List[Dict[str, Any]]:
        if not doc_name:
            doc_name = Path(pdf_path).name
        start_time = time.monotonic()

        log.info(f"[Coordinator] Starting pipeline: {doc_name} [{doc_type}]")
        await self._emit("pipeline", "started", f"Processing {doc_name}")

        # Warm up models once
        if not self._warm_started:
            await self._emit("pipeline", "warming", "Loading embedding models...")
            warm_up_category_embeddings()
            self._warm_started = True

        # Shared context passed between stages
        context: Dict[str, Any] = {
            "doc_type": doc_type,
            "doc_name": doc_name,
            "use_llm_norm": use_llm_norm,
            "_llm_semaphore": self._llm_sem,
            "batch_size": self._batch_size,
            "min_confidence": self._min_confidence,
        }

        # ── Stage 1: Ingest ────────────────────────────────────────────────
        if not Path(pdf_path).exists():
            log.error(f"[Ingest] PDF not found: {pdf_path}")
            return []

        await self._emit("[Stage_1.Ingest]", "running", f"Reading {doc_name}...")
        ingest = StageIngest(DEBUG_PAGE_LIMIT)
        pages: List[Tuple[int, str, List[str]]] = await self._pool.submit(
            ingest.process(pdf_path, context)
        )

        # ----- Stage 1: Debug
        # for count in range(0, DEBUG_PAGE_LIMIT):
        #     log.info(f"[Ingest] Page Num: {count} \n Page check : {pages[count]}")

        await self._emit("[Stage_1.Ingest]", "done", f"{len(pages)} pages loaded", page=len(pages))
        if not pages:
            return []

        # ── Stages 2-7: Process pages concurrently ─────────────────────────
        await self._emit("[Pipeline]", "processing", "Running extraction pipeline...")
        page_id_lock = asyncio.Lock()
        page_counters: Dict[str, int] = {}
        all_reqs: List[Dict[str, Any]] = []
        total_pages = len(pages)

        async def _process_page(page_item: Tuple[int, str, List[str]]) -> List[Dict[str, Any]]:
            page_num, text, tables = page_item

            # Build output directory path for this batch
            output_base = Path(pdf_path).parent / "output_req_extracted"
            output_base.mkdir(parents=True, exist_ok=True)
            output_dir = output_base / f"Page_{page_num}"

            # ── Stage 2: Segment ───────────────────────────────────────
            await self._emit("[Stage_2.Segment]", "running", f"Segmenting page {page_num}")
            if SEGMENTATION_ENABLE_LLM:
                segment = StageLLM_Segment(enable_llm=True)
            else:
                segment = StageSegment()
            _, segments, tables = await segment.process((page_num, text, tables), context=context)
            await self._emit("[Stage_2.Segment]", "done", f"Page {page_num}: {len(segments)} segments", page=page_num)
            # Save Stage 2 output
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(output_dir / "stage2_segment.json", "w", encoding="utf-8") as f:
                json.dump({"page": page_num, "segments": segments, "raw_text_length": len(text)}, f, indent=2, default=str)
            if not segments:
                return []


            # ── Stage 3: Detect ────────────────────────────────────────
            await self._emit("[Stage_3.Detect]", "running", f"Detecting page {page_num}")
            if DETECTION_ENABLE_LLM:
                detect = StageLLMDetect(enable_llm=True)
            else:
                detect = StageDetect()
            _, passed, tables = await detect.process((page_num, segments, tables), context=context)
            await self._emit("[Stage_3.Detect]", "done", f"Page {page_num}: {len(passed)} passed", page=page_num)
            # Save Stage 3 output
            with open(output_dir / "stage3_detect.json", "w", encoding="utf-8") as f:
                json.dump({"page": page_num, "input_segments": segments, "passed": [{"text": t, "score": s} for t, s in passed]}, f, indent=2, default=str)
            if not passed:
                return []

            # ── Stage 4: Normalize ─────────────────────────────────────
            await self._emit("[Stage_4.Normalize]", "running", f"Normalizing page {page_num}")
            normalize = StageNormalize()
            _, normalized, tables = await normalize.process((page_num, passed, tables), context)
            await self._emit("[Stage_4.Normalize]", "done", f"[PageNum] : {page_num} normalized", page=page_num)
            # Save Stage 4 output
            with open(output_dir / "stage4_normalize.json", "w", encoding="utf-8") as f:
                json.dump({"page": page_num, "normalized": [{"text": t, "score": s, "normalized": n} for t, s, n in normalized]}, f, indent=2, default=str)

            # ── Stage 5: Classify ──────────────────────────────────────
            await self._emit("[Stage_5.Classify]", "running", f"Classifying page {page_num}")
            classify = StageClassify(enable_llm=CLASSIFICATION_ENABLE_LLM)
            _, classified, tables = await classify.process((page_num, normalized, tables), context)
            await self._emit("[Stage_5.Classify]", "done", f"Page {page_num} classified", page=page_num)
            # Save Stage 5 output
            with open(output_dir / "stage5_classify.json", "w", encoding="utf-8") as f:
                json.dump({"page": page_num, "classified": [{"category": c, "sub_category": sub, "sem_conf": sc, "kw_conf": kc, "text": orig} for c, sub, sc, kc, orig in classified]}, f, indent=2, default=str)

            # ── Stage 6: Explain ───────────────────────────────────────
            await self._emit("[Stage_6.Explain]", "running", f"Explaining page {page_num}")
            explain = StageExplain(enable_llm=EXPLAIN_ENABLE_LLM)
            _, explained, tables = await explain.process((page_num, classified, tables), context)
            await self._emit("[Stage_6.Explain]", "done", f"Page {page_num} explained", page=page_num)
            # Save Stage 6 output
            with open(output_dir / "stage6_explain.json", "w", encoding="utf-8") as f:
                json.dump({"page": page_num, "explained": [{"category": c, "sub_category": sub, "sem_conf": sc, "kw_conf": kc, "text": orig, "explanation": expl} for c, sub, sc, kc, orig, expl in explained]}, f, indent=2, default=str)

            # ── Stage 7: Score + ID assignment ─────────────────────────
            await self._emit("[Stage_7.Score]", "running", f"Scoring page {page_num}")
            score = StageScore(enable_llm=SCORING_ENABLE_LLM)
            page_reqs = await score.process((page_num, explained, tables), {
                **context,
                "_id_lock": page_id_lock,
                "_counters": page_counters,
            })
            total = 0
            for _pn, r, _tb in page_reqs:
                total += len(r)
            await self._emit("[Stage_7.Score]", "done", f"Page {page_num}: {total} requirements", page=page_num)
            # Save Stage 7 output
            with open(output_dir / f"stage7_score.json", "w", encoding="utf-8") as f:
                json.dump({"page": page_num, "requirements": [dict(r) for _, r, _ in page_reqs for r in r]}, f, indent=2, default=str)

            reqs = []
            for _pn, r, _tb in page_reqs:
                reqs.extend(r)
            return reqs

        # Run all pages concurrently (throttled by WorkerPool)
        tasks = [_process_page(p) for p in pages]
        page_results_list = await asyncio.gather(*tasks)

        # Flatten all requirements from all pages
        for reqs in page_results_list:
            all_reqs.extend(reqs)

        # ── Stage 8: Global Dedup ──────────────────────────────────────────
        await self._emit("[Stage_8.DeDuplicate]", "running", "Running global deduplication...")
        dedup = StageDedup(enable_llm=DEDUP_ENABLE_LLM)
        dedup_result = await dedup.process(all_reqs, {
            **context,
            "dedup_threshold": self._dedup_threshold,
            "link_threshold": self._link_threshold,
        })

        elapsed = time.monotonic() - start_time
        high_conf = sum(1 for r in dedup_result if r.get("confidence", 0) >= 0.60)
        log.info(
            f"[Coordinator] Done in {elapsed:.1f}s | "
            f"{len(dedup_result)} requirements ({high_conf} high-confidence)"
        )
        await self._emit("[Pipeline]", "completed",
                         f"Done in {elapsed:.1f}s | {len(dedup_result)} requirements",
                         counters=dict(self._counters))

        return dedup_result

    @property
    def pool(self) -> WorkerPool:
        return self._pool


# ─── Extraction Event Loop Manager ──────────────────────────────────────────
class ExtractionEventLoop:
    """Top-level API — manages event loop, pipeline, and resources."""

    def __init__(
        self,
        page_concurrency: int = DEFAULT_PAGE_CONCURRENCY,
        llm_concurrency: int = DEFAULT_LLM_CONCURRENCY,
        batch_size: int = DEFAULT_BATCH_SIZE,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
        link_threshold: float = DEFAULT_LINK_THRESHOLD,
    ):
        self._coordinator = PipelineCoordinator(
            page_concurrency=page_concurrency,
            llm_concurrency=llm_concurrency,
            batch_size=batch_size,
            min_confidence=min_confidence,
            dedup_threshold=dedup_threshold,
            link_threshold=link_threshold,
        )
        self._progress_callbacks: List[Callable] = []

    @property
    def coordinator(self) -> PipelineCoordinator:
        return self._coordinator

    @property
    def stats(self) -> Dict[str, Any]:
        return self._coordinator.pool.stats

    def on_progress(self, callback: Callable) -> None:
        self._progress_callbacks.append(callback)
        self._coordinator.on_progress(callback)

    async def run(
        self,
        pdf_path: str,
        doc_type: str = "TechSpec",
        doc_name: Optional[str] = None,
        use_llm_norm: bool = False,
    ) -> List[Dict[str, Any]]:
        try:
            return await self._coordinator.run(
                pdf_path=pdf_path,
                doc_type=doc_type,
                doc_name=doc_name or Path(pdf_path).name,
                use_llm_norm=use_llm_norm,
            )
        finally:
            self._running = False

    def run_sync(
        self,
        pdf_path: str,
        doc_type: str = "TechSpec",
        doc_name: Optional[str] = None,
        use_llm_norm: bool = False,
    ) -> List[Dict[str, Any]]:
        """Sync entry point -- creates a fresh event loop."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                log.warning("run_sync called from running loop! Use run() instead.")
        except RuntimeError:
            pass
        return asyncio.run(
            self.run(pdf_path=pdf_path, doc_type=doc_type,
                     doc_name=doc_name, use_llm_norm=use_llm_norm)
        )

    async def run_multi(
        self,
        files: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Run extraction on multiple files concurrently."""
        tasks = {}
        for f in files:
            name = f.get("doc_name", Path(f["pdf_path"]).name)
            tasks[name] = self.run(
                pdf_path=f["pdf_path"],
                doc_type=f.get("doc_type", "TechSpec"),
                doc_name=name,
                use_llm_norm=f.get("use_llm_norm", False),
            )
        results = await asyncio.gather(*tasks.values())
        return dict(zip(tasks.keys(), results))

    async def shutdown(self) -> None:
        self._running = False
        log.info("[EventLoop] Shutdown complete")


# ─── Convenience functions ──────────────────────────────────────────────────
def extract_requirements(
    pdf_path: str,
    doc_type: str = "TechSpec",
    use_llm_norm: bool = False,
    page_concurrency: int = DEFAULT_PAGE_CONCURRENCY,
) -> List[Dict[str, Any]]:
    """Sync entry point."""
    loop = ExtractionEventLoop(page_concurrency=page_concurrency)
    return loop.run_sync(pdf_path=pdf_path, doc_type=doc_type, use_llm_norm=use_llm_norm)


async def extract_requirements_async(
    pdf_path: str,
    doc_type: str = "TechSpec",
    use_llm_norm: bool = False,
    progress_callback: Optional[Callable] = None,
) -> List[Dict[str, Any]]:
    """Async entry point -- for FastAPI / running event loops."""
    loop = ExtractionEventLoop()
    if progress_callback:
        loop.on_progress(progress_callback)
    return await loop.run(pdf_path=pdf_path, doc_type=doc_type, use_llm_norm=use_llm_norm)


# ─── Demo / CLI entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extraction_event_loop.py <pdf_path> [doc_type]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    doc_type = sys.argv[2] if len(sys.argv) > 2 else "TechSpec"

    print(f"\n\n [DEBUG] Extracting from {pdf_path} [{doc_type}] \n\n")
    results = asyncio.run(extract_requirements_async(pdf_path, doc_type=doc_type, use_llm_norm=True))
    print(f"[DEBUG] \nTotal: {len(results)} requirements extracted \n\n")

    # Save results as JSON
    output_dir = Path(pdf_path).parent / "output_req_extracted"
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(pdf_path).stem
    output_file = output_dir / f"{base_name}_req_extracted.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[DEBUG] Saved {len(results)} requirements to {output_file}")

    count = 1
    for req in results[:5]:
        if count == 1:
            print("[DEBUG] ", req, end="\n\n")
            count+=1
        print(f"[DEBUG]  [{req['id']}] ({req['category']}/{req.get('sub_category','?')}) "
              f"conf={req['confidence']:.2f} => \n {req['text'][:80]}...")
    if len(results) > 5:
        print(f"  ... and {len(results) - 5} more")
