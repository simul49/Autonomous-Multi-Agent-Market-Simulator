"""WebSocket router — real-time simulation event streaming v2."""
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.ws_manager import ws_manager
from services.simulation_service import engine
from services.analytics_service import (
    compute_gini, compute_avg_price_index,
    get_top_products, get_transaction_feed,
)
from database import SessionLocal
from models import Agent, Product, Transaction, Review

logger = logging.getLogger("ws_router")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws, "dashboard")
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, "dashboard")
    except Exception as e:
        logger.warning(f"WS error: {e}")
        ws_manager.disconnect(ws, "dashboard")


def build_tick_event(tick_index: int) -> dict:
    db = SessionLocal()
    try:
        from sqlalchemy import func

        gini = compute_gini(db)
        avg_price = compute_avg_price_index(db)
        total_txn = db.query(Transaction).count()
        total_agents = db.query(Agent).filter(Agent.agent_type == "consumer").count()
        total_products = db.query(Product).count()

        # Recent reviews for this tick
        reviews = (
            db.query(Review, Agent.name.label("agent_name"), Product.name.label("product_name"))
            .join(Agent, Review.agent_id == Agent.id)
            .join(Product, Review.product_id == Product.id)
            .filter(Review.tick_index == tick_index)
            .order_by(Review.id.desc())
            .limit(5)
            .all()
        )

        # Recent transactions for this tick
        txns = (
            db.query(Transaction, Agent.name.label("agent_name"), Product.name.label("product_name"))
            .join(Agent, Transaction.agent_id == Agent.id)
            .join(Product, Transaction.product_id == Product.id)
            .filter(Transaction.tick_index == tick_index)
            .order_by(Transaction.id.desc())
            .limit(15)
            .all()
        )

        return {
            "type": "tick_update",
            "tick": tick_index,
            "gini": gini,
            "avg_price": avg_price,
            "total_agents": total_agents,
            "total_products": total_products,
            "total_transactions": total_txn,
            "reviews": [
                {"id": r.Review.id, "tick": r.Review.tick_index,
                 "agent_name": r.agent_name, "product_name": r.product_name,
                 "rating": r.Review.rating_stars, "text": r.Review.review_text}
                for r in reviews
            ],
            "recent_transactions": [
                {"id": t.Transaction.id, "tick": t.Transaction.tick_index,
                 "agent": t.agent_name, "product": t.product_name,
                 "price": float(t.Transaction.purchase_price)}
                for t in txns
            ],
            "top_products": get_top_products(db),
            "price_point": {"tick": tick_index, "avg_price": avg_price},
            "gini_point": {"tick": tick_index, "gini": gini},
            "active_events": engine.get_active_events(),
        }
    finally:
        db.close()


async def _on_tick(tick_index: int):
    try:
        event = build_tick_event(tick_index)
        await ws_manager.broadcast(event)
    except Exception as e:
        logger.error(f"Tick broadcast error: {e}")


def _sync_tick_callback(tick_index: int):
    asyncio.create_task(_on_tick(tick_index))


engine.on_tick(_sync_tick_callback)
