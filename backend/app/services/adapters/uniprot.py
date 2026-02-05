from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.services.adapters.base import Adapter
from app.services.http_client import get_json


ACCESSION_RE = re.compile(r"^[A-Z0-9]{6,10}$")


@lru_cache(maxsize=256)
def resolve_uniprot_entry(query: str, organism_taxon_id: int | None = None) -> dict | None:
    if not query:
        return None
    query = query.strip()
    if ACCESSION_RE.match(query.upper()):
        entry = _fetch_entry(query.upper(), include_isoforms=True)
        if entry:
            return entry
    accession = _search_accession(query, organism_taxon_id=organism_taxon_id)
    if not accession:
        return None
    return _fetch_entry(accession, include_isoforms=True)


@lru_cache(maxsize=256)
def resolve_uniprot_accession(query: str, organism_taxon_id: int | None = None) -> str | None:
    entry = resolve_uniprot_entry(query, organism_taxon_id=organism_taxon_id)
    if not entry:
        return None
    return entry.get("primaryAccession")


def _fetch_entry(accession: str, include_isoforms: bool = False) -> dict | None:
    params = {"includeIsoforms": "true"} if include_isoforms else None
    url = f"{settings.uniprot_base_url}/uniprotkb/{accession}.json"
    data = get_json(url, params=params)
    if data:
        return data
    fallback_params = dict(params or {})
    fallback_params["format"] = "json"
    fallback_url = f"{settings.uniprot_base_url}/uniprotkb/{accession}"
    return get_json(fallback_url, params=fallback_params)


def _search_accession(query: str, organism_taxon_id: int | None = None) -> str | None:
    candidates = _build_queries(query, organism_taxon_id=organism_taxon_id)
    for candidate in candidates:
        url = f"{settings.uniprot_base_url}/uniprotkb/search"
        data = get_json(
            url,
            params={
                "query": candidate,
                "format": "json",
                "fields": "accession,organism_id,organism_name,id",
                "size": 10,
            },
        )
        if not data:
            continue
        results = data.get("results", [])
        if not results:
            continue
        if organism_taxon_id:
            matches = []
            unknown = []
            for result in results:
                organism = result.get("organism") or {}
                taxon_id = (
                    organism.get("taxonId")
                    or organism.get("taxon_id")
                    or result.get("organism_id")
                    or result.get("organismId")
                )
                if taxon_id is None:
                    unknown.append(result)
                elif taxon_id == organism_taxon_id:
                    matches.append(result)
            if matches:
                return matches[0].get("primaryAccession")
            if unknown and len(matches) == 0:
                return unknown[0].get("primaryAccession")
            continue
        return results[0].get("primaryAccession")

    if organism_taxon_id:
        fallback_candidates = _build_queries(query, organism_taxon_id=None)
        for candidate in fallback_candidates:
            url = f"{settings.uniprot_base_url}/uniprotkb/search"
            data = get_json(
                url,
                params={
                    "query": candidate,
                    "format": "json",
                    "fields": "accession,organism_id",
                    "size": 10,
                },
            )
            if not data:
                continue
            results = data.get("results", [])
            if not results:
                continue
            for result in results:
                taxon_id = (result.get("organism", {}) or {}).get("taxonId")
                if taxon_id == organism_taxon_id:
                    return result.get("primaryAccession")
        if query.isalnum() and len(query) <= 4 and not query[-1].isdigit():
            return _search_accession(f"{query}1", organism_taxon_id=organism_taxon_id)
    return None


def _build_queries(query: str, organism_taxon_id: int | None = None) -> list[str]:
    query = query.strip()
    if not query:
        return []
    if " " in query:
        return [_with_organism_filter(query, organism_taxon_id)]
    base = [f"gene_exact:{query}", f"gene:{query}"]
    if query.isalnum() and len(query) <= 6:
        base.append(f"gene:{query}*")
        base.append(f"id:{query}*")
        base.append(f"protein_name:{query}*")
    base += [f"accession:{query}", f"id:{query}", query, f"{query}*"]
    return [_with_organism_filter(item, organism_taxon_id) for item in base]


