"""Consumer & Merchant agent management service."""
import random
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session

from models import Agent
from schemas import AgentCreate, AgentPersonality


NAMES_POOL = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank",
    "Iris", "Jack", "Kate", "Leo", "Mia", "Noah", "Olivia", "Paul",
    "Quinn", "Rose", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zack", "Aria", "Ben", "Cleo", "Dan", "Ella", "Finn",
    "Gina", "Hugo", "Ivy", "Jake", "Kira", "Liam", "Maya", "Nate",
    "Oscar", "Piper", "Quentin", "Ruby", "Steve", "Tara", "Ulysses",
    "Vera", "Will", "Xena", "Yuri", "Zara",
]


def random_personality() -> dict:
    """Generate a random agent personality vector."""
    return {
        "price_sensitivity": round(random.random(), 2),
        "impulsiveness": round(random.random(), 2),
        "risk_tolerance": round(random.random(), 2),
        "brand_loyalty": round(random.random(), 2),
        "trend_alignment": round(random.random(), 2),
    }


def create_consumer(db: Session, name: str, balance: float = 500.00) -> Agent:
    """Create a consumer agent with random personality."""
    p = random_personality()
    agent = Agent(
        name=name,
        agent_type="consumer",
        balance=Decimal(str(round(balance, 2))),
        price_sensitivity=p["price_sensitivity"],
        impulsiveness=p["impulsiveness"],
        risk_tolerance=p["risk_tolerance"],
        brand_loyalty=p["brand_loyalty"],
        trend_alignment=p["trend_alignment"],
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def create_merchant(db: Session, name: str, pricing_strategy: str = "adaptive") -> Agent:
    """Create a merchant agent."""
    agent = Agent(
        name=name,
        agent_type="merchant",
        balance=Decimal("10000.00"),
        pricing_strategy=pricing_strategy,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_consumers(db: Session) -> List[Agent]:
    return db.query(Agent).filter(Agent.agent_type == "consumer").all()


def get_merchants(db: Session) -> List[Agent]:
    return db.query(Agent).filter(Agent.agent_type == "merchant").all()


def get_agent(db: Session, agent_id: int) -> Optional[Agent]:
    return db.query(Agent).filter(Agent.id == agent_id).first()


def add_income_to_all(db: Session, amount: Decimal, tick: int):
    """Distribute base income to all consumer agents."""
    consumers = db.query(Agent).filter(Agent.agent_type == "consumer").all()
    for c in consumers:
        c.balance += amount
    db.commit()


def adjust_balances(db: Session, agent_id: int, delta: Decimal):
    """Safely adjust an agent's balance."""
    agent = db.query(Agent).filter(Agent.id == agent_id).with_for_update().first()
    if agent:
        agent.balance += delta
        db.commit()


def get_all_agents(db: Session) -> List[Agent]:
    return db.query(Agent).all()
