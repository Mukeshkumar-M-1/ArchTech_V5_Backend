import logging
from pathlib import Path

# Adjust imports for running as a script inside AgentCore directory
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from AgentCore.repository.snapshot import SnapshotManager
from AgentCore.repository.index import RepositoryIndex
from AgentCore.repository.query_engine import RepositoryQueryEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    # Use the AgentCore directory as the root for our snapshot
    root_dir = Path(__file__).parent.parent
    
    # 1. Create Snapshot
    manager = SnapshotManager(str(root_dir))
    snapshot = manager.create_snapshot()
    print(f"\n[Test] Snapshot created with {len(snapshot.files)} files.\n")
    
    # 2. Build Index
    index = RepositoryIndex(snapshot)
    index.build()
    
    # 3. Query Engine
    engine = RepositoryQueryEngine(index)
    
    print("\n--- Testing Symbol Lookup ---")
    symbols = engine.find_symbol("ExecutionEngine")
    for s in symbols:
        print(f"Found {s.name} ({s.symbol_type}) in {s.file_path} at lines {s.line_start}-{s.line_end}")

    print("\n--- Testing File Summary ---")
    # Let's summarize the kernel file
    kernel_summary = engine.summarize_file("core/agent_kernel.py")
    print(kernel_summary)

if __name__ == "__main__":
    main()
