from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Protein Intelligence Hub"
    api_v1_prefix: str = "/api"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60 * 24
    algorithm: str = "HS256"

    # Default to SQLite for local demo; override with DATABASE_URL for Postgres.
    database_url: str = "sqlite:///./protein_hub.db"
    uniprot_base_url: str = "https://rest.uniprot.org"
    ncbi_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    ncbi_api_key: str | None = None
    ncbi_tool: str = "protein-intelligence-hub"
    ncbi_email: str | None = None
    string_base_url: str = "https://string-db.org/api"
    reactome_base_url: str = "https://reactome.org/ContentService"
    reactome_analysis_base_url: str = "https://reactome.org/AnalysisService"
    alphafold_base_url: str = "https://alphafold.ebi.ac.uk/api"
    europe_pmc_base_url: str = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
