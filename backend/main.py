"""FastAPI application entry point for AMMS."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from database import engine, Base
from routers import agents, market, simulation, analytics, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("amm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-create tables on startup, seed default preset if empty, clean shutdown."""
    logger.info("Creating database tables if not exist...")
    Base.metadata.create_all(bind=engine)

    # Auto-seed default preset when database is empty
    from database import SessionLocal
    from models import Agent
    db = SessionLocal()
    try:
        if db.query(Agent).count() == 0:
            logger.info("Database empty — applying default preset...")
            from routers.simulation import apply_preset
            apply_preset("default", db=db)
            logger.info("Default preset applied.")
        else:
            logger.info("Existing agents found — skipping auto-seed.")
    except Exception as e:
        logger.error(f"Auto-seed failed: {e}")
        db.rollback()
    finally:
        db.close()

    logger.info("AMMS ready.")
    yield
    # Shutdown: stop simulation if running
    from services.simulation_service import engine as sim_engine
    if sim_engine.running:
        await sim_engine.stop()
    logger.info("AMMS shut down.")


app = FastAPI(
    title="Autonomous Multi-Agent Market Simulator",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(agents.router)
app.include_router(market.router)
app.include_router(simulation.router)
app.include_router(analytics.router)
app.include_router(ws.router)


@app.get("/")
@app.head("/")
def root():
    return {
        "app": "AMMS - Autonomous Multi-Agent Market Simulator",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
@app.head("/health")
def health():
    return {"status": "ok"}


# ── Serve frontend static files ──
import os
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