def _with_organism_filter(query: str, organism_taxon_id: int | None) -> str:
    if organism_taxon_id:
        return f"({query}) AND organism_id:{organism_taxon_id}"
    return query


class UniProtAdapter(Adapter):
    name = "UniProt"

    def fetch(self, query: str, context: dict | None = None) -> dict:
        organism_taxon_id = (context or {}).get("organism_taxon_id")
        entry = resolve_uniprot_entry(query, organism_taxon_id=organism_taxon_id)
        if not entry:
            return {}

        overview = self._map_overview(entry)
        if not overview.get("isoforms") and entry.get("primaryAccession"):
            entry_iso = _fetch_entry(entry.get("primaryAccession"), include_isoforms=True)
            if entry_iso:
                overview = self._map_overview(entry_iso)
        resolved_id = entry.get("primaryAccession") or query.upper()
        return {
            "overview": overview,
            "resolved_id": resolved_id,
            "provenance": {"overview": "UniProt (live)"},
        }

    def _map_overview(self, entry: dict[str, Any]) -> dict[str, Any]:
        protein_description = entry.get("proteinDescription", {}) or {}
        recommended = protein_description.get("recommendedName", {}) or {}
        protein_name = self._get_text_value(recommended.get("fullName")) or "Unknown protein"

        genes = entry.get("genes", []) or []
        gene_name = None
        if genes:
            gene_name = self._get_text_value(genes[0].get("geneName"))
        gene_name = gene_name or entry.get("uniProtkbId") or entry.get("primaryAccession") or "Unknown"

        organism = (entry.get("organism", {}) or {}).get("scientificName") or "Unknown organism"
        length = (entry.get("sequence", {}) or {}).get("length")

        isoforms = self._extract_isoforms(entry.get("comments", []) or [])
        domains = self._extract_domains(entry.get("features", []) or [])
        domains += self._extract_domain_cross_refs(entry)
        domains = self._dedupe_domains(domains)
        subcellular = self._extract_subcellular(entry.get("comments", []) or [])
        function_summary = self._extract_function(entry.get("comments", []) or [])
        caveats = self._extract_caveats(entry.get("comments", []) or [], entry.get("features", []) or [])
        key_annotations = self._extract_key_annotations(entry)
        cross_refs = self._extract_cross_refs(entry)

        return {
            "protein_name": protein_name,
            "gene": gene_name,
            "organism": organism,
            "length": length,
            "isoforms": isoforms,
            "domains": domains,
            "subcellular_locations": subcellular,
            "function_summary": function_summary,
            "caveats": caveats,
            "key_annotations": key_annotations,
            "cross_refs": cross_refs,
        }

    def _get_text_value(self, node: Any) -> str | None:
        if isinstance(node, dict):
            value = node.get("value")
            return value if isinstance(value, str) else None
        return None

    def _extract_function(self, comments: list[dict]) -> str:
        for comment in comments:
            if comment.get("commentType") == "FUNCTION":
                texts = comment.get("texts", [])
                if texts:
                    value = self._get_text_value(texts[0]) or ""
                    return self._truncate_summary(value)
        return "Function summary not available."

    def _extract_caveats(self, comments: list[dict], features: list[dict]) -> list[str]:
        caveats: list[str] = []
        for comment in comments:
            if comment.get("commentType") in {"CAUTION", "SEQUENCE CAUTION"}:
                for text in comment.get("texts", []) or []:
                    value = self._get_text_value(text)
                    if value:
                        caveats.append(value)
        for feature in features:
            if feature.get("type") == "CONFLICT":
                desc = feature.get("description")
                if desc:
                    caveats.append(desc)
        return caveats

    def _extract_subcellular(self, comments: list[dict]) -> list[str]:
        locations: list[str] = []
        for comment in comments:
            if comment.get("commentType") == "SUBCELLULAR LOCATION":
                for loc in comment.get("subcellularLocations", []) or []:
                    name = (loc.get("location", {}) or {}).get("value")
                    if name and name not in locations:
                        locations.append(name)
        return locations

    def _extract_isoforms(self, comments: list[dict]) -> list[str]:
        isoforms: list[str] = []
        for comment in comments:
            if comment.get("commentType") == "ALTERNATIVE PRODUCTS":
                for iso in comment.get("isoforms", []) or []:
                    iso_ids = iso.get("isoformIds", []) or []
                    name = self._get_text_value(iso.get("name"))
                    synonyms = [self._get_text_value(s) for s in iso.get("synonyms", []) or []]
                    sequence_id = iso.get("isoformSequenceId")
                    for value in iso_ids:
                        if value:
                            isoforms.append(value)
                    if sequence_id:
                        isoforms.append(sequence_id)
                    if name:
                        isoforms.append(name)
                    for synonym in synonyms:
                        if synonym:
                            isoforms.append(synonym)
        return self._dedupe_values(isoforms)

    def _dedupe_values(self, values: list[str]) -> list[str]:
        seen = set()
        deduped = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _extract_domains(self, features: list[dict]) -> list[dict]:
        domains: list[dict] = []
        for feature in features:
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
        return domains

    def _extract_domain_cross_refs(self, entry: dict[str, Any]) -> list[dict]:
        domains: list[dict] = []
        for ref in entry.get("uniProtKBCrossReferences", []) or []:
            db = ref.get("database")
            if db not in {"InterPro", "Pfam", "SMART", "PROSITE", "CDD"}:
                continue
            props = {item.get("key"): item.get("value") for item in ref.get("properties", []) or []}
            name = props.get("EntryName") or props.get("entryName") or props.get("Name") or ref.get("id")
            if not name:
                continue
            domains.append(
                {
                    "name": name,
                    "start": None,
                    "end": None,
                    "source": db,
                }
            )
        return domains

    def _dedupe_domains(self, domains: list[dict]) -> list[dict]:
        seen = set()
        deduped = []
        for domain in domains:
            key = (domain.get("name"), domain.get("start"), domain.get("end"), domain.get("source"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(domain)
        return deduped

    def _extract_cross_refs(self, entry: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        primary = entry.get("primaryAccession")
        if primary:
            refs.append(
                {
                    "db": "UniProt",
                    "id": primary,
                    "url": f"https://www.uniprot.org/uniprotkb/{primary}",
                }
            )

        for ref in entry.get("uniProtKBCrossReferences", []) or []:
            db = ref.get("database")
            if db not in {"Ensembl", "RefSeq", "PDB"}:
                continue
            ref_id = ref.get("id")
            if ref_id:
                refs.append({"db": db, "id": ref_id})
        return refs

    def _extract_key_annotations(self, entry: dict[str, Any]) -> list[str]:
        annotations: list[str] = []
        entry_type = entry.get("entryType")
        if entry_type:
            lower = entry_type.lower()
            if "reviewed" in lower:
                annotations.append("Entry status: Reviewed (Swiss-Prot)")
            elif "unreviewed" in lower:
                annotations.append("Entry status: Unreviewed (TrEMBL)")
            else:
                annotations.append(f"Entry status: {entry_type}")

        existence_raw = entry.get("proteinExistence")
        existence = None
        if isinstance(existence_raw, dict):
            existence = existence_raw.get("type") or existence_raw.get("value")
        elif isinstance(existence_raw, str):
            existence = existence_raw
        if existence:
            annotations.append(f"Protein existence: {existence}")

        score = entry.get("annotationScore")
        if isinstance(score, (int, float)):
            annotations.append(f"Annotation score: {score}/5")

        primary = entry.get("primaryAccession")
        if primary:
            annotations.append(f"UniProt accession: {primary}")

        keywords = []
        for keyword in entry.get("keywords", []) or []:
            name = (keyword or {}).get("name")
            if name:
                keywords.append(name)
            if len(keywords) >= 4:
                break
        if keywords:
            annotations.append(f"Keywords: {', '.join(keywords)}")

        if not annotations:
            length = (entry.get("sequence", {}) or {}).get("length")
            if length:
                annotations.append(f"Sequence length: {length} aa")

        return annotations

    def _truncate_summary(self, text: str) -> str:
        text = text.strip()
        if not text:
            return "Function summary not available."
        sentences = re.split(r"(?<=[.!?])\\s+", text)
        summary = " ".join(sentences[:2]).strip()
        return summary if summary else text[:400]
