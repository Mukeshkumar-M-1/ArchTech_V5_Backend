"""
Repository Intelligence Tests

Tests both the original Python-code indexing path and the new .ArchTech
document-repo indexing path. Assertions check behavior ("returns results"),
not fixed sizes — repositories evolve so tests must not break on size changes.
"""

import logging
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from AgentCore.repository.repo_snapshot import SnapshotManager
from AgentCore.repository.repo_index import RepositoryIndex
from AgentCore.repository.repo_query_engine import RepositoryQueryEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def test_python_repository():
    """Original test — Python AST symbol indexing."""
    root_dir = Path("/home/devusr/Mukesh/ArchTech_V5_1/Backend/backend/AgentCore/repository")

    snapshot_manager = SnapshotManager(root_path=str(root_dir))
    snapshot_data = snapshot_manager.create_snapshot()
    print(f"\n[Test] Snapshot created with {len(snapshot_data.files)} files.\n")

    # Verify all paths are relative
    for file_path in snapshot_data.files:
        assert not Path(file_path).is_absolute(), f"Path must be relative: {file_path}"

    repo_index = RepositoryIndex(snapshot=snapshot_data)
    repo_index.build()
    engine = RepositoryQueryEngine(repo_index=repo_index)

    print("\n--- Testing Symbol Lookup ---")
    symbols = engine.find_symbol("RepositoryIndex")
    for s in symbols:
        print(f"  Found {s.name} ({s.symbol_type}) in {s.file_path} at lines {s.line_start}-{s.line_end}")
    assert symbols, "Should find RepositoryIndex class"

    print("\n--- Testing File Summary ---")
    summary = engine.summarize_file("repo_index.py")
    assert "RepositoryIndex" in summary or "Symbol" in summary
    print(summary)


def test_archtech_repository():
    """Test repository module against .ArchTech document repos."""
    archtech_project_root = Path("/home/devusr/Mukesh/ArchTech_V5_1/Backend/.ArchTech/DP-SPL-0502")

    print("\n" + "=" * 70)
    print("ArchTech Document Repository Test")
    print("=" * 70)

    # 1. Snapshot captures files with relative paths
    snapshot_manager = SnapshotManager(str(archtech_project_root))
    snapshot = snapshot_manager.create_snapshot()
    assert snapshot.files, "Snapshot should contain files"

    for file_path in snapshot.files:
        assert not Path(file_path).is_absolute(), f"Path must be relative: {file_path}"

    # Ignored dirs excluded
    for file_path in snapshot.files:
        assert "output_req_extracted" not in file_path
        assert "transcripts" not in file_path

    print(f"[1] Snapshot: {len(snapshot.files)} files captured with relative paths.")

    # 2. Index builds successfully
    repo_index = RepositoryIndex(snapshot)
    repo_index.build()
    engine = RepositoryQueryEngine(repo_index)

    assert repo_index.requirements.requirement_locations, "Should have indexed requirements"
    print(f"[2] Index: {len(repo_index.requirements.requirement_locations)} requirement IDs found.")

    # 3. Exact requirement lookup returns results
    results = engine.find_requirement("HAR-0001")
    assert results, "HAR-0001 should be found"
    assert len(results) >= 2, "HAR-0001 should appear in both .md and requirements.json"

    for r in results:
        if r.metadata and r.metadata.get("category"):
            assert r.metadata.get("category") == "Hardware", \
                f"HAR-0001 category should be Hardware, got {r.metadata.get('category')}"
    print(f"[3] find_requirement('HAR-0001'): {len(results)} locations.")

    # 4. Category filter returns results
    hardware_reqs = engine.find_requirements_by_category("Hardware")
    assert hardware_reqs, "Hardware category should have requirements"
    print(f"[4] find_requirements_by_category('Hardware'): {len(hardware_reqs)} locations.")

    # 5. Cross-references resolve correctly
    related = engine.get_related_requirements("HAR-0001")
    assert "HAR-0043" in related, f"HAR-0043 should be related to HAR-0001, got: {related}"
    print(f"[5] get_related_requirements('HAR-0001'): {related}")

    # 6. Template placeholders extracted
    templates = engine.get_project_files_by_type("template")
    assert templates, "Should find template files"

    found_placeholders = False
    for tmpl_path in templates[:5]:
        ph = engine.get_placeholders(tmpl_path)
        if ph:
            found_placeholders = True
            print(f"[6] Template '{tmpl_path}' placeholders: {ph[:5]}...")
    assert found_placeholders, "Template files should contain placeholders"

    # 7. Version info available
    version_meta = engine.get_version_info()
    assert version_meta, "Version file should be indexed"
    print(f"[7] Version info: {version_meta}")

    # 8. File summaries include format-specific info
    req_files = engine.get_project_files_by_type("requirement")
    assert req_files, "Should find requirement files"

    if req_files:
        summary = engine.summarize_file(req_files[0])
        assert "HAR" in summary or "FUN" in summary or "SOF" in summary or "NFR" in summary, \
            f"Requirement summary should mention requirement IDs. Got: {summary[:200]}"
        print(f"[8] File summary sample:\n{summary[:300]}")

    # 9. Keyword search uses inverted index
    keyword_results = engine.find_requirements_by_keyword("ethernet")
    assert keyword_results, "Ethernet keyword should match requirements"
    print(f"[9] find_requirements_by_keyword('ethernet'): {len(keyword_results)} locations.")

    # 10. Invalid regex patterns do NOT match (strictness check)
    false_matches = engine.find_requirement("HTTP-2000")
    assert not false_matches, "HTTP-2000 should not be treated as a requirement ID"
    print("[10] Strictness: find_requirement('HTTP-2000') correctly returns empty.")

    # 11. Incremental rebuild test
    modified_snapshot = snapshot_manager.create_snapshot(incremental=True)
    repo_index.rebuild(modified_snapshot)
    assert repo_index.requirements.requirement_locations, "Rebuild should preserve index"
    print("[11] Incremental rebuild: index preserved.")

    print("\n" + "=" * 70)
    print("All ArchTech tests passed.")
    print("=" * 70 + "\n")


def main():
    """Run all repository intelligence tests."""
    print("Starting Repository Intelligence Tests\n")
    test_python_repository()
    test_archtech_repository()
    print("\nAll tests completed successfully.")


if __name__ == "__main__":
    main()