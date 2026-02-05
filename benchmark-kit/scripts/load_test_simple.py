import argparse
import csv
import os
import random
import threading
import time
import requests

API_BASE = os.getenv("PIH_API_BASE", "http://localhost:8000")
DEFAULT_TAXON = int(os.getenv("PIH_ORGANISM_TAXON_ID", "9606"))


def percentile(sorted_values, pct):
    if not sorted_values:
        return 0.0
    k = int(round((pct / 100.0) * (len(sorted_values) - 1)))
    k = max(0, min(k, len(sorted_values) - 1))
    return sorted_values[k]


def worker(stop_event, genes, taxon_id, results, lock):
    while not stop_event.is_set():
        gene = random.choice(genes)
        url = f"{API_BASE}/api/proteins/{gene}/dossier"
        params = {"organism_taxon_id": taxon_id, "variant_page": 1, "variant_page_size": 10}
        t0 = time.time()
        success = False
        try:
            resp = requests.get(url, params=params, timeout=30)
            success = resp.status_code == 200
        except requests.RequestException:
            success = False
        latency = time.time() - t0
        with lock:
            results.append((latency, success))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--genes", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--samples", default="")
    parser.add_argument("--taxon", type=int, default=DEFAULT_TAXON)
    args = parser.parse_args()

    with open(args.genes) as f:
        genes = [line.strip() for line in f if line.strip()]

    results = []
    lock = threading.Lock()
    stop_event = threading.Event()

    threads = []
    for _ in range(args.concurrency):
        thread = threading.Thread(target=worker, args=(stop_event, genes, args.taxon, results, lock))
        thread.daemon = True
        thread.start()
        threads.append(thread)

    start = time.time()
    time.sleep(args.duration)
    stop_event.set()

    for thread in threads:
        thread.join(timeout=1)

    duration = time.time() - start
    latencies = [lat for lat, _ in results]
    latencies_sorted = sorted(latencies)
    total = len(results)
    failures = sum(1 for _, success in results if not success)
    success_rate = ((total - failures) / total * 100) if total else 0
    rps = total / duration if duration else 0

    p50 = percentile(latencies_sorted, 50) * 1000
    p95 = percentile(latencies_sorted, 95) * 1000

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if args.samples:
        os.makedirs(os.path.dirname(args.samples), exist_ok=True)
    with open(args.out, "w", newline="") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=[
                "duration_s",
                "total_requests",
                "failure_count",
                "success_rate_pct",
                "rps",
                "p50_ms",
                "p95_ms",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "duration_s": round(duration, 2),
                "total_requests": total,
                "failure_count": failures,
                "success_rate_pct": round(success_rate, 2),
                "rps": round(rps, 2),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
            }
        )

    if args.samples:
        with open(args.samples, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["latency_s", "success"])
            writer.writeheader()
            for latency, success in results:
                writer.writerow({"latency_s": round(latency, 4), "success": int(success)})

    print("Load test summary")
    print("Duration (s):", round(duration, 2))
    print("Total requests:", total)
    print("Success rate %:", round(success_rate, 2))
    print("RPS:", round(rps, 2))
    print("p50 ms:", round(p50, 2))
    print("p95 ms:", round(p95, 2))


if __name__ == "__main__":
    main()
