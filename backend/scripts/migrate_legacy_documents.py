import os
import sys
import json
import asyncio
from pathlib import Path

# Add backend directory to sys.path to allow imports
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
sys.path.append(str(backend_dir))

from models.document import init_db
from repositories.document_repository import DocumentRepository
from system_config import get_database_dir

async def migrate_documents():
    """
    Migrates legacy documents (stored solely as files) into the SQLite database.
    """
    # Ensure database is initialized
    await init_db()
    repo = DocumentRepository()

    workspace_root = get_database_dir() # Workspaces are generally parallel to DB or in AppData
    # Actually system_config.py has get_project_workspace_dir(project_id)
    # Since we need to iterate over projects, let's assume they are stored in an 'ArchTech_Workspaces' dir or similar.
    # We will search the database directory for project folders.
    
    # We need to know where projects are stored. Let's import the real function
    from system_config import get_project_workspace_dir
    
    print("Starting legacy document migration...")
    
    # In ArchTech, typically project workspace root is 'Database/workspaces' or similar.
    # I'll iterate through projects if there is a known list, or just scan the directory.
    db_dir = Path(get_database_dir())
    if not db_dir.exists():
        print(f"Database directory {db_dir} does not exist. Aborting.")
        return
        
    projects_dir = db_dir.parent / "projects"  # Assuming standard ArchTech structure, adjust if needed
    if not projects_dir.exists():
        # Fallback to scanning db_dir itself for potential workspaces
        projects_dir = db_dir

    migrated_count = 0
    skipped_count = 0

    for project_path in projects_dir.iterdir():
        if not project_path.is_dir():
            continue
            
        project_id = project_path.name
        docs_dir = project_path / "documents"
        
        if not docs_dir.exists():
            continue
            
        for doc_path in docs_dir.iterdir():
            if not doc_path.is_dir():
                continue
                
            document_id = doc_path.name
            json_file = doc_path / "document.json"
            
            if not json_file.exists():
                continue
                
            # Check if it already exists in the database
            existing_doc = await repo.get_document(document_id)
            if existing_doc:
                skipped_count += 1
                continue
                
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    content_json = json.load(f)
                    
                # Create base document in DB
                doc = await repo.create_document(
                    project_id=project_id,
                    document_id=document_id,
                    content_json=content_json,
                    created_by="system_migration"
                )
                
                print(f"Migrated document {document_id} for project {project_id}")
                migrated_count += 1
            except Exception as e:
                print(f"Error migrating {document_id}: {e}")

    print(f"Migration complete! Migrated: {migrated_count}, Skipped (already in DB): {skipped_count}")

if __name__ == "__main__":
    asyncio.run(migrate_documents())
