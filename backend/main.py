"""
Claura Backend — main.py
FastAPI application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from routes import auth, upload, analyse, results
from services.model import load_model
from services.database import init_db

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model and initialise DB on startup."""
    logger.info("Starting Claura backend...")
    await init_db()
    load_model()
    logger.info("Ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Claura API",
    description="Legal clause risk classification for UK construction subcontractors",
    version="0.1.0",
    lifespan=lifespan
)

# CORS — allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:8080",
        "https://claura.ai",
        "https://www.claura.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router,    prefix="/auth",    tags=["auth"])
app.include_router(upload.router,  prefix="/upload",  tags=["upload"])
app.include_router(analyse.router, prefix="/analyse", tags=["analyse"])
app.include_router(results.router, prefix="/results", tags=["results"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "claura-api"}


# Serve frontend static files — must be last
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
