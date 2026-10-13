from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.api.routes import auth, dashboard, incidents, logs, analysis, copilot, remediation, knowledge, models_audit

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TraceIQ starting up", version=settings.VERSION, environment=settings.ENVIRONMENT)
    # Load ML model if it exists
    try:
        from app.ml.anomaly_detector import get_detector
        detector = get_detector()
        if detector.is_trained():
            logger.info("ML model loaded", trained_at=str(detector.trained_at))
        else:
            logger.info("No ML model found. Train one via POST /api/v1/models/train")
    except Exception as e:
        logger.warning(f"ML model loading error: {e}")
    yield
    logger.info("TraceIQ shutting down")


app = FastAPI(
    title="TraceIQ API",
    description="AI Root Cause Analysis & Intelligent Ticket Resolution Copilot",
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
prefix = "/api/v1"
app.include_router(auth.router, prefix=prefix)
app.include_router(dashboard.router, prefix=prefix)
app.include_router(incidents.router, prefix=prefix)
app.include_router(logs.router, prefix=prefix)
app.include_router(analysis.router, prefix=prefix)
app.include_router(copilot.router, prefix=prefix)
app.include_router(remediation.router, prefix=prefix)
app.include_router(knowledge.router, prefix=prefix)
app.include_router(models_audit.router, prefix=prefix)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/ready")
async def ready():
    """Readiness probe: check DB connection."""
    try:
        from app.db.session import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "not_ready", "error": str(e)})
