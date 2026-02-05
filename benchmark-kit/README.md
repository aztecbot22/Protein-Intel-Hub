# Protein Intelligence Hub Benchmark Kit

This folder is a **separate, self-contained benchmark kit** you can publish as its own GitHub repo.
It measures API performance, coverage, ranking quality, and cache efficiency.

## What It Measures
- **Latency & throughput**: p50/p95, RPS, success rate for `/api/proteins/{query}/dossier`.
- **Coverage**: % of genes resolved, and % with non-empty module results.
- **Ranking quality**: top-K recall for gene–disease pairs using ML relevance.
- **Cache efficiency**: cold vs warm response time deltas and cache hit ratio.

## Requirements
- Python 3.9+
- The main app running locally (default: `http://localhost:8000`)

Install dependencies:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

If you're running from a global Conda env and hit a `urllib3` import error, use the venv above
or explicitly pin `urllib3<2.0`:
```bash
pip install "urllib3<2.0" --force-reinstall
```

## Configuration
Environment variables (optional):
- `PIH_API_BASE` (default: `http://localhost:8000`)
- `PIH_ORGANISM_TAXON_ID` (default: `9606`)

## 1) Latency & Throughput
### Option A: Locust (recommended)
```bash
locust -f scripts/load_test_locust.py --headless -u 50 -r 5 -t 2m --csv reports/locust
python3 scripts/summarize_locust.py --stats reports/locust_stats.csv --out reports/latency_throughput.csv
```
Outputs:
- `reports/locust_stats.csv`
- `reports/latency_throughput.csv`

### Option B: Simple runner (no Locust)
```bash
python3 scripts/load_test_simple.py \\
  --genes data/gene_list.txt \\
  --duration 120 \\
  --concurrency 20 \\
  --out reports/latency_throughput.csv \\
  --samples reports/latency_samples.csv
```

## 2) Coverage
```bash
python3 scripts/coverage.py --genes data/gene_list.txt --out reports/coverage.csv
```

## 3) Ranking Quality (Top-K Recall)
```bash
python3 scripts/ranking_eval.py \
  --pairs data/gene_disease_pairs.csv \
  --k 10 \
  --out reports/ranking_eval.csv
```

## 4) Cache Efficiency
```bash
python3 scripts/cache_eval.py --genes data/gene_list.txt --out reports/cache_eval.csv
```

## Report Summary (CSV + Charts)
```bash
python3 scripts/report.py --out reports
```
This produces:
- `reports/summary.csv`
- `reports/summary.png`
- `reports/latency_hist.png`
- `reports/coverage_modules.png`
- `reports/cache_efficiency.png`
- `reports/throughput_success.png`
- `reports/ranking_quality.png`
- `reports/linkedin_board.png`

## Notes
- Keep the gene list reasonably sized (50–200) to avoid NCBI rate limits.
- For higher throughput, configure `NCBI_API_KEY` and `NCBI_EMAIL` in the main app.
- Cache hit ratio is computed from `/api/health/metrics` (main app endpoint).
