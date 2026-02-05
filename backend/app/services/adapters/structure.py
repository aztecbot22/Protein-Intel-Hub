from __future__ import annotations

from app.core.config import settings
from app.services.adapters.base import Adapter
from app.services.adapters.uniprot import resolve_uniprot_accession, resolve_uniprot_entry
from app.services.http_client import get_json


class StructureAdapter(Adapter):
    name = "PDB/AlphaFold"

    def fetch(self, query: str, context: dict | None = None) -> dict:
        organism_taxon_id = (context or {}).get("organism_taxon_id")
        accession = resolve_uniprot_accession(query, organism_taxon_id=organism_taxon_id)
        entry = resolve_uniprot_entry(query, organism_taxon_id=organism_taxon_id)
        if not accession or not entry:
            return {}

        pdb_ids = self._extract_pdb_ids(entry)
        predicted_domains = self._extract_domains(entry)
        binding_sites, binding_sites_detail = self._extract_binding_sites(entry)
        alphafold_id, alphafold_files = self._fetch_alphafold_data(accession)
        druggability_flags = self._heuristics(entry, binding_sites, alphafold_id, pdb_ids)

        structure = {
            "pdb_ids": pdb_ids,
            "alphafold_id": alphafold_id,
            "alphafold_files": alphafold_files,
            "predicted_domains": predicted_domains,
            "binding_sites": binding_sites,
            "binding_sites_detail": binding_sites_detail,
            "druggability_flags": druggability_flags,
        }

        return {"structure": structure, "provenance": {"structure": "PDB/AlphaFold (live)"}}

    def _extract_pdb_ids(self, entry: dict) -> list[str]:
        ids = []
        for ref in entry.get("uniProtKBCrossReferences", []) or []:
            if ref.get("database") == "PDB" and ref.get("id"):
                ids.append(ref["id"])
        return sorted(set(ids))

    def _extract_binding_sites(self, entry: dict) -> tuple[list[str], list[dict]]:
        sites = []
        details = []
        seen = set()
        for feature in entry.get("features", []) or []:
            if feature.get("type") not in {"BINDING", "ACT_SITE", "SITE", "METAL"}:
                continue
            desc = feature.get("description") or feature.get("type") or "Binding site"
            location = feature.get("location", {}) or {}
            start = (location.get("start", {}) or {}).get("value")
            end = (location.get("end", {}) or {}).get("value")
            label = desc
            if start or end:
                label = f"{desc} ({start or end}-{end or start})"
            if label not in sites:
                sites.append(label)
            key = (desc, start, end)
            if key not in seen:
                seen.add(key)
                details.append({"label": desc, "start": start, "end": end})
        for comment in entry.get("comments", []) or []:
            if comment.get("commentType") == "COFACTOR":
                for cofactor in comment.get("cofactors", []) or []:
                    name = (cofactor.get("name") or "").strip()
                    if not name:
                        continue
                    label = f"Cofactor: {name}"
                    if label not in sites:
                        sites.append(label)
                    key = (label, None, None)
                    if key not in seen:
                        seen.add(key)
                        details.append({"label": label, "start": None, "end": None})
        for keyword in entry.get("keywords", []) or []:
            name = (keyword or {}).get("name")
            if not name:
                continue
            if "binding" in name.lower() and name not in sites:
                sites.append(name)
                key = (name, None, None)
                if key not in seen:
                    seen.add(key)
                    details.append({"label": name, "start": None, "end": None})
        return sites, details

    def _extract_domains(self, entry: dict) -> list[dict]:
        domains = []
        for feature in entry.get("features", []) or []:
            if feature.get("type") not in {"DOMAIN", "REGION", "REPEAT", "MOTIF"}:
                continue
            location = feature.get("location", {}) or {}
            start = (location.get("start", {}) or {}).get("value")
            end = (location.get("end", {}) or {}).get("value")
            name = feature.get("description") or feature.get("type", "Domain")
            domains.append(
                {
                    "name": name,
                    "start": start,
                    "end": end,
                    "source": "UniProt",
                }
            )
        if not domains:
            for ref in entry.get("uniProtKBCrossReferences", []) or []:
                db = ref.get("database")
                if db not in {"InterPro", "Pfam", "SMART", "PROSITE", "CDD"}:
                    continue
                props = {item.get("key"): item.get("value") for item in ref.get("properties", []) or []}
                name = props.get("EntryName") or props.get("entryName") or props.get("Name") or ref.get("id")
                if name:
                    domains.append(
                        {
                            "name": name,
                            "start": None,
                            "end": None,
                            "source": db,
                        }
                    )
        return domains

    def _fetch_alphafold_data(self, accession: str) -> tuple[str | None, list[dict]]:
        url = f"{settings.alphafold_base_url}/prediction/{accession}"
        data = get_json(url)
        if not data or not isinstance(data, list):
            return None, []
        first = data[0] if data else None
        if not isinstance(first, dict):
            return None, []
        entry_id = first.get("entryId") or first.get("modelId") or first.get("model_id")
        files = self._extract_alphafold_files(first)
        return entry_id, files

    def _extract_alphafold_files(self, data: dict) -> list[dict]:
        files = []
        label_map = {
            "pdbUrl": "PDB file",
            "cifUrl": "mmCIF file",
            "paeImageUrl": "PAE image",
            "paeUrl": "PAE JSON",
            "jsonUrl": "Model JSON",
            "modelUrl": "Model summary",
        }
        for key, label in label_map.items():
            url = data.get(key)
            if url:
                files.append({"label": label, "url": url})
        for key, value in data.items():
            if not isinstance(value, str) or not key.endswith("Url"):
                continue
            if any(file["url"] == value for file in files):
                continue
            files.append({"label": key, "url": value})
        return files

    def _heuristics(
        self,
        entry: dict,
        binding_sites: list[str],
        alphafold_id: str | None,
        pdb_ids: list[str],
    ) -> list[str]:
        flags = []
        if any(comment.get("commentType") == "SUBCELLULAR LOCATION" for comment in entry.get("comments", [])):
            flags.append("Subcellular localization known")
        if any(feature.get("type") == "TRANSMEM" for feature in entry.get("features", [])):
            flags.append("Membrane protein (likely druggable)")
        if any(comment.get("commentType") == "CATALYTIC ACTIVITY" for comment in entry.get("comments", [])):
            flags.append("Catalytic activity annotated")
        if binding_sites:
            flags.append("Ligand/active site annotations available")
        if alphafold_id:
            flags.append("AlphaFold structure available")
        if pdb_ids:
            flags.append("Experimental PDB structures available")
        flags += self._keyword_flags(entry)
        return list(dict.fromkeys(flags))

    def _keyword_flags(self, entry: dict) -> list[str]:
        flags = []
        for keyword in entry.get("keywords", []) or []:
            name = (keyword or {}).get("name")
            if not name:
                continue
            if "Kinase" in name or "Phosphotransferase" in name:
                flags.append("Kinase activity")
            if "Receptor" in name:
                flags.append("Receptor protein")
            if "Ion channel" in name:
                flags.append("Ion channel")
            if "Transcription" in name:
                flags.append("Transcription factor")
        return flags
