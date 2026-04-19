"""FastAPI app entry point."""
from fastapi import FastAPI

from prism_api import __version__

app = FastAPI(title="Prism API", version=__version__)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
