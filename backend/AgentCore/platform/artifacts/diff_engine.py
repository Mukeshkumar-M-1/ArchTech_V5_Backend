"""
Diff Engine

Computes precise diffs before applying changes to the filesystem.
This ensures preview, approval, and safe rollback capabilities.
"""

import logging
import difflib

log = logging.getLogger(__name__)

class DiffEngine:
    def __init__(self):
        log.info("[DiffEngine] Initialized.")

    def generate_diff(self, original: str, modified: str, filename: str) -> str:
        log.info(f"[DiffEngine] Computing diff for {filename}")
        
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}"
        )
        return "".join(diff)
