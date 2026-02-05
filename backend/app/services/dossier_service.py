from concurrent.futures import ThreadPoolExecutor, as_completed

from app.schemas.dossier import Dossier, Overview, Structure, Interactions
from app.services.adapters.clinvar import ClinVarAdapter
from app.services.adapters.interactions import InteractionsAdapter
from app.services.adapters.literature import LiteratureAdapter
from app.services.adapters.pathways import PathwaysAdapter
from app.services.adapters.structure import StructureAdapter
from app.services.adapters.uniprot import UniProtAdapter


class DossierService:
    def __init__(self) -> None:
        self.adapters = [
            UniProtAdapter(),
            ClinVarAdapter(),
            StructureAdapter(),
            PathwaysAdapter(),
            InteractionsAdapter(),
            LiteratureAdapter(),
        ]

    def build(self, query: str, context: dict | None = None) -> Dossier:
        payload: dict = {"query": query}
        provenance: dict[str, str] = {}
        results: list[dict | None] = [None] * len(self.adapters)
        with ThreadPoolExecutor(max_workers=len(self.adapters)) as executor:
            future_map = {
                executor.submit(adapter.fetch, query, context=context): index
                for index, adapter in enumerate(self.adapters)
            }
            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    results[index] = future.result()
                except Exception:
                    results[index] = None

        for result in results:
            if not result:
                continue
            provenance.update(result.pop("provenance", {}))
            payload.update(result)

        if not payload.get("overview"):
            raise ValueError("Protein not found")

        resolved_id = payload.get("resolved_id") or query
        structure = payload.get("structure") or {}
        interactions = payload.get("interactions") or {}

        provenance = {
            "overview": provenance.get("overview", "UniProt (not wired)"),
            "variants": provenance.get("variants", "ClinVar (not wired)"),
            "structure": provenance.get("structure", "PDB/AlphaFold (not wired)"),
            "pathways": provenance.get("pathways", "Reactome (not wired)"),
            "interactions": provenance.get("interactions", "STRING (not wired)"),
            "literature": provenance.get("literature", "PubMed (not wired)"),
        }

        study_suggestions = payload.get("study_suggestions") or []
        if payload.get("variants_overview"):
            counts = payload["variants_overview"].get("condition_counts", [])
            study_suggestions += [item["condition"] for item in counts if item.get("condition")]

        topic = (context or {}).get("topic")
        if topic:
            study_suggestions.append(topic)

        study_suggestions = self._dedupe_suggestions(study_suggestions)

        return Dossier(
            query=query,
            resolved_id=resolved_id,
            overview=Overview(**payload["overview"]),
            variants=payload.get("variants", []),
            variants_overview=payload.get("variants_overview"),
            structure=Structure(**structure) if structure else Structure(),
            pathways=payload.get("pathways", []),
            interactions=Interactions(**interactions) if interactions else Interactions(),
            literature=payload.get("literature", []),
            literature_overview=payload.get("literature_overview"),
            study_suggestions=study_suggestions,
            provenance=provenance,
        )

    @staticmethod
    def _dedupe_suggestions(values: list[str]) -> list[str]:
        seen = set()
        deduped = []
        for value in values:
            cleaned = value.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return deduped
