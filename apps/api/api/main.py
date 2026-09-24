from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import dev_caller_middleware
from api.routes import (
    analytics,
    books,
    breaks,
    decisions,
    helix,
    recs,
    runs,
    sessions,
    worklist,
)
from api.websocket import handler

CONSOLE_ORIGIN = "http://localhost:3100"


def create_app() -> FastAPI:
    app = FastAPI(title="FOBO Investigation API", version="0.1.0")
    # Registered before CORS so CORS wraps it: a refused dev caller still
    # gets the CORS headers the browser needs to read the 400.
    app.middleware("http")(dev_caller_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[CONSOLE_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(runs.router)
    app.include_router(sessions.router)
    app.include_router(recs.router)
    app.include_router(decisions.router)
    app.include_router(worklist.router)
    app.include_router(analytics.router)
    app.include_router(books.router)
    app.include_router(breaks.router)
    app.include_router(helix.router)
    app.include_router(handler.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
