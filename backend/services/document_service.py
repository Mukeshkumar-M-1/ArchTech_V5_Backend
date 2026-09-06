from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from repositories.document_repository import DocumentRepository
from schemas.document_schema import DocumentCreate, DocumentUpdate
from models.document import Document, DocumentRevision

class DocumentService:
    def __init__(self, db: Session):
        self.repo = DocumentRepository(db)

    def get_document(self, document_id: str) -> Document:
        doc = self.repo.get_document_by_id(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
        return doc

    def create_document(self, doc_in: DocumentCreate) -> Document:
        doc = self.repo.create_document(
            project_id=doc_in.project_id,
            title=doc_in.title,
            content_json=doc_in.content,
            schema_version=doc_in.schema_version
        )
        # Create initial revision
        self.repo.create_revision(
            document_id=doc.id,
            version=doc.current_version,
            content_json=doc.content_json,
            change_type="CREATE",
            schema_version=doc.schema_version
        )
        return doc

    def update_document(self, document_id: str, update_in: DocumentUpdate) -> Document:
        doc = self.repo.get_document_by_id(document_id)
        
        if not doc:
            if update_in.project_id:
                # Upsert behavior: create it if project_id is provided
                doc = self.repo.create_document(
                    project_id=update_in.project_id,
                    title=update_in.title or document_id,
                    content_json=update_in.content,
                    schema_version=1,
                    document_id=document_id
                )
                self.repo.create_revision(
                    document_id=doc.id,
                    version=doc.current_version,
                    content_json=doc.content_json,
                    change_type="CREATE",
                    schema_version=doc.schema_version
                )
                return doc
            else:
                raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
        
        if doc.current_version != update_in.base_version:
            if update_in.base_version > doc.current_version:
                # Legacy migration fallback: if frontend is ahead of SQLite DB, let the DB catch up
                doc.current_version = update_in.base_version
            else:
                # Frontend remounted with stale prop, or local conflict. 
                # Since this is a local single-user app, we will log a warning and force the update to prevent breaking the editor.
                import logging
                log = logging.getLogger(__name__)
                log.warning(f"Version mismatch for {document_id}: Server at {doc.current_version}, Client sent {update_in.base_version}. Forcing update.")

        new_version = doc.current_version + 1
        updated_doc = self.repo.update_document_content(
            document_id=document_id,
            content_json=update_in.content,
            new_version=new_version
        )
        
        # We assume the caller handles revision strategies. 
        # But for basic saves, we can create a revision. 
        # In a fully fleshed out system, this might defer to a persistence service that runs in background or checks limits.
        self.repo.create_revision(
            document_id=updated_doc.id,
            version=new_version,
            content_json=updated_doc.content_json,
            change_type=update_in.change_type,
            schema_version=updated_doc.schema_version
        )

        return updated_doc

    def get_revisions(self, document_id: str) -> List[DocumentRevision]:
        # Ensure document exists
        self.get_document(document_id)
        return self.repo.get_revisions(document_id)

    def get_revision(self, document_id: str, version: int) -> DocumentRevision:
        self.get_document(document_id)
        rev = self.repo.get_revision_by_version(document_id, version)
        if not rev:
            raise HTTPException(status_code=404, detail="REVISION_NOT_FOUND")
        return rev
