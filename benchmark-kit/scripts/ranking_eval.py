import argparse
import csv
import os
import requests

API_BASE = os.getenv("PIH_API_BASE", "http://localhost:8000")
DEFAULT_TAXON = int(os.getenv("PIH_ORGANISM_TAXON_ID", "9606"))


def fetch_literature(gene: str, disease: str, taxon_id: int):
    url = f"{API_BASE}/api/proteins/{gene}/dossier"
    params = {
        "organism_taxon_id": taxon_id,
        "topic": disease,
        "literature_sort": "ml",
        "literature_page": 1,
        "literature_page_size": 10,
    }
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data.get("literature", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--out", required=True)
    parser.add_argument("--taxon", type=int, default=DEFAULT_TAXON)
    args = parser.parse_args()

    rows = []
    with open(args.pairs, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rows.append(row)

    results = []
    hits = 0
    for row in rows:
        gene = row["gene"]
        disease = row["disease"]
        taxon = int(row.get("organism_taxon_id") or args.taxon)
        literature = fetch_literature(gene, disease, taxon)
        topk = literature[: args.k]
        match = 0
        for paper in topk:
            title = (paper.get("title") or "").lower()
            tags = " ".join(paper.get("tags") or []).lower()
            if disease.lower() in title or disease.lower() in tags:
                match = 1
                break
        hits += match
        results.append({"gene": gene, "disease": disease, "hit": match})

    recall = hits / len(rows) if rows else 0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["gene", "disease", "hit"])
        writer.writeheader()
        writer.writerows(results)

    print("Top-K recall:", round(recall, 3))


if __name__ == "__main__":
    main()
