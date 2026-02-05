import argparse
import csv
import os


def read_locust_stats(path: str) -> dict:
    with open(path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)
    if not rows:
        return {}
    row = next((r for r in rows if r.get("Name") == "Aggregated"), rows[0])
    def get_value(key, fallback_keys=None):
        if key in row and row[key] != "":
            return float(row[key])
        if fallback_keys:
            for fk in fallback_keys:
                if fk in row and row[fk] != "":
                    return float(row[fk])
        return None

    request_count = get_value("Request Count") or 0
    failure_count = get_value("Failure Count") or 0
    rps = get_value("Requests/s") or 0
    p50 = get_value("Median Response Time", ["50%", "50%ile", "Median"])
    p95 = get_value("95%", ["95%ile", "95th", "95th Percentile"])

    success_rate = 0.0
    if request_count:
        success_rate = max(0.0, (request_count - failure_count) / request_count * 100)

    return {
        "request_count": int(request_count),
        "failure_count": int(failure_count),
        "success_rate_pct": round(success_rate, 2),
        "rps": round(rps, 3),
        "p50_ms": round(p50, 2) if p50 is not None else None,
        "p95_ms": round(p95, 2) if p95 is not None else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    summary = read_locust_stats(args.stats)
    if not summary:
        raise SystemExit("No locust stats rows found.")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print("Latency/Throughput summary:")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
