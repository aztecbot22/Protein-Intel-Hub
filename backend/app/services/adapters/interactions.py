from __future__ import annotations

from app.core.config import settings
from app.services.adapters.base import Adapter
from app.services.adapters.uniprot import resolve_uniprot_entry
from app.services.http_client import get_json


class InteractionsAdapter(Adapter):
    name = "STRING"

    def fetch(self, query: str, context: dict | None = None) -> dict:
        organism_taxon_id = (context or {}).get("organism_taxon_id")
        entry = resolve_uniprot_entry(query, organism_taxon_id=organism_taxon_id)
        if not entry:
            return {}

        gene = self._resolve_gene_symbol(entry, query)
        taxon = (entry.get("organism", {}) or {}).get("taxonId") or 9606

        url = f"{settings.string_base_url}/json/network"
        data = get_json(
            url,
            params={
                "identifiers": gene,
                "species": taxon,
                "limit": 15,
            },
        )
        if not data or not isinstance(data, list):
            return {}

        nodes = {}
        edges = []
        for link in data:
            source = link.get("preferredName_A")
            target = link.get("preferredName_B")
            if not source or not target:
                continue
            nodes[source] = {"id": source, "label": source, "type": "protein"}
            nodes[target] = {"id": target, "label": target, "type": "protein"}
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "evidence": "STRING",
                    "score": link.get("score"),
                }
            )

        interactions = {"nodes": list(nodes.values()), "edges": edges}
        return {"interactions": interactions, "provenance": {"interactions": "STRING (live)"}}

    def _resolve_gene_symbol(self, entry: dict, fallback: str) -> str:
        genes = entry.get("genes", []) or []
        if genes:
            gene_name = (genes[0].get("geneName") or {}).get("value")
            if gene_name:
                return gene_name
        return fallback
