from datetime import datetime

from pydantic import BaseModel


class AnnotationCreate(BaseModel):
    content: str


class AnnotationOut(BaseModel):
    id: int
    protein_id: str
    author_id: int
    author_name: str
    content: str
    source: str
    created_at: datetime

    class Config:
        from_attributes = True
