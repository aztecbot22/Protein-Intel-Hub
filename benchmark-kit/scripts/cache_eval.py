import argparse
import os
import time
import requests
import csv

API_BASE = os.getenv("PIH_API_BASE", "http://localhost:8000")
DEFAULT_TAXON = int(os.getenv("PIH_ORGANISM_TAXON_ID", "9606"))


def fetch_once(gene: str, taxon_id: int):
    url = f"{API_BASE}/api/proteins/{gene}/dossier"
    params = {"organism_taxon_id": taxon_id, "variant_page": 1, "variant_page_size": 10}
    t0 = time.time()
    resp = requests.get(url, params=params, timeout=30)
    latency = time.time() - t0
    return resp.status_code, latency


def fetch_cache_metrics():
    url = f"{API_BASE}/api/health/metrics"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("cache")
    except requests.RequestException:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--genes", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--taxon", type=int, default=DEFAULT_TAXON)
    args = parser.parse_args()

    with open(args.genes) as f:
        genes = [line.strip() for line in f if line.strip()]

    start_metrics = fetch_cache_metrics()

    cold_latencies = []
    warm_latencies = []

    for gene in genes:
        status, latency = fetch_once(gene, args.taxon)
        if status == 200:
            cold_latencies.append(latency)

    for gene in genes:
        status, latency = fetch_once(gene, args.taxon)
        if status == 200:
            warm_latencies.append(latency)

    end_metrics = fetch_cache_metrics()

    avg_cold = sum(cold_latencies) / len(cold_latencies) if cold_latencies else 0
    avg_warm = sum(warm_latencies) / len(warm_latencies) if warm_latencies else 0
    improvement = ((avg_cold - avg_warm) / avg_cold) * 100 if avg_cold else 0

    cache_hit_ratio = None
    cache_hits = None
    cache_misses = None
    if start_metrics and end_metrics:
        hits = end_metrics.get("hits", 0) - start_metrics.get("hits", 0)
        misses = end_metrics.get("misses", 0) - start_metrics.get("misses", 0)
        total = hits + misses
        if total > 0:
            cache_hit_ratio = round(hits / total, 4)
        cache_hits = hits
        cache_misses = misses

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=[
                "avg_cold",
                "avg_warm",
                "improvement_pct",
                "cache_hit_ratio",
                "cache_hits",
                "cache_misses",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "avg_cold": round(avg_cold, 3),
                "avg_warm": round(avg_warm, 3),
                "improvement_pct": round(improvement, 2),
                "cache_hit_ratio": cache_hit_ratio,
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
            }
        )

    print("Avg cold:", round(avg_cold, 3))
    print("Avg warm:", round(avg_warm, 3))
    print("Improvement %:", round(improvement, 2))
    if cache_hit_ratio is not None:
        print("Cache hit ratio:", cache_hit_ratio)


if __name__ == "__main__":
    main()
