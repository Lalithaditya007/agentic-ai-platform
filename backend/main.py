from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys

# Force UTF-8 encoding for Windows terminal to prevent print() crashes
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from config import settings
from database.models import create_tables
from memory.redis_client import init_redis
from memory.chromadb_client import init_chromadb


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    print("[STARTUP] Starting Universal Agentic AI Platform...")

    # Initialize capability registry
    from capabilities.registry import capability_registry
    try:
        capability_registry.load_from_yaml()
        print("[OK] Capabilities loaded successfully")
    except Exception as e:
        print(f"[WARN] Failed to load capabilities: {e}")


    # Initialize database tables
    try:
        await create_tables()
        print("[OK] PostgreSQL tables ready")
    except Exception as e:
        print(f"[WARN] PostgreSQL startup error: {e}")

    # Initialize Redis connection
    try:
        await init_redis()
        print("[OK] Redis (Upstash) connected")
    except Exception as e:
        print(f"[WARN] Redis connection failed (caching disabled): {e}")

    # Initialize ChromaDB
    try:
        init_chromadb()
        print("[OK] ChromaDB (embedded) initialized")
    except Exception as e:
        print(f"[WARN] ChromaDB startup error: {e}")

    print("[OK] Platform ready - http://localhost:8000")
    yield

    print("[SHUTDOWN] Shutting down platform...")


app = FastAPI(
    title="Universal Agentic AI Platform",
    description="Dynamically creates and orchestrates AI agents for any B2B customer discovery domain.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register API routers ───────────────────────────────────
from api import projects, icp, workflows, hitl, analytics, ws, dag_preview

app.include_router(projects.router,    prefix="/api", tags=["Projects"])
app.include_router(icp.router,         prefix="/api", tags=["ICP"])
app.include_router(workflows.router,   prefix="/api", tags=["Workflows"])
app.include_router(hitl.router,        prefix="/api", tags=["HITL"])
app.include_router(analytics.router,   prefix="/api", tags=["Analytics"])
app.include_router(dag_preview.router, prefix="/api", tags=["DAG"])
app.include_router(ws.router,          tags=["WebSocket"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ok",
        "platform": "Universal Agentic AI Platform",
        "version": "1.0.0",
        "llm_provider": settings.LLM_PROVIDER,
        "demo_mode": settings.DEMO_MODE,
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
