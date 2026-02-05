from locust import HttpUser, task, between
import os
import random

API_BASE = os.getenv("PIH_API_BASE", "http://localhost:8000")
ORGANISM = os.getenv("PIH_ORGANISM_TAXON_ID", "9606")

with open(os.path.join(os.path.dirname(__file__), "..", "data", "gene_list.txt")) as f:
    GENES = [line.strip() for line in f if line.strip()]


class DossierUser(HttpUser):
    wait_time = between(0.2, 1.2)
    host = API_BASE

    @task
    def dossier(self):
        gene = random.choice(GENES)
        self.client.get(
            f"/api/proteins/{gene}/dossier",
            params={"organism_taxon_id": ORGANISM, "variant_page": 1, "variant_page_size": 10},
            name="/api/proteins/{gene}/dossier",
        )
