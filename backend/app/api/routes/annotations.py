from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.annotation import Annotation
from app.models.user import User
from app.schemas.annotation import AnnotationCreate, AnnotationOut


router = APIRouter(prefix="/proteins", tags=["annotations"])


@router.get("/{query}/notes", response_model=list[AnnotationOut])
def list_notes(query: str, db: Session = Depends(get_db)) -> list[Annotation]:
    protein_id = query.upper()
    return (
        db.query(Annotation)
        .filter(Annotation.protein_id == protein_id)
        .order_by(Annotation.created_at.desc())
        .all()
    )


@router.post("/{query}/notes", response_model=AnnotationOut)
def add_note(
    query: str,
    payload: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Annotation:
    protein_id = query.upper()
    note = Annotation(
        protein_id=protein_id,
        author_id=current_user.id,
        author_name=current_user.full_name or current_user.email,
        content=payload.content,
        source="user",
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note
