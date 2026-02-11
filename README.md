# Protein Intelligence Hub

Protein Intelligence Hub is a full‑stack web app that assembles a single, structured protein dossier from multiple live biomedical databases. It merges canonical protein context, clinical variants, pathways/interactions, ML‑ranked literature, and an interactive AlphaFold 3D structure viewer into one evidence‑first workspace.

## Live Demo
Web app: `https://main.d3z2b962y6301.amplifyapp.com`

Note: The backend currently uses a Cloudflare quick tunnel. If the tunnel URL changes, the demo may be temporarily unavailable until it is updated.

## Features (Core)
- Live multi‑database dossier: UniProt, ClinVar, PubMed, Reactome, STRING, PDB, AlphaFold.
- ML‑ranked literature (TF‑IDF + learning‑to‑rank signals) with topic labels.
- Interactive AlphaFold 3D viewer with clickable residue details and binding‑site spheres.
- Variants table with clinical significance and evidence provenance.
- Organism‑aware search and study‑focus filters.
- Benchmark kit for latency, coverage, ranking quality, and cache efficiency.

## Suggested GitHub Topics (SEO)
`bioinformatics` `computational-biology` `proteomics` `uniprot` `clinvar` `pubmed` `alphafold` `fastapi` `react` `machine-learning`

## MVP Modules
- Protein Overview with canonical info, isoforms, domains, subcellular location, and a one-paragraph summary.
- Variants and Clinical Significance with exportable tables.
- Structure and Druggability with PDB + AlphaFold, a 3D viewer, domain maps, and heuristic flags.
- Pathways and Interactions with a filtered interaction view.
- Literature and Evidence feed.

## Recent Enhancements
- Organism dropdown (taxon-aware UniProt search).
- Suggested study focus dropdown driven by live evidence.
- 3D AlphaFold viewer with clickable residue details and binding-site spheres.
- ClinVar condition wheel + significance sorting.
- Backend parallel fetch + in-memory cache for faster responses.
- ML-powered literature relevance (TF-IDF similarity on title/abstract + learning-to-rank signals).
- Topic modeling labels for literature (lightweight clustering on TF-IDF).
- Disease relevance scoring for literature (topic-to-abstract similarity).

## Stack
- Backend: FastAPI + SQLAlchemy.
- Frontend: React + TypeScript + Vite.
- Database: SQLite by default, Postgres for multi-user.

## Quick Start (Local)
1. Backend.
   - `python3 -m venv .venv && source .venv/bin/activate`
   - `pip install -r backend/requirements.txt`
   - `python3 backend/scripts/init_db.py`
   - `uvicorn app.main:app --app-dir backend --reload`
2. Frontend.
   - `cd frontend`
   - `npm install`
   - `npm run dev`
3. Open `http://localhost:5173`.

## Quick Start (Docker)
1. `docker compose up --build`
2. Open `http://localhost:5173`.

## Environment Variables
Copy `.env.example` to `.env` and update as needed.
- `DATABASE_URL` defaults to SQLite for local development.
- `SECRET_KEY` should be rotated before deployment.
- `NCBI_API_KEY` / `NCBI_EMAIL` are optional but recommended for higher E-utilities limits.
- `VITE_ENABLE_DEMO_FALLBACK` controls demo fallback when the API is offline.

## API Endpoints
- `GET /api/health`
- `GET /api/health/metrics`
- `GET /api/proteins/{query}/dossier`
- `GET /api/export/variants?query=TP53`

## Data Sources & Attribution
This project integrates live data from the following sources. Please follow their citation and usage guidelines:
- UniProt
- ClinVar (NCBI)
- PubMed (NCBI)
- Reactome
- STRING
- Protein Data Bank (PDB)
- AlphaFold DB
- Europe PMC (citations)

## License
MIT License. Copyright (c) 2026 Priyansh Pathak.

## Citation
If you use this software in a publication or demo, please cite it and the underlying data sources.

**BibTeX (software):**
```
@software{protein_intelligence_hub_2026,
  author = {Priyansh Pathak},
  title = {Protein Intelligence Hub},
  year = {2026},
  version = {0.1.0},
  url = {https://github.com/<your-username>/protein-intelligence-hub}
}
```

## Demo Data
- Live data is used by default. Demo data only appears if `VITE_ENABLE_DEMO_FALLBACK=true`.
- Backend sample dossier: `backend/app/data/sample_dossier.json`
- Frontend fallback: `frontend/src/sampleDossier.ts`

## Search Filters
- Organism filter uses UniProt organism taxon IDs (default: human).
- Optional topic filter targets disease or study focus in ClinVar and PubMed.
- Variants and literature are paginated with 10 items per page by default.

## Integrating Real Databases
Each adapter lives in `backend/app/services/adapters/`.
1. Replace the `fetch` implementation with real API calls.
2. Normalize results into the dossier schema in `backend/app/schemas/dossier.py`.
3. Capture provenance in the `provenance` field.

## Notes
This scaffold focuses on clear data contracts, adapter boundaries, and a strong UX foundation. You can extend the adapters for deeper evidence and scoring.





<img width="1330" height="676" alt="image" src="https://github.com/user-attachments/assets/88ec5b28-4c41-4801-9127-7e96d61cbd6e" />

