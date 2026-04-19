"""FastAPI app entry point."""
from fastapi import FastAPI

from prism_api import __version__
from prism_api.routers import auth as auth_router
from prism_api.routers import users as users_router

app = FastAPI(title="Prism API", version=__version__)
app.include_router(auth_router.router)
app.include_router(users_router.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
