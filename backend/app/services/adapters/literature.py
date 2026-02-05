from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from app.core.config import settings
from app.services.adapters.base import Adapter
from app.services.adapters.uniprot import resolve_uniprot_entry
from app.services.http_client import get_json, get_text


class LiteratureAdapter(Adapter):
    name = "PubMed"

    def fetch(self, query: str, context: dict | None = None) -> dict:
        entry = resolve_uniprot_entry(query, organism_taxon_id=(context or {}).get("organism_taxon_id"))
        gene = self._resolve_gene_symbol(entry, query)
        if not gene:
            return {}

        topic = (context or {}).get("topic")
        literature_page = (context or {}).get("literature_page", 1)
        literature_page_size = (context or {}).get("literature_page_size", 10)
        literature_year_from = (context or {}).get("literature_year_from")
        literature_year_to = (context or {}).get("literature_year_to")
        literature_sort = (context or {}).get("literature_sort", "date")

        organism_name = (entry.get("organism", {}) or {}).get("scientificName") if entry else None
        term = self._build_query(gene, topic=topic, organism=organism_name)
        offset = max(literature_page - 1, 0) * literature_page_size

        esearch_url = f"{settings.ncbi_base_url}/esearch.fcgi"
        if literature_sort in {"citation", "ml"}:
            retmax = max(literature_page_size * 10, 100)
            esearch = get_json(
                esearch_url,
                params={
                    "db": "pubmed",
                    "term": term,
                    "retmode": "json",
                    "retmax": retmax,
                    "retstart": 0,
                    "sort": "relevance" if literature_sort == "ml" else "relevance",
                    "datetype": "pdat" if literature_year_from or literature_year_to else None,
                    "mindate": literature_year_from,
                    "maxdate": literature_year_to,
                    **self._ncbi_params(),
                },
            )
        else:
            esearch = get_json(
                esearch_url,
                params={
                    "db": "pubmed",
                    "term": term,
                    "retmode": "json",
                    "retmax": literature_page_size,
                    "retstart": offset,
                    "sort": "pub+date" if literature_sort == "date" else "relevance",
                    "datetype": "pdat" if literature_year_from or literature_year_to else None,
                    "mindate": literature_year_from,
                    "maxdate": literature_year_to,
                    **self._ncbi_params(),
                },
            )
        if not esearch:
            return {}

        esearch_result = esearch.get("esearchresult", {}) or {}
        ids = esearch_result.get("idlist", [])
        total = int(esearch_result.get("count", 0) or 0)
        if not ids:
            suggestions = self._suggest_study_topics(gene, organism_name)
            return {
                "literature": [],
                "literature_overview": {"total": total},
                "study_suggestions": suggestions,
                "provenance": {"literature": "PubMed (live, no hits)"},
            }

        esummary_url = f"{settings.ncbi_base_url}/esummary.fcgi"
        summary = get_json(
            esummary_url,
            params={
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "json",
                **self._ncbi_params(),
            },
        )
        if not summary:
            return {}

        result = summary.get("result", {}) or {}
        uids = result.get("uids", []) or []
        items = []
        for uid in uids:
            item = result.get(uid, {}) or {}
            items.append(self._map_paper(uid, item))

        citation_map = self._fetch_citation_counts([item["pmid"] for item in items])
        for item in items:
            item["citation_count"] = citation_map.get(item["pmid"])

        abstracts = self._fetch_abstracts([item["pmid"] for item in items])
        self._assign_topics(items, abstracts)
        if literature_sort == "ml":
            self._apply_ml_ranking(items, gene, topic, organism_name, abstracts)
            start = offset
            end = offset + literature_page_size
            items = items[start:end]

        if literature_sort == "citation":
            items.sort(key=lambda item: item.get("citation_count") or 0, reverse=True)
            start = offset
            end = offset + literature_page_size
            items = items[start:end]

        suggestions = self._suggest_study_topics(gene, organism_name)

        return {
            "literature": items,
            "literature_overview": {"total": total},
            "study_suggestions": suggestions,
            "provenance": {"literature": "PubMed (live)"},
        }

    def _build_query(self, gene: str, topic: str | None = None, organism: str | None = None) -> str:
        keywords = ["mutation", "inhibitor", "knockout", "biomarker"]
        keyword_query = " OR ".join(keywords)
        base = f"({gene}[Title/Abstract])"
        if organism:
            base = f"{base} AND ({organism}[MeSH Terms] OR {organism}[Title/Abstract])"
        if topic:
            return f"{base} AND ({topic})"
        return f"{base} AND ({keyword_query})"

    def _suggest_study_topics(self, gene: str, organism: str | None) -> list[str]:
        if not gene:
            return []
        term = f"({gene}[Title/Abstract])"
        if organism:
            term = f"{term} AND ({organism}[MeSH Terms] OR {organism}[Title/Abstract])"

        esearch_url = f"{settings.ncbi_base_url}/esearch.fcgi"
        esearch = get_json(
            esearch_url,
            params={
                "db": "pubmed",
                "term": term,
                "retmode": "json",
                "retmax": 30,
                "sort": "relevance",
                **self._ncbi_params(),
            },
        )
        if not esearch:
            return []
        ids = (esearch.get("esearchresult", {}) or {}).get("idlist", [])
        if not ids:
            return []

        mesh_terms = self._fetch_mesh_terms(ids)
        counts: dict[str, int] = {}
        for term in mesh_terms:
            if self._is_generic_term(term):
                continue
            counts[term] = counts.get(term, 0) + 1

        suggestions = sorted(counts, key=lambda key: counts[key], reverse=True)
        return suggestions[:8]

    def _fetch_citation_counts(self, pmids: list[str]) -> dict[str, int]:
        if not pmids:
            return {}
        url = f"{settings.europe_pmc_base_url}/search"
        data = self._query_europe_pmc(pmids, mode="EXT_ID")
        if not data:
            data = self._query_europe_pmc(pmids, mode="PMID")
        if not data:
            return {}
        results = (data.get("resultList") or {}).get("result", []) or []
        citations = {}
        for item in results:
            pmid = item.get("pmid")
            count = item.get("citationCount") or item.get("citedByCount") or item.get("citedByCount", None)
            if not pmid or count is None:
                continue
            try:
                citations[pmid] = int(count)
            except (TypeError, ValueError):
                continue
        return citations

    def _query_europe_pmc(self, pmids: list[str], mode: str = "EXT_ID") -> dict | None:
        query = " OR ".join([f"{mode}:{pmid}" for pmid in pmids])
        url = f"{settings.europe_pmc_base_url}/search"
        return get_json(
            url,
            params={
                "query": query,
                "format": "json",
                "pageSize": len(pmids),
                "resultType": "core",
            },
        )

    def _fetch_mesh_terms(self, pmids: list[str]) -> list[str]:
        efetch_url = f"{settings.ncbi_base_url}/efetch.fcgi"
        xml_text = get_text(
            efetch_url,
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
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
        terms = []
        for node in root.findall(".//MeshHeading/DescriptorName"):
            if node.text:
                terms.append(node.text.strip())
        for node in root.findall(".//KeywordList/Keyword"):
            if node.text:
                terms.append(node.text.strip())
        return terms

    def _fetch_abstracts(self, pmids: list[str]) -> dict[str, str]:
        if not pmids:
            return {}
        efetch_url = f"{settings.ncbi_base_url}/efetch.fcgi"
        xml_text = get_text(
            efetch_url,
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                **self._ncbi_params(),
            },
            headers={"accept": "application/xml"},
        )
        if not xml_text:
            return {}
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return {}
        abstracts: dict[str, str] = {}
        for article in root.findall(".//PubmedArticle"):
            pmid_node = article.find(".//MedlineCitation/PMID")
            if pmid_node is None or not pmid_node.text:
                continue
            pmid = pmid_node.text.strip()
            parts = []
            for node in article.findall(".//Abstract/AbstractText"):
                if node.text:
                    parts.append(node.text.strip())
            if parts:
                abstracts[pmid] = " ".join(parts)
        return abstracts

    def _is_generic_term(self, term: str) -> bool:
        generic = {
            "Humans",
            "Animals",
            "Male",
            "Female",
            "Adult",
            "Mice",
            "Rats",
            "Cells",
            "Cell Line",
            "HeLa Cells",
            "Molecular Sequence Data",
            "Gene Expression Regulation",
            "Mutation",
        }
        return term in generic or len(term) < 4

    def _map_paper(self, pmid: str, item: dict) -> dict:
        title = item.get("title") or "Untitled"
        journal = item.get("fulljournalname") or item.get("source")
        year = self._extract_year(item.get("pubdate"))
        tags = self._tag_from_title(title)
        return {
            "pmid": pmid,
            "title": title,
            "journal": journal,
            "year": year,
            "tags": tags,
            "ml_score": None,
            "disease_score": None,
            "l2r_score": None,
            "topic_label": None,
        }

    def _extract_year(self, pubdate: str | None) -> int | None:
        if not pubdate:
            return None
        match = re.search(r"(19|20)\d{2}", pubdate)
        return int(match.group(0)) if match else None

    def _tag_from_title(self, title: str) -> list[str]:
        tags = []
        lower = title.lower()
        for tag in ["mutation", "inhibitor", "knockout", "biomarker", "variant", "pathway"]:
            if tag in lower:
                tags.append(tag)
        return tags

    def _resolve_gene_symbol(self, entry: dict | None, fallback: str) -> str:
        if not entry:
            return fallback
        genes = entry.get("genes", []) or []
        if genes:
            gene_name = (genes[0].get("geneName") or {}).get("value")
            if gene_name:
                return gene_name
        return fallback

    def _apply_ml_ranking(
        self,
        items: list[dict],
        gene: str,
        topic: str | None,
        organism: str | None,
        abstracts: dict[str, str],
    ) -> None:
        if not items:
            return
        query_parts = [gene]
        if topic:
            query_parts.append(topic)
        if organism:
            query_parts.append(organism)
        query_text = " ".join(query_parts)

        docs = []
        for item in items:
            abstract = abstracts.get(item["pmid"], "")
            tags = " ".join(item.get("tags") or [])
            docs.append(" ".join([item.get("title", ""), abstract, tags]))

        scores = self._tfidf_scores(docs, query_text)
        disease_scores = self._tfidf_scores(docs, topic) if topic else [0.0 for _ in docs]
        citation_scores = self._normalize_scores(
            [math.log1p(item.get("citation_count") or 0) for item in items]
        )
        recency_scores = self._normalize_scores(
            [self._recency_value(item.get("year")) for item in items]
        )

        l2r_scores = []
        for idx, score in enumerate(scores):
            l2r = (
                0.5 * score
                + 0.2 * disease_scores[idx]
                + 0.2 * citation_scores[idx]
                + 0.1 * recency_scores[idx]
            )
            l2r_scores.append(l2r)

        for item, score in zip(items, scores):
            item["ml_score"] = round(score, 4)
        for item, score in zip(items, disease_scores):
            item["disease_score"] = round(score, 4)
        for item, score in zip(items, l2r_scores):
            item["l2r_score"] = round(score, 4)
        items.sort(key=lambda item: item.get("l2r_score") or 0, reverse=True)

    def _tfidf_scores(self, docs: list[str], query: str) -> list[float]:
        tokenized_docs = [self._tokenize(doc) for doc in docs]
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return [0.0 for _ in docs]

        df: dict[str, int] = {}
        for tokens in tokenized_docs:
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1

        idf: dict[str, float] = {}
        n_docs = max(len(tokenized_docs), 1)
        for token, count in df.items():
            idf[token] = math.log((1 + n_docs) / (1 + count)) + 1

        query_vec = self._tfidf_vector(query_tokens, idf)
        query_norm = self._vector_norm(query_vec)
        if query_norm == 0:
            return [0.0 for _ in docs]

        scores = []
        for tokens in tokenized_docs:
            doc_vec = self._tfidf_vector(tokens, idf)
            doc_norm = self._vector_norm(doc_vec)
            if doc_norm == 0:
                scores.append(0.0)
                continue
            dot = 0.0
            for token, value in doc_vec.items():
                dot += value * query_vec.get(token, 0.0)
            scores.append(dot / (doc_norm * query_norm))
        return scores

    def _assign_topics(self, items: list[dict], abstracts: dict[str, str]) -> None:
        if not items:
            return
        docs = []
        for item in items:
            abstract = abstracts.get(item["pmid"], "")
            tags = " ".join(item.get("tags") or [])
            docs.append(" ".join([item.get("title", ""), abstract, tags]))

        tokenized_docs = [self._tokenize(doc) for doc in docs]
        vocab = self._build_vocab(tokenized_docs, max_terms=120)
        if not vocab:
            return

        idf = self._idf_from_vocab(tokenized_docs, vocab)
        vectors = [self._tfidf_vector_dense(tokens, vocab, idf) for tokens in tokenized_docs]
        k = min(4, len(vectors))
        assignments, centroids = self._kmeans(vectors, k)
        topic_terms = self._topic_terms(centroids, vocab, top_n=5)

        for item, cluster_id in zip(items, assignments):
            label = topic_terms.get(cluster_id)
            if label:
                item["topic_label"] = label

    def _build_vocab(self, tokenized_docs: list[list[str]], max_terms: int = 120) -> list[str]:
        counts: dict[str, int] = {}
        for tokens in tokenized_docs:
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
        sorted_terms = sorted(counts, key=lambda t: counts[t], reverse=True)
        return sorted_terms[:max_terms]

    def _idf_from_vocab(self, tokenized_docs: list[list[str]], vocab: list[str]) -> dict[str, float]:
        df: dict[str, int] = {term: 0 for term in vocab}
        for tokens in tokenized_docs:
            token_set = set(tokens)
            for term in vocab:
                if term in token_set:
                    df[term] += 1
        idf = {}
        n_docs = max(len(tokenized_docs), 1)
        for term in vocab:
            idf[term] = math.log((1 + n_docs) / (1 + df[term])) + 1
        return idf

    def _tfidf_vector_dense(self, tokens: list[str], vocab: list[str], idf: dict[str, float]) -> list[float]:
        tf: dict[str, int] = {}
        for token in tokens:
            if token in idf:
                tf[token] = tf.get(token, 0) + 1
        total = max(len(tokens), 1)
        vector = []
        for term in vocab:
            value = (tf.get(term, 0) / total) * idf[term]
            vector.append(value)
        return vector

    def _kmeans(self, vectors: list[list[float]], k: int, iterations: int = 8) -> tuple[list[int], list[list[float]]]:
        centroids = [vectors[i][:] for i in range(k)]
        assignments = [0 for _ in vectors]
        for _ in range(iterations):
            for i, vector in enumerate(vectors):
                best = 0
                best_score = -1.0
                for idx, centroid in enumerate(centroids):
                    score = self._cosine_similarity(vector, centroid)
                    if score > best_score:
                        best_score = score
                        best = idx
                assignments[i] = best
            centroids = self._recompute_centroids(vectors, assignments, k, len(vectors[0]))
        return assignments, centroids

    def _recompute_centroids(
        self, vectors: list[list[float]], assignments: list[int], k: int, size: int
    ) -> list[list[float]]:
        centroids = [[0.0 for _ in range(size)] for _ in range(k)]
        counts = [0 for _ in range(k)]
        for vec, cluster in zip(vectors, assignments):
            counts[cluster] += 1
            for idx, value in enumerate(vec):
                centroids[cluster][idx] += value
        for cluster in range(k):
            if counts[cluster] == 0:
                continue
            centroids[cluster] = [value / counts[cluster] for value in centroids[cluster]]
        return centroids

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _topic_terms(self, centroids: list[list[float]], vocab: list[str], top_n: int = 5) -> dict[int, str]:
        topics = {}
        for idx, centroid in enumerate(centroids):
            term_scores = list(enumerate(centroid))
            term_scores.sort(key=lambda item: item[1], reverse=True)
            top_terms = [vocab[i] for i, _ in term_scores[:top_n]]
            topics[idx] = " / ".join(top_terms)
        return topics

    def _recency_value(self, year: int | None) -> float:
        if not year:
            return 0.0
        now = datetime.utcnow().year
        return max(0.0, year - (now - 20))

    def _normalize_scores(self, values: list[float]) -> list[float]:
        if not values:
            return []
        min_v = min(values)
        max_v = max(values)
        if max_v == min_v:
            return [0.0 for _ in values]
        return [(value - min_v) / (max_v - min_v) for value in values]

    def _tfidf_vector(self, tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        total = max(len(tokens), 1)
        vec: dict[str, float] = {}
        for token, count in tf.items():
            if token not in idf:
                continue
            vec[token] = (count / total) * idf[token]
        return vec

    def _vector_norm(self, vec: dict[str, float]) -> float:
        return math.sqrt(sum(value * value for value in vec.values()))

    def _tokenize(self, text: str) -> list[str]:
        if not text:
            return []
        tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
        return [token for token in tokens if len(token) > 2]

    def _ncbi_params(self) -> dict:
        params: dict[str, str] = {"tool": settings.ncbi_tool}
        if settings.ncbi_email:
            params["email"] = settings.ncbi_email
        if settings.ncbi_api_key:
            params["api_key"] = settings.ncbi_api_key
        return params
