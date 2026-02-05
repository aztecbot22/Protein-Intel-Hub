import csv
from io import StringIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.dossier_service import DossierService


router = APIRouter(prefix="/export", tags=["export"])
service = DossierService()


@router.get("/variants")
def export_variants(query: str):
    try:
        dossier = service.build(query)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "variant_id",
            "hgvs",
            "protein_change",
            "aa_position",
            "classification",
            "condition",
            "species",
            "review_status",
            "conflicts",
            "pmids",
        ]
    )
    for variant in dossier.variants:
        writer.writerow(
            [
                variant.variant_id,
                variant.hgvs or "",
                variant.protein_change or "",
                variant.aa_position or "",
                variant.classification or "",
                variant.condition or "",
                variant.species or "",
                variant.review_status or "",
                "; ".join(variant.conflicts or []),
                "; ".join(variant.pmids or []),
            ]
        )

    output.seek(0)
    headers = {"Content-Disposition": f"attachment; filename={query}_variants.csv"}
    return StreamingResponse(output, media_type="text/csv", headers=headers)
