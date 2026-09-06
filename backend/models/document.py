import datetime
import uuid
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    content_json = Column(JSON, nullable=False, default=dict)
    schema_version = Column(Integer, nullable=False, default=1)
    current_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    revisions = relationship("DocumentRevision", back_populates="document", order_by="DocumentRevision.version")


class DocumentRevision(Base):
    __tablename__ = "document_revisions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content_json = Column(JSON, nullable=False)
    schema_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String, nullable=True)
    change_type = Column(String, nullable=False)  # e.g., USER_EDIT, AI_GENERATION, MANUAL_SAVE, etc.
    content_hash = Column(String, nullable=False, index=True)

    document = relationship("Document", back_populates="revisions")
