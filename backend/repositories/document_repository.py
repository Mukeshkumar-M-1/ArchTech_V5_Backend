import hashlib
import json
from typing import Optional, List, Tuple
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from system_config import get_database_dir
from models.document import Base, Document, DocumentRevision

# Setup SQLite database
DATABASE_PATH = get_database_dir() / "archtech.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_document_by_id(self, document_id: str) -> Optional[Document]:
        return self.db.query(Document).filter(Document.id == document_id, Document.deleted_at == None).first()

    def create_document(self, project_id: str, title: str, content_json: dict, schema_version: int = 1, document_id: Optional[str] = None) -> Document:
        new_doc = Document(
            project_id=project_id,
            title=title,
            content_json=content_json,
            schema_version=schema_version,
            current_version=1
        )
        if document_id:
            new_doc.id = document_id

        self.db.add(new_doc)
        self.db.commit()
        self.db.refresh(new_doc)
        return new_doc

    def update_document_content(self, document_id: str, content_json: dict, new_version: int) -> Optional[Document]:
        doc = self.get_document_by_id(document_id)
        if doc:
            doc.content_json = content_json
            doc.current_version = new_version
            self.db.commit()
            self.db.refresh(doc)
        return doc

    def generate_content_hash(self, content_json: dict) -> str:
        content_str = json.dumps(content_json, sort_keys=True)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    def create_revision(self, document_id: str, version: int, content_json: dict, change_type: str, schema_version: int = 1) -> DocumentRevision:
        content_hash = self.generate_content_hash(content_json)
        
        # Check if the exact same content hash exists for this document
        existing = self.db.query(DocumentRevision).filter(
            DocumentRevision.document_id == document_id,
            DocumentRevision.content_hash == content_hash
        ).first()

        if existing:
            # Prevent duplicate revision if content is exactly the same, unless we want to force it
            pass 
        
        rev = DocumentRevision(
            document_id=document_id,
            version=version,
            content_json=content_json,
            schema_version=schema_version,
            change_type=change_type,
            content_hash=content_hash
        )
        self.db.add(rev)
        self.db.commit()
        self.db.refresh(rev)
        return rev

    def get_revisions(self, document_id: str) -> List[DocumentRevision]:
        return self.db.query(DocumentRevision).filter(
            DocumentRevision.document_id == document_id
        ).order_by(DocumentRevision.version.desc()).all()

    def get_revision_by_version(self, document_id: str, version: int) -> Optional[DocumentRevision]:
        return self.db.query(DocumentRevision).filter(
            DocumentRevision.document_id == document_id,
            DocumentRevision.version == version
        ).first()
