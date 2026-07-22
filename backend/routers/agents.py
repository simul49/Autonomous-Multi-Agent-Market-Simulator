"""Agent management API router."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from services.agent_service import (
    create_consumer, create_merchant, get_consumers,
    get_merchants, get_agent, NAMES_POOL,
)
import random

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/")
def list_agents(
    agent_type: str = Query(None, description="Filter: consumer | merchant"),
    db: Session = Depends(get_db),
):
    """List all agents, optionally filtered by type."""
    if agent_type:
        from models import Agent
        agents = db.query(Agent).filter(Agent.agent_type == agent_type).all()
    else:
        from models import Agent
        agents = db.query(Agent).all()
    return [_agent_to_dict(a) for a in agents]


@router.get("/consumers")
def list_consumers(db: Session = Depends(get_db)):
    return [_agent_to_dict(a) for a in get_consumers(db)]


@router.get("/merchants")
def list_merchants(db: Session = Depends(get_db)):
    return [_agent_to_dict(a) for a in get_merchants(db)]


@router.get("/{agent_id}")
def get_agent_detail(agent_id: int, db: Session = Depends(get_db)):
    agent = get_agent(db, agent_id)
    if not agent:
        return {"error": "Agent not found"}
    return _agent_to_dict(agent)


@router.post("/consumers/spawn")
def spawn_consumer(db: Session = Depends(get_db)):
    """Spawn a single random consumer agent."""
    name = random.choice(NAMES_POOL) + "-" + str(random.randint(100, 999))
    agent = create_consumer(db, name)
    return _agent_to_dict(agent)


@router.post("/merchants/spawn")
def spawn_merchant(db: Session = Depends(get_db)):
    """Spawn a single merchant agent."""
    name = random.choice(["MegaMart", "EcoShop", "PrimeStore", "ValueKing",
                           "TrendHub", "DealZone", "ShopNova", "NextGen"]) + "-" + str(random.randint(10, 99))
    agent = create_merchant(db, name)
    return _agent_to_dict(agent)


@router.post("/consumers/batch")
def spawn_consumers_batch(count: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)):
    """Spawn multiple consumer agents at once."""
    used = set()
    agents = []
    for _ in range(count):
        name = random.choice(NAMES_POOL)
        while name in used:
            name = random.choice(NAMES_POOL) + str(random.randint(1, 99))
        used.add(name)
        agents.append(create_consumer(db, name))
    return {"spawned": len(agents)}


def _agent_to_dict(agent):
    from models import Transaction
    from database import SessionLocal
    purchase_count = 0
    if agent.agent_type == "consumer":
        db2 = SessionLocal()
        try:
            purchase_count = db2.query(Transaction).filter(Transaction.agent_id == agent.id).count()
        finally:
            db2.close()

    return {
        "id": agent.id,
        "name": agent.name,
        "agent_type": agent.agent_type,
        "balance": float(agent.balance),
        "price_sensitivity": float(agent.price_sensitivity) if agent.price_sensitivity is not None else None,
        "impulsiveness": float(agent.impulsiveness) if agent.impulsiveness is not None else None,
        "risk_tolerance": float(agent.risk_tolerance) if agent.risk_tolerance is not None else None,
        "brand_loyalty": float(agent.brand_loyalty) if agent.brand_loyalty is not None else None,
        "trend_alignment": float(agent.trend_alignment) if agent.trend_alignment is not None else None,
        "pricing_strategy": agent.pricing_strategy,
        "purchase_count": purchase_count,
    }
