"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import keywords, contents, tasks, settings, sources

app = FastAPI(
    title="Social Discovery Agent API",
    version="0.1.0",
    description="Internal content-discovery tool – backend API",
)

# Allow Streamlit (default port 8501) to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(keywords.router)
app.include_router(contents.router)
app.include_router(tasks.router)
app.include_router(settings.router)
app.include_router(sources.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "message": "Social Discovery Agent API is running"}
