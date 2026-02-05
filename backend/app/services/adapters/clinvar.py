from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.core.config import settings
from app.services.adapters.base import Adapter
from app.services.adapters.uniprot import resolve_uniprot_entry
from app.services.http_client import get_json, get_text


class ClinVarAdapter(Adapter):
    name = "ClinVar"

    def fetch(self, query: str, context: dict | None = None) -> dict:
        topic = (context or {}).get("topic")
        variant_page = (context or {}).get("variant_page", 1)
        variant_page_size = (context or {}).get("variant_page_size", 10)
        variant_sort = (context or {}).get("variant_sort", "significance")
        organism_taxon_id = (context or {}).get("organism_taxon_id")
        species_label = self._species_label(organism_taxon_id)
        gene = self._resolve_gene_symbol(query, context=context)
        if not gene:
            return {}

        offset = max(variant_page - 1, 0) * variant_page_size
        term = f"{gene}[gene]"
        if topic:
            term = f"({term}) AND ({topic})"

        esearch_url = f"{settings.ncbi_base_url}/esearch.fcgi"
        if variant_sort == "significance":
            retmax = max(variant_page_size * 10, 100)
            esearch = get_json(
                esearch_url,
                params={
                    "db": "clinvar",
                    "term": term,
                    "retmode": "json",
                    "retmax": retmax,
                    "retstart": 0,
                    **self._ncbi_params(),
                },
            )
        else:
            esearch = get_json(
                esearch_url,
                params={
                    "db": "clinvar",
                    "term": term,
                    "retmode": "json",
                    "retmax": variant_page_size,
                    "retstart": offset,
                    **self._ncbi_params(),
                },
            )
        if not esearch:
            return {}

        esearch_result = esearch.get("esearchresult", {}) or {}
        ids = esearch_result.get("idlist", [])
        total = int(esearch_result.get("count", 0) or 0)
        if not ids:
            return {
                "variants": [],
                "variants_overview": {"total": total, "condition_counts": []},
                "provenance": {"variants": "ClinVar (live, no hits)"},
            }

        esummary_url = f"{settings.ncbi_base_url}/esummary.fcgi"
        summary = get_json(
            esummary_url,
            params={
                "db": "clinvar",
                "id": ",".join(ids),
                "retmode": "json",
                **self._ncbi_params(),
            },
        )
        if not summary:
            return {}

        result = summary.get("result", {}) or {}
        uids = result.get("uids", []) or []
        variants: list[dict] = []
        for uid in uids:
            item = result.get(uid, {}) or {}
            variants.append(self._map_variant(uid, item, species_label))

        variants_for_summary = list(variants)

        if variant_sort == "significance":
            variants.sort(key=self._score_variant, reverse=True)
            start = offset
            end = offset + variant_page_size
            variants = variants[start:end]

        self._attach_pubmed_links(variants)
        condition_counts = self._summarize_conditions(variants_for_summary)

        return {
            "variants": variants,
            "variants_overview": {"total": total, "condition_counts": condition_counts},
            "provenance": {"variants": "ClinVar (live)"},
        }

    def _resolve_gene_symbol(self, query: str, context: dict | None = None) -> str | None:
        organism_taxon_id = (context or {}).get("organism_taxon_id")
        entry = resolve_uniprot_entry(query, organism_taxon_id=organism_taxon_id)
        if not entry:
            return query.upper()
        genes = entry.get("genes", []) or []
        if genes:
            gene_name = (genes[0].get("geneName") or {}).get("value")
            if gene_name:
                return gene_name
        return (entry.get("uniProtkbId") or query).split("_")[0]

    def _map_variant(self, uid: str, item: dict, species_label: str | None) -> dict:
        classification = None
        review_status = None
        if item.get("germline_classification"):
            germ = item.get("germline_classification") or {}
            classification = germ.get("description")
            review_status = germ.get("review_status")
        if not classification and item.get("clinical_impact_classification"):
            clinical = item.get("clinical_impact_classification") or {}
            classification = clinical.get("description")
            review_status = review_status or clinical.get("review_status")
        if not classification:
            classification = item.get("clinical_significance") or item.get("clinical_significance_list")

        traits = []
        trait_set = item.get("trait_set")
        if isinstance(trait_set, dict):
            trait_set = [trait_set]
        if isinstance(trait_set, list):
            for trait in trait_set:
                if isinstance(trait, dict):
                    name = trait.get("trait_name") or trait.get("traitname") or trait.get("trait")
                    if isinstance(name, list):
                        traits.extend([value for value in name if isinstance(value, str)])
                    elif isinstance(name, str):
                        traits.append(name)
        if not traits and item.get("phenotype_list"):
            traits = [value.strip() for value in str(item.get("phenotype_list")).split(";") if value.strip()]

        hgvs = item.get("title")
        variation_set = item.get("variation_set", []) or []
        if not hgvs and variation_set:
            hgvs = variation_set[0].get("variation_name")

        conflicts = []
        if review_status and re.search(r"conflict", review_status, re.IGNORECASE):
            conflicts.append("conflicting interpretations")

        protein_change, aa_position = self._extract_protein_change(hgvs or "")
        condition = "; ".join(traits) if traits else "Not specified"

        return {
            "clinvar_uid": uid,
            "variant_id": item.get("accession") or uid,
            "hgvs": hgvs,
            "protein_change": protein_change,
            "aa_position": aa_position,
            "classification": classification,
            "condition": condition,
            "species": species_label,
            "review_status": review_status,
            "conflicts": conflicts,
            "pmids": [],
        }

    def _attach_pubmed_links(self, variants: list[dict]) -> None:
        for variant in variants[:5]:
            uid = variant.get("clinvar_uid") or variant.get("variant_id")
            if not uid:
                continue
            pmids = self._fetch_pubmed_links(uid)
            if pmids:
                variant["pmids"] = pmids

    def _fetch_pubmed_links(self, clinvar_id: str) -> list[str]:
        elink_url = f"{settings.ncbi_base_url}/elink.fcgi"
        xml_text = get_text(
            elink_url,
            params={
                "dbfrom": "clinvar",
                "db": "pubmed",
                "id": clinvar_id,
                **self._ncbi_params(),
            },
            headers={"accept": "application/xml"},
        )
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        pmids = []
        for linksetdb in root.findall(".//LinkSetDb"):
            for link in linksetdb.findall("Link/Id"):
                if link.text:
                    pmids.append(link.text.strip())
        return pmids

    def _summarize_conditions(self, variants: list[dict]) -> list[dict]:
        counts: dict[str, int] = {}
        for variant in variants:
            condition = variant.get("condition")
            if not condition:
                continue
            if condition.lower() == "not specified":
                continue
            for entry in [value.strip() for value in condition.split(";") if value.strip()]:
                counts[entry] = counts.get(entry, 0) + 1
        summary = [{"condition": key, "count": value} for key, value in counts.items()]
        summary.sort(key=lambda item: item["count"], reverse=True)
        return summary

    def _extract_protein_change(self, hgvs: str) -> tuple[str | None, int | None]:
        match = re.search(r"p\.([A-Za-z]{3})(\d+)([A-Za-z]{3})", hgvs)
        if not match:
            return None, None
        return f"{match.group(1)}{match.group(2)}{match.group(3)}", int(match.group(2))

    def _species_label(self, taxon_id: int | None) -> str | None:
        if not taxon_id:
            return None
        mapping = {
            9606: "Human",
            10090: "Mouse",
            10116: "Rat",
            7955: "Zebrafish",
            7227: "Fly",
            559292: "Yeast",
            3702: "Arabidopsis",
            83333: "E. coli",
        }
        return mapping.get(taxon_id, f"Taxon {taxon_id}")

    def _score_variant(self, variant: dict) -> int:
        classification = (variant.get("classification") or "").lower()
        review_status = (variant.get("review_status") or "").lower()

        classification_scores = {
            "pathogenic": 5,
            "likely pathogenic": 4,
            "uncertain significance": 2,
            "vus": 2,
            "likely benign": 1,
            "benign": 0,
        }
        review_scores = {
            "practice guideline": 4,
            "reviewed by expert panel": 3,
            "criteria provided, multiple submitters, no conflicts": 2,
            "criteria provided, single submitter": 1,
        }

        score = 0
        for label, value in classification_scores.items():
            if label in classification:
                score += value
                break
        for label, value in review_scores.items():
            if label in review_status:
                score += value
                break
        return score

    def _ncbi_params(self) -> dict:
        params: dict[str, str] = {"tool": settings.ncbi_tool}
        if settings.ncbi_email:
            params["email"] = settings.ncbi_email
        if settings.ncbi_api_key:
            params["api_key"] = settings.ncbi_api_key
        return params
