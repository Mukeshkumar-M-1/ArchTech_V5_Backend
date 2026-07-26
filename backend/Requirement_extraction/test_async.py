#!/usr/bin/env python3
"""Test script for both sync and async entry points."""

import asyncio
import sys
from extraction_event_loop import extract_requirements, extract_requirements_async

PDF_PATH = "/home/devusr/Mukesh/ArchTech_V5/Backend/uploads/batch_2e49b875/DP-XMC-5049-000-HRS-0V04.pdf"


def test_sync():
    print("=== Testing extract_requirements (sync) ===")
    results = extract_requirements(PDF_PATH, doc_type="HRS", use_llm_norm=True)
    print(f"  Total: {len(results)} requirements\n")
    for r in results[:3]:
        print(f"  [{r['id']}] ({r['category']}) conf={r['confidence']:.2f}: {r['text'][:80]}")


async def test_async():
    print("\n=== Testing extract_requirements_async ===")
    results = await extract_requirements_async(PDF_PATH, doc_type="HRS", use_llm_norm=True)
    print(f"  Total: {len(results)} requirements\n")
    for r in results[:3]:
        print(f"  [{r['id']}] ({r['category']}) conf={r['confidence']:.2f}: {r['text'][:80]}")


if __name__ == "__main__":
    # Test sync
    # test_sync()
    # Test async
    asyncio.run(test_async())
