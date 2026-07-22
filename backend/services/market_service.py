"""Marketplace transaction service with ACID-compliant buys."""
import logging
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import Agent, Product, Transaction, Review
from schemas import BuyResponse
from services.agent_service import get_agent
from services.llm_service import generate_review

logger = logging.getLogger("market_service")


def get_listings(db: Session, category: Optional[str] = None) -> List[dict]:
    """Return active product listings with aggregated review data."""
    query = db.query(Product).filter(Product.stock > 0)
    if category:
        query = query.filter(Product.category == category)

    products = query.all()
    listings = []
    for p in products:
        # Aggregate reviews for this product
        from sqlalchemy import func as sa_func
        review_data = (
            db.query(
                sa_func.coalesce(sa_func.avg(Review.rating_stars), 0),
                sa_func.count(Review.id),
            )
            .filter(Review.product_id == p.id)
            .first()
        )

        listings.append({
            "id": p.id,
            "name": p.name,
            "merchant_id": p.merchant_id,
            "category": p.category,
            "base_price": float(p.base_price),
            "current_price": float(p.current_price),
            "stock": p.stock,
            "sales_velocity": p.sales_velocity,
            "avg_rating": round(float(review_data[0]) if review_data else 0, 1),
            "review_count": review_data[1] if review_data else 0,
        })
    return listings


def execute_buy(
    db: Session, agent_id: int, product_id: int, tick_index: int
) -> BuyResponse:
    """
    ACID-compliant purchase transaction.
    Uses SELECT ... FOR UPDATE to prevent double-spending/overselling.
    """
    # Lock the product row
    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .with_for_update()
        .first()
    )
    if not product:
        return BuyResponse(success=False, message="Product not found.")

    if product.stock <= 0:
        return BuyResponse(success=False, message="Out of stock.")

    # Lock the agent row
    agent = (
        db.query(Agent)
        .filter(Agent.id == agent_id)
        .with_for_update()
        .first()
    )
    if not agent or agent.agent_type != "consumer":
        return BuyResponse(success=False, message="Invalid buyer.")

    price = product.current_price
    if agent.balance < price:
        return BuyResponse(
            success=False,
            message=f"Insufficient balance. Need ${float(price):.2f}, have ${float(agent.balance):.2f}",
        )

    # Execute the atomic trade
    agent.balance -= price
    product.stock -= 1
    product.sales_velocity += 1

    # Credit the merchant
    merchant = db.query(Agent).filter(Agent.id == product.merchant_id).with_for_update().first()
    if merchant:
        merchant.balance += price

    # Log transaction
    txn = Transaction(
        tick_index=tick_index,
        agent_id=agent_id,
        product_id=product_id,
        purchase_price=price,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    logger.info(
        f"[Tick {tick_index}] {agent.name} bought {product.name} "
        f"for ${float(price):.2f} | Txn #{txn.id}"
    )

    return BuyResponse(
        success=True,
        message=f"Purchase complete: {product.name}",
        transaction_id=txn.id,
        purchase_price=float(price),
    )


async def submit_review(
    db: Session,
    tick_index: int,
    agent_id: int,
    product_id: int,
    rating_stars: int,
    use_llm: bool = True,
) -> Review:
    """Submit a review, optionally generating text via LLM."""
    agent = get_agent(db, agent_id)
    product = db.query(Product).filter(Product.id == product_id).first()

    # Find the most recent purchase price for context
    txn = (
        db.query(Transaction)
        .filter(Transaction.agent_id == agent_id, Transaction.product_id == product_id)
        .order_by(Transaction.id.desc())
        .first()
    )
    price_context = float(txn.purchase_price) if txn else float(product.current_price)

    # Generate review text
    if use_llm and agent:
        personality = {
            "price_sensitivity": float(agent.price_sensitivity or 0.5),
            "impulsiveness": float(agent.impulsiveness or 0.5),
            "risk_tolerance": float(agent.risk_tolerance or 0.5),
            "brand_loyalty": float(agent.brand_loyalty or 0.5),
            "trend_alignment": float(agent.trend_alignment or 0.5),
        }
        review_text = await generate_review(
            agent_name=agent.name,
            personality=personality,
            product_name=product.name if product else "Unknown Product",
            product_category=product.category if product else "General",
            price_paid=price_context,
            rating_stars=rating_stars,
        )
    else:
        review_text = None

    review = Review(
        tick_index=tick_index,
        agent_id=agent_id,
        product_id=product_id,
        rating_stars=rating_stars,
        review_text=review_text,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def get_product_reviews(db: Session, product_id: int) -> List[Review]:
    return db.query(Review).filter(Review.product_id == product_id).order_by(Review.id.desc()).limit(50).all()
