import os
import json
import tempfile
from pathlib import Path
from system_config import get_project_workspace_dir

class DocumentPersistenceService:
    def __init__(self):
        pass

    def _atomic_write_json(self, file_path: Path, data: dict):
        """
        Safely writes JSON data to a file using a temporary file and atomic rename.
        Ensures that data is flushed to disk before renaming.
        """
        # Create a temporary file in the same directory to ensure it's on the same filesystem
        dir_path = file_path.parent
        dir_path.mkdir(parents=True, exist_ok=True)
        
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
        
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomically replace the target file
            os.replace(tmp_path, file_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise e

    def _atomic_write_text(self, file_path: Path, text: str):
        dir_path = file_path.parent
        dir_path.mkdir(parents=True, exist_ok=True)
        
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
        
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            
            os.replace(tmp_path, file_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise e

    def get_document_directory(self, project_id: str, document_id: str) -> Path:
        base = get_project_workspace_dir(project_id)
        return base / "documents" / document_id

    def persist_document(self, project_id: str, document_id: str, content_json: dict) -> bool:
        """
        Persists the canonical JSON to the materialized representation.
        """
        doc_dir = self.get_document_directory(project_id, document_id)
        json_path = doc_dir / "document.json"
        
        try:
            self._atomic_write_json(json_path, content_json)
            return True
        except Exception as e:
            import logging
            logging.error(f"Failed to persist materialized document.json: {e}")
            return False
