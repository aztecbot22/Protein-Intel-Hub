from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import annotations, auth, dossier, export, health
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(dossier.router, prefix=settings.api_v1_prefix)
app.include_router(annotations.router, prefix=settings.api_v1_prefix)
app.include_router(export.router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def startup() -> None:
    # Ensure tables exist for local/demo deployments.
    Base.metadata.create_all(bind=engine)
