from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class DocumentBase(BaseModel):
    project_id: str
    title: str
    content: Dict[str, Any] = Field(..., description="Structured Tiptap JSON content")
    schema_version: int = Field(default=1)

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    base_version: int
    content: Dict[str, Any]
    change_type: str = Field(default="USER_EDIT", description="Type of change: USER_EDIT, AI_GENERATION, etc.")
    project_id: Optional[str] = None
    title: Optional[str] = None

class DocumentResponse(DocumentBase):
    id: str
    version: int
    updated_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentRevisionResponse(BaseModel):
    id: str
    document_id: str
    version: int
    schema_version: int
    created_at: datetime
    change_type: str
    content_hash: str

    class Config:
        from_attributes = True

class DocumentRevisionDetailResponse(DocumentRevisionResponse):
    content: Dict[str, Any]

class DocumentSaveResponse(BaseModel):
    id: str
    version: int
    saved: bool = True
    updated_at: datetime
