"""Simulation control API router v2 — with presets and events."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from services.simulation_service import engine
from services.agent_service import create_consumer, create_merchant
from models import Agent, Product, CATEGORIES
from decimal import Decimal
import random

router = APIRouter(prefix="/simulation", tags=["simulation"])

PRESETS = {
    "default": {
        "label": "Default Market",
        "desc": "Balanced economy with 5 merchants, 20 products, 50 consumers",
        "consumers": 50, "merchants": 5, "products_per_merchant": 4,
        "strategies": ["adaptive", "aggressive", "conservative", "loss_leader", "premium"],
        "income": 15, "income_interval": 10,
        "consumer_balance": (50, 500),
    },
    "inequality": {
        "label": "Extreme Inequality",
        "desc": "Few rich consumers, many poor — study wealth concentration",
        "consumers": 50, "merchants": 3, "products_per_merchant": 4,
        "strategies": ["premium", "premium", "aggressive"],
        "income": 5, "income_interval": 20,
        "consumer_balance": (5, 2000),
    },
    "price_war": {
        "label": "Price War",
        "desc": "All merchants aggressive — watch the race to the bottom",
        "consumers": 40, "merchants": 6, "products_per_merchant": 5,
        "strategies": ["aggressive"] * 6,
        "income": 20, "income_interval": 8,
        "consumer_balance": (100, 300),
    },
    "viral_market": {
        "label": "Viral Market",
        "desc": "High impulsiveness & trend alignment — see fads emerge",
        "consumers": 60, "merchants": 4, "products_per_merchant": 5,
        "strategies": ["adaptive", "adaptive", "loss_leader", "premium"],
        "income": 15, "income_interval": 10,
        "consumer_balance": (30, 400),
        "personality_bias": {"impulsiveness": 0.7, "trend_alignment": 0.7},
    },
    "recession": {
        "label": "Recession",
        "desc": "High price sensitivity, low risk tolerance, low income",
        "consumers": 50, "merchants": 4, "products_per_merchant": 4,
        "strategies": ["conservative", "conservative", "adaptive", "loss_leader"],
        "income": 5, "income_interval": 15,
        "consumer_balance": (10, 200),
        "personality_bias": {"price_sensitivity": 0.8, "risk_tolerance": 0.2},
    },
}

PRODUCT_POOLS = {
    "Electronics": ["Wireless Earbuds", "USB-C Hub", "Mechanical Keyboard", "4K Monitor",
                    "Bluetooth Speaker", "Smart Watch", "Tablet Stand", "Webcam Pro", "VR Headset", "Drone"],
    "Clothing": ["Denim Jacket", "Running Shoes", "Cotton T-Shirt", "Winter Coat",
                 "Sunglasses", "Leather Belt", "Wool Scarf", "Casual Sneakers", "Hoodie", "Blazer"],
    "Food": ["Organic Coffee", "Protein Bars", "Green Tea Box", "Dark Chocolate",
             "Trail Mix Pack", "Instant Ramen Set", "Olive Oil Bottle", "Dried Mango", "Honey Jar", "Spice Kit"],
    "Books": ["Python Cookbook", "Sci-Fi Novel", "Self-Help Guide", "History Epic",
              "Mystery Thriller", "Art Book", "Travel Guide", "Philosophy Text", "Biography", "Poetry Collection"],
    "Home": ["Throwsilk Blanket", "Scented Candle", "Wall Art Print", "Desk Lamp",
             "Plant Pot Set", "Yoga Mat", "Water Bottle", "Notebook Set", "Wall Clock", "Storage Basket"],
}

CONSUMER_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry",
    "Iris", "Jack", "Kate", "Leo", "Maria", "Nathan", "Olivia", "Paul",
    "Quinn", "Rachel", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zack", "Amber", "Brian", "Clara", "Derek", "Elena", "Felix",
    "Gina", "Hugo", "Ivy", "Jake", "Kira", "Liam", "Mona", "Nora",
    "Oscar", "Penny", "Quade", "Rosa", "Sean", "Tara", "Ugo", "Vera", "Will", "Xena",
    "Aria", "Ben", "Cleo", "Dan", "Ella", "Finn", "Gia", "Hank", "Isla", "Jude",
    "Kai", "Luna", "Milo", "Nia", "Owen", "Petra",
]


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    from models import Agent, Product, Transaction
    from services.analytics_service import compute_gini

    return {
        "running": engine.running,
        "tick": engine.current_tick,
        "agents_count": db.query(Agent).filter(Agent.agent_type == "consumer").count(),
        "merchants_count": db.query(Agent).filter(Agent.agent_type == "merchant").count(),
        "products_count": db.query(Product).count(),
        "total_transactions": db.query(Transaction).count(),
        "current_gini": compute_gini(db),
        "tick_speed_ms": engine.tick_speed_ms,
        "active_events": engine.get_active_events(),
    }


@router.post("/start")
async def start_simulation():
    await engine.start()
    return {"status": "started", "tick": engine.current_tick}


@router.post("/stop")
async def stop_simulation():
    await engine.stop()
    return {"status": "stopped", "tick": engine.current_tick}


@router.post("/step")
async def step_simulation():
    tick = await engine.step_once()
    return {"status": "stepped", "tick": tick}


@router.post("/speed")
def set_speed(ms: int = Query(default=2000, ge=100, le=10000)):
    engine.set_speed(ms)
    return {"tick_speed_ms": engine.tick_speed_ms}


@router.post("/reset")
def reset_simulation(db: Session = Depends(get_db)):
    from models import Transaction, Review, TickSnapshot, Product, Agent

    db.query(TickSnapshot).delete()
    db.query(Review).delete()
    db.query(Transaction).delete()
    db.query(Product).delete()
    db.query(Agent).delete()
    db.commit()

    engine._tick = 0
    engine._events.clear()
    engine._event_history.clear()
    engine._social_graph.clear()
    engine._purchase_history.clear()
    engine._bankruptcy_cooldown.clear()

    return {"status": "reset"}


@router.get("/events")
def get_events():
    """Get active and recent market events."""
    return {
        "active": engine.get_active_events(),
        "history": engine.get_event_history(),
    }


@router.get("/presets")
def get_presets():
    """Available simulation presets."""
    return [{"id": k, "label": v["label"], "desc": v["desc"]} for k, v in PRESETS.items()]


@router.post("/presets/{preset_id}")
def apply_preset(preset_id: str, db: Session = Depends(get_db)):
    """Reset and seed with a specific preset configuration."""
    if preset_id not in PRESETS:
        return {"status": "error", "message": f"Unknown preset: {preset_id}"}

    # Reset first
    from models import Transaction, Review, TickSnapshot, Product as ProductModel, Agent as AgentModel
    db.query(TickSnapshot).delete()
    db.query(Review).delete()
    db.query(Transaction).delete()
    db.query(ProductModel).delete()
    db.query(AgentModel).delete()
    db.commit()

    engine._tick = 0
    engine._events.clear()
    engine._event_history.clear()
    engine._social_graph.clear()
    engine._purchase_history.clear()
    engine._bankruptcy_cooldown.clear()

    cfg = PRESETS[preset_id]
    bias = cfg.get("personality_bias", {})

    # Create merchants
    merchant_names = ["MegaMart", "EcoShop", "PrimeStore", "ValueKing", "TrendHub", "BargainBin"][:cfg["merchants"]]
    merchant_ids = []
    for i, mn in enumerate(merchant_names):
        strategy = cfg["strategies"][i] if i < len(cfg["strategies"]) else "adaptive"
        m = AgentModel(name=mn, agent_type="merchant", balance=Decimal("5000.00"), pricing_strategy=strategy)
        db.add(m)
        db.flush()
        merchant_ids.append(m.id)

    # Create products
    product_counter = 1
    for mid in merchant_ids:
        for _ in range(cfg["products_per_merchant"]):
            cat = random.choice(CATEGORIES)
            pool = PRODUCT_POOLS.get(cat, ["Item"])
            pname = random.choice(pool) + f" #{product_counter}"
            product_counter += 1
            bp = Decimal(str(round(random.uniform(5, 200), 2)))
            p = ProductModel(name=pname, merchant_id=mid, category=cat,
                             base_price=bp, current_price=bp,
                             stock=random.randint(50, 200))
            db.add(p)

    # Create consumers
    names = random.sample(CONSUMER_NAMES, min(cfg["consumers"], len(CONSUMER_NAMES)))
    for name in names:
        bal = Decimal(str(random.randint(*cfg["consumer_balance"])))
        agent = AgentModel(
            name=name, agent_type="consumer", balance=bal,
            price_sensitivity=Decimal(str(round(random.uniform(0.1, 0.9), 2)))
                if "price_sensitivity" not in bias
                else Decimal(str(round(random.uniform(bias["price_sensitivity"], min(0.99, bias["price_sensitivity"] + 0.2)), 2))),
            impulsiveness=Decimal(str(round(random.uniform(0.1, 0.9), 2)))
                if "impulsiveness" not in bias
                else Decimal(str(round(random.uniform(bias["impulsiveness"], min(0.99, bias["impulsiveness"] + 0.2)), 2))),
            risk_tolerance=Decimal(str(round(random.uniform(0.1, 0.9), 2)))
                if "risk_tolerance" not in bias
                else Decimal(str(round(random.uniform(bias["risk_tolerance"], min(0.99, bias["risk_tolerance"] + 0.2)), 2))),
            brand_loyalty=Decimal(str(round(random.uniform(0.1, 0.9), 2))),
            trend_alignment=Decimal(str(round(random.uniform(0.1, 0.9), 2)))
                if "trend_alignment" not in bias
                else Decimal(str(round(random.uniform(bias["trend_alignment"], min(0.99, bias["trend_alignment"] + 0.2)), 2))),
        )
        db.add(agent)

    db.commit()
    engine._build_social_graph()

    return {"status": "ok", "preset": preset_id, "label": cfg["label"],
            "consumers": cfg["consumers"], "merchants": cfg["merchants"]}
