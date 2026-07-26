"""
test_memory_agent.py — Standalone test script for MemoryManagementAgent.

Runs MemoryManagementAgent on a sample project and verifies the output.

Usage:
    python -m Memory_Management.test_memory_agent
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Memory_Management.memory_management_agent import MemoryManagementAgent

Peoject_ID = "Sample_1"

async def test_memory_agent():
    """Run MemoryManagementAgent on Sample_1 and verify output files."""
    agent = MemoryManagementAgent()

    print("[Test] Running MemoryManagementAgent on project 'Sample_1'...")
    stats = await agent.run(project_id=Peoject_ID)

    print("\n[Phase Stats]:")
    for phase, result in stats.items():
        if phase != "project_id":
            print(f"  {phase}: {result}")

    # Verify output files
    from system_config import get_knowledge_source_dir

    knowledge_dir = Path(get_knowledge_source_dir(project_id=Peoject_ID))

    print(f"\n[Verification] Checking output in: {knowledge_dir}")

    expected_dirs = ["requirements", "categories", "subcategories"]
    expected_files = ["overview.md", "relationships.md"]

    for d in expected_dirs:
        dir_path = knowledge_dir / d
        if dir_path.exists():
            count = len(list(dir_path.glob("*.md")))
            print(f"  ✓ {d}/ — {count} .md files")
        else:
            print(f"  ✗ {d}/ — MISSING")

    for f in expected_files:
        fpath = knowledge_dir / f
        if fpath.exists():
            print(f"  ✓ {f} — exists")
        else:
            print(f"  ✗ {f} — MISSING")

    req_files = list((knowledge_dir / "requirements").glob("*.md")) if (knowledge_dir / "requirements").exists() else []
    print(f"\n[Test] Total requirement .md files created: {len(req_files)}")


if __name__ == "__main__":
    asyncio.run(test_memory_agent())
