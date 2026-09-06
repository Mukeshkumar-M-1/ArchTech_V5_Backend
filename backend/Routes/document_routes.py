from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from repositories.document_repository import get_db, init_db
from services.document_service import DocumentService
from schemas.document_schema import (
    DocumentCreate, 
    DocumentResponse, 
    DocumentUpdate, 
    DocumentSaveResponse, 
    DocumentRevisionResponse,
    DocumentRevisionDetailResponse
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.on_event("startup")
def startup_event():
    init_db()

def get_document_service(db: Session = Depends(get_db)):
    return DocumentService(db)

@router.post("", response_model=DocumentResponse)
def create_document(doc_in: DocumentCreate, service: DocumentService = Depends(get_document_service)):
    return service.create_document(doc_in)

@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, service: DocumentService = Depends(get_document_service)):
    return service.get_document(document_id)

@router.patch("/{document_id}", response_model=DocumentSaveResponse)
def update_document(document_id: str, update_in: DocumentUpdate, service: DocumentService = Depends(get_document_service)):
    updated_doc = service.update_document(document_id, update_in)
    return DocumentSaveResponse(
        id=updated_doc.id,
        version=updated_doc.current_version,
        saved=True,
        updated_at=updated_doc.updated_at or updated_doc.created_at or datetime.now(timezone.utc)
    )

@router.get("/{document_id}/revisions", response_model=List[DocumentRevisionResponse])
def get_document_revisions(document_id: str, service: DocumentService = Depends(get_document_service)):
    return service.get_revisions(document_id)

@router.get("/{document_id}/revisions/{version}", response_model=DocumentRevisionDetailResponse)
def get_document_revision(document_id: str, version: int, service: DocumentService = Depends(get_document_service)):
    return service.get_revision(document_id, version)
