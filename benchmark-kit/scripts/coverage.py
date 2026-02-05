import argparse
import os
import time
import requests
import csv

API_BASE = os.getenv("PIH_API_BASE", "http://localhost:8000")
DEFAULT_TAXON = int(os.getenv("PIH_ORGANISM_TAXON_ID", "9606"))


def fetch_dossier(gene: str, taxon_id: int):
    url = f"{API_BASE}/api/proteins/{gene}/dossier"
    params = {"organism_taxon_id": taxon_id, "variant_page": 1, "variant_page_size": 10}
    t0 = time.time()
    resp = requests.get(url, params=params, timeout=30)
    latency = time.time() - t0
    if resp.status_code != 200:
        return None, latency
    return resp.json(), latency


def module_has_data(dossier: dict, key: str) -> bool:
    if key == "variants":
        return bool(dossier.get("variants"))
    if key == "pathways":
        return bool(dossier.get("pathways"))
    if key == "literature":
        return bool(dossier.get("literature"))
    if key == "structure":
        structure = dossier.get("structure", {})
        return bool(structure.get("pdb_ids")) or bool(structure.get("alphafold_files"))
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--genes", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--taxon", type=int, default=DEFAULT_TAXON)
    args = parser.parse_args()

    with open(args.genes) as f:
        genes = [line.strip() for line in f if line.strip()]

    results = []
    resolved = 0
    modules = {"variants": 0, "pathways": 0, "literature": 0, "structure": 0}
    latencies = []

    for gene in genes:
        dossier, latency = fetch_dossier(gene, args.taxon)
        latencies.append(latency)
        if dossier is None:
            results.append({"gene": gene, "resolved": 0, **{k: 0 for k in modules}})
            continue
        resolved += 1
        row = {"gene": gene, "resolved": 1}
        for key in modules:
            has_data = module_has_data(dossier, key)
            row[key] = 1 if has_data else 0
            if has_data:
                modules[key] += 1
        results.append(row)

    total = len(genes)
    summary = {
        "total_genes": total,
        "resolved_pct": round((resolved / total) * 100, 2) if total else 0,
        "p50_latency": round(sorted(latencies)[len(latencies) // 2], 3) if latencies else 0,
        "p95_latency": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 3) if latencies else 0,
        "variants_pct": round((modules["variants"] / total) * 100, 2) if total else 0,
        "pathways_pct": round((modules["pathways"] / total) * 100, 2) if total else 0,
        "literature_pct": round((modules["literature"] / total) * 100, 2) if total else 0,
        "structure_pct": round((modules["structure"] / total) * 100, 2) if total else 0,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print("Summary")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
