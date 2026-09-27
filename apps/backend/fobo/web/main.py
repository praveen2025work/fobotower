import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fobo.web.auth import dev_caller_middleware
from fobo.web.dependencies import setup_checkpointer
from fobo.web.routes import console, investigations, workflow_config
from fobo.investigation.versions import Invalid, VersionError


def _console_origins() -> list[str]:
    """The consoles allowed to call the API. FOBO_CONSOLE_ORIGINS is a
    comma-separated list; the e2e console runs on its own port."""
    raw = os.getenv("FOBO_CONSOLE_ORIGINS", "http://localhost:3100")
    return [o.strip() for o in raw.split(",") if o.strip()]


async def _version_error(_request, exc: VersionError) -> JSONResponse:
    """A refused workflow change, in the API's usual `detail` envelope. A
    validation failure lists every problem so the console can show each one."""
    detail = (
        {"message": str(exc), "errors": exc.errors}
        if isinstance(exc, Invalid) and exc.errors
        else str(exc)
    )
    return JSONResponse(status_code=exc.status, content={"detail": detail})


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Creates the checkpoint tables/indexes before this process serves its
    # first request — see setup_checkpointer's docstring for why doing this
    # lazily, inside a request, can deadlock forever on a fresh database.
    await setup_checkpointer()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="FOBO Investigation API", version="0.1.0", lifespan=_lifespan)
    # Registered before CORS so CORS wraps it: a refused dev caller still
    # gets the CORS headers the browser needs to read the 400.
    app.middleware("http")(dev_caller_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_console_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(VersionError, _version_error)
    # console.router owns GET /api/board and POST /api/recs/{id}/messages
    # and /decisions; investigations.router only adds /investigate and
    # /trace, so the two routers never collide.
    app.include_router(investigations.router)
    app.include_router(console.router)
    app.include_router(workflow_config.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
