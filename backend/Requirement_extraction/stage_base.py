"""
stage_base.py — Base classes for pipeline stages and events.
Shared by all stage modules and the coordinator.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class PipelineEvent:
    """Event emitted by the pipeline at each stage boundary."""
    __slots__ = ("stage", "status", "message", "page", "segment",
                 "counters", "metadata")

    def __init__(
        self,
        stage: str,
        status: str,
        message: str = "",
        page: Optional[int] = None,
        segment: Optional[int] = None,
        counters: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ):
        self.stage = stage
        self.status = status
        self.message = message
        self.page = page
        self.segment = segment
        self.counters = counters or {}
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"PipelineEvent({self.stage}={self.status}, {self.message})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "message": self.message,
            "page": self.page,
            "segment": self.segment,
            "counters": self.counters,
            "metadata": self.metadata,
        }
