from __future__ import annotations

from app.core.config import settings
from app.services.adapters.base import Adapter
from app.services.adapters.uniprot import resolve_uniprot_accession, resolve_uniprot_entry
from app.services.http_client import get_json, post_text


class PathwaysAdapter(Adapter):
    name = "Reactome"

    def fetch(self, query: str, context: dict | None = None) -> dict:
        organism_taxon_id = (context or {}).get("organism_taxon_id")
        accession = resolve_uniprot_accession(query, organism_taxon_id=organism_taxon_id)
        entry = resolve_uniprot_entry(query, organism_taxon_id=organism_taxon_id)
        if not accession and not entry:
            return {}

        pathways: list[dict] = []
        if accession:
            url = f"{settings.reactome_base_url}/data/mapping/UniProt/{accession}/pathways"
            data = get_json(url)
            if data:
                pathways = self._map_pathways(data)

        if not pathways:
            gene = self._resolve_gene_symbol(entry, query)
            organism_name = (entry.get("organism", {}) or {}).get("scientificName") if entry else None
            pathways = self._analysis_fallback(gene, organism_name)

        return {"pathways": pathways, "provenance": {"pathways": "Reactome (live)"}}

    def _map_pathways(self, data: list[dict]) -> list[dict]:
        pathways = []
        for item in data:
            name = item.get("displayName")
            if not name:
                continue
            pathways.append({"name": name, "source": "Reactome", "role": None})
        return pathways

    def _analysis_fallback(self, gene: str, organism_name: str | None) -> list[dict]:
        if not gene:
            return []
        url = f"{settings.reactome_analysis_base_url}/identifiers/"
        params = {"species": organism_name} if organism_name else None
        data = post_text(
            url,
            data=gene,
            params=params,
            headers={"content-type": "text/plain"},
        )
        if not data:
            return []
        pathways = []
        for item in data.get("pathways", []) or []:
            name = item.get("name") or item.get("displayName") or item.get("pathway")
            if not name:
                continue
            pathways.append({"name": name, "source": "Reactome", "role": None})
        return pathways

    def _resolve_gene_symbol(self, entry: dict | None, fallback: str) -> str:
        if not entry:
            return fallback
        genes = entry.get("genes", []) or []
        if genes:
            gene_name = (genes[0].get("geneName") or {}).get("value")
            if gene_name:
                return gene_name
        return fallback
