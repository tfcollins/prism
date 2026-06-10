"""FastAPI app entry point."""

from fastapi import FastAPI

from prism_api import __version__
from prism_api.routers import admin as admin_router
from prism_api.routers import artifacts as artifacts_router
from prism_api.routers import auth as auth_router
from prism_api.routers import cases as cases_router
from prism_api.routers import compare as compare_router
from prism_api.routers import matrix as matrix_router
from prism_api.routers import overview as overview_router
from prism_api.routers import projects as projects_router
from prism_api.routers import runs as runs_router
from prism_api.routers import search as search_router
from prism_api.routers import suites as suites_router
from prism_api.routers import tokens as tokens_router
from prism_api.routers import user_settings as user_settings_router
from prism_api.routers import users as users_router

app = FastAPI(title="Prism API", version=__version__)
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(projects_router.router)
app.include_router(runs_router.router)
app.include_router(suites_router.router)
app.include_router(cases_router.router)
app.include_router(artifacts_router.router)
app.include_router(compare_router.router)
app.include_router(admin_router.router)
app.include_router(overview_router.router)
app.include_router(tokens_router.router)
app.include_router(user_settings_router.router)
app.include_router(matrix_router.router)
app.include_router(search_router.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
