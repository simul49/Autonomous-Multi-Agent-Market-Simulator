"""Analytics API router v2 — dashboard, trends, wealth, categories, leaderboard."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from services.analytics_service import (
    get_dashboard_summary, get_snapshots,
    get_wealth_distribution, get_category_breakdown,
    get_agent_leaderboard, get_transaction_feed,
)
from services.llm_service import test_providers

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return get_dashboard_summary(db)


@router.get("/snapshots")
def snapshots(limit: int = 100, db: Session = Depends(get_db)):
    snaps = get_snapshots(db, limit=limit)
    return [
        {
            "tick_index": s.tick_index,
            "total_transactions": s.total_transactions,
            "total_volume": float(s.total_volume),
            "gini_coefficient": float(s.gini_coefficient) if s.gini_coefficient else None,
            "avg_price_index": float(s.avg_price_index) if s.avg_price_index else None,
            "active_consumers": s.active_consumers,
        }
        for s in snaps
    ]


@router.get("/wealth")
def wealth_distribution(db: Session = Depends(get_db)):
    return get_wealth_distribution(db)


@router.get("/categories")
def category_breakdown(db: Session = Depends(get_db)):
    return get_category_breakdown(db)


@router.get("/leaderboard")
def agent_leaderboard(db: Session = Depends(get_db)):
    return get_agent_leaderboard(db)


@router.get("/transactions")
def transaction_feed(limit: int = 30, db: Session = Depends(get_db)):
    return get_transaction_feed(db, limit=limit)


@router.get("/test-llm")
async def test_llm_connectivity():
    return await test_providers()
