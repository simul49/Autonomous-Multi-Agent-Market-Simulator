"""Marketplace API router: listings, buy, review."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from schemas import BuyRequest, ReviewRequest
from services.market_service import (
    get_listings, execute_buy, submit_review, get_product_reviews,
)
from services.simulation_service import engine

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/listings")
def list_market_items(
    category: str = Query(None),
    db: Session = Depends(get_db),
):
    """Get all active product listings."""
    return get_listings(db, category=category)


@router.post("/buy")
def buy_item(req: BuyRequest, db: Session = Depends(get_db)):
    """Execute a purchase (ACID-safe)."""
    tick = engine.current_tick
    result = execute_buy(db, req.agent_id, req.product_id, tick)
    return result


@router.post("/review")
async def submit_product_review(req: ReviewRequest, db: Session = Depends(get_db)):
    """Submit a product review (generates LLM text if review_text is empty)."""
    tick = engine.current_tick
    use_llm = req.review_text is None
    review = await submit_review(
        db, tick, req.agent_id, req.product_id,
        req.rating_stars, use_llm=use_llm,
    )
    return {
        "id": review.id,
        "tick_index": review.tick_index,
        "agent_id": review.agent_id,
        "product_id": review.product_id,
        "rating_stars": review.rating_stars,
        "review_text": review.review_text,
    }


@router.get("/reviews/{product_id}")
def get_reviews(product_id: int, db: Session = Depends(get_db)):
    reviews = get_product_reviews(db, product_id)
    return [
        {
            "id": r.id,
            "tick_index": r.tick_index,
            "agent_id": r.agent_id,
            "rating_stars": r.rating_stars,
            "review_text": r.review_text,
        }
        for r in reviews
    ]
