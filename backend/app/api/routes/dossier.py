from fastapi import APIRouter, HTTPException, Query

from app.schemas.dossier import Dossier
from app.services.dossier_service import DossierService


router = APIRouter(prefix="/proteins", tags=["proteins"])
service = DossierService()


@router.get("/{query}/dossier", response_model=Dossier)
def get_dossier(
    query: str,
    organism_taxon_id: int | None = Query(default=None, ge=1),
    topic: str | None = Query(default=None, max_length=120),
    variant_page: int = Query(default=1, ge=1),
    variant_page_size: int = Query(default=10, ge=1, le=50),
    variant_sort: str = Query(default="significance", pattern="^(significance|date)$"),
    literature_page: int = Query(default=1, ge=1),
    literature_page_size: int = Query(default=10, ge=1, le=50),
    literature_year_from: int | None = Query(default=None, ge=1900, le=2100),
    literature_year_to: int | None = Query(default=None, ge=1900, le=2100),
    literature_sort: str = Query(default="date", pattern="^(date|relevance|citation|ml)$"),
) -> Dossier:
    try:
        context = {
            "organism_taxon_id": organism_taxon_id,
            "topic": topic,
            "variant_page": variant_page,
            "variant_page_size": variant_page_size,
            "variant_sort": variant_sort,
            "literature_page": literature_page,
            "literature_page_size": literature_page_size,
            "literature_year_from": literature_year_from,
            "literature_year_to": literature_year_to,
            "literature_sort": literature_sort,
        }
        return service.build(query, context=context)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
