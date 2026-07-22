"""Analytics & telemetry service v2 — wealth distribution, categories, leaderboard."""
from decimal import Decimal
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models import Agent, Product, Transaction, Review, TickSnapshot


def compute_gini(db: Session) -> float:
    balances = [float(a.balance) for a in db.query(Agent).filter(Agent.agent_type == "consumer").all()]
    n = len(balances)
    if n == 0:
        return 0.0
    balances.sort()
    total = sum(balances)
    if total == 0:
        return 0.0
    cumulative = 0.0
    area = 0.0
    for i, b in enumerate(balances):
        cumulative += b
        if i == 0:
            area += (cumulative / total) * (1 / n) / 2
        else:
            area += ((cumulative - b) / total + cumulative / total) * (1 / n) / 2
    return round(1 - 2 * area, 4)


def compute_avg_price_index(db: Session) -> float:
    result = db.query(func.avg(Product.current_price)).filter(Product.stock > 0).scalar()
    return round(float(result) if result else 0, 4)


def compute_active_consumers(db: Session, tick_index: int) -> int:
    count = db.query(func.count(func.distinct(Transaction.agent_id))).filter(
        Transaction.tick_index == tick_index
    ).scalar()
    return count or 0


def capture_snapshot(db: Session, tick_index: int):
    total_txn = db.query(func.count(Transaction.id)).filter(Transaction.tick_index == tick_index).scalar() or 0
    total_volume = db.query(func.sum(Transaction.purchase_price)).filter(
        Transaction.tick_index == tick_index
    ).scalar() or Decimal("0.00")
    gini = compute_gini(db)
    avg_price = compute_avg_price_index(db)
    active = compute_active_consumers(db, tick_index)

    existing = db.query(TickSnapshot).filter(TickSnapshot.tick_index == tick_index).first()
    if existing:
        existing.total_transactions = total_txn
        existing.total_volume = total_volume
        existing.gini_coefficient = gini
        existing.avg_price_index = avg_price
        existing.active_consumers = active
    else:
        snap = TickSnapshot(
            tick_index=tick_index,
            total_transactions=total_txn,
            total_volume=total_volume,
            gini_coefficient=gini,
            avg_price_index=avg_price,
            active_consumers=active,
        )
        db.add(snap)
    db.commit()


def get_snapshots(db: Session, limit: int = 100) -> List[TickSnapshot]:
    return db.query(TickSnapshot).order_by(TickSnapshot.tick_index.desc()).limit(limit).all()


def get_price_trend(db: Session, limit: int = 50) -> List[dict]:
    snaps = db.query(TickSnapshot).order_by(TickSnapshot.tick_index.desc()).limit(limit).all()
    return [{"tick": s.tick_index, "avg_price": float(s.avg_price_index or 0)} for s in reversed(snaps)]


def get_gini_trend(db: Session, limit: int = 50) -> List[dict]:
    snaps = db.query(TickSnapshot).order_by(TickSnapshot.tick_index.desc()).limit(limit).all()
    return [{"tick": s.tick_index, "gini": float(s.gini_coefficient or 0)} for s in reversed(snaps)]


def get_volume_trend(db: Session, limit: int = 50) -> List[dict]:
    snaps = db.query(TickSnapshot).order_by(TickSnapshot.tick_index.desc()).limit(limit).all()
    return [{"tick": s.tick_index, "volume": float(s.total_volume or 0)} for s in reversed(snaps)]


def get_top_products(db: Session, limit: int = 10) -> List[dict]:
    products = db.query(Product).order_by(desc(Product.sales_velocity)).limit(limit).all()
    return [
        {"id": p.id, "name": p.name, "category": p.category,
         "current_price": float(p.current_price), "stock": p.stock,
         "sales_velocity": p.sales_velocity}
        for p in products
    ]


def get_recent_reviews(db: Session, limit: int = 20) -> List[dict]:
    reviews = (
        db.query(Review, Agent.name.label("agent_name"), Product.name.label("product_name"))
        .join(Agent, Review.agent_id == Agent.id)
        .join(Product, Review.product_id == Product.id)
        .order_by(desc(Review.id))
        .limit(limit)
        .all()
    )
    return [
        {"id": r.Review.id, "tick": r.Review.tick_index, "agent_name": r.agent_name,
         "product_name": r.product_name, "rating": r.Review.rating_stars, "text": r.Review.review_text}
        for r in reviews
    ]


# ── NEW: Wealth Distribution ──
def get_wealth_distribution(db: Session) -> dict:
    """Decile breakdown of consumer wealth."""
    consumers = db.query(Agent).filter(Agent.agent_type == "consumer").all()
    balances = sorted([float(a.balance) for a in consumers])
    n = len(balances)
    if n == 0:
        return {"deciles": [], "richest": [], "poorest": []}

    deciles = []
    for i in range(10):
        start = int(n * i / 10)
        end = int(n * (i + 1) / 10)
        chunk = balances[start:end]
        deciles.append({
            "decile": i + 1,
            "count": len(chunk),
            "total": round(sum(chunk), 2),
            "avg": round(sum(chunk) / max(1, len(chunk)), 2),
            "min": round(chunk[0], 2) if chunk else 0,
            "max": round(chunk[-1], 2) if chunk else 0,
        })

    richest = sorted(consumers, key=lambda a: float(a.balance), reverse=True)[:5]
    poorest = sorted(consumers, key=lambda a: float(a.balance))[:5]

    return {
        "deciles": deciles,
        "richest": [{"name": a.name, "balance": float(a.balance)} for a in richest],
        "poorest": [{"name": a.name, "balance": float(a.balance)} for a in poorest],
        "total_wealth": round(sum(balances), 2),
        "avg_wealth": round(sum(balances) / n, 2),
    }


# ── NEW: Category Breakdown ──
def get_category_breakdown(db: Session) -> List[dict]:
    """Sales volume, avg price, and stock per category."""
    from models import CATEGORIES
    results = []
    for cat in CATEGORIES:
        products = db.query(Product).filter(Product.category == cat).all()
        results.append({
            "category": cat,
            "product_count": len(products),
            "total_sales": sum(p.sales_velocity for p in products),
            "total_stock": sum(p.stock for p in products),
            "avg_price": round(float(sum(p.current_price for p in products) / max(1, len(products))), 2),
            "total_value": round(float(sum(p.current_price * p.stock for p in products)), 2),
        })
    return sorted(results, key=lambda x: x["total_sales"], reverse=True)


# ── NEW: Agent Leaderboard ──
def get_agent_leaderboard(db: Session) -> dict:
    """Top agents by wealth and activity."""
    consumers = db.query(Agent).filter(Agent.agent_type == "consumer").all()
    merchants = db.query(Agent).filter(Agent.agent_type == "merchant").all()

    # Consumer rankings
    consumer_txns = (
        db.query(Transaction.agent_id, func.count(Transaction.id).label("count"),
                 func.sum(Transaction.purchase_price).label("spent"))
        .group_by(Transaction.agent_id)
        .all()
    )
    txn_map = {t.agent_id: {"count": t.count, "spent": float(t.spent or 0)} for t in consumer_txns}

    rich_consumers = sorted(consumers, key=lambda a: float(a.balance), reverse=True)[:10]
    active_consumers = sorted(consumers, key=lambda a: txn_map.get(a.id, {}).get("count", 0), reverse=True)[:5]

    return {
        "richest_consumers": [
            {"name": a.name, "balance": float(a.balance),
             "purchases": txn_map.get(a.id, {}).get("count", 0),
             "spent": txn_map.get(a.id, {}).get("spent", 0)}
            for a in rich_consumers
        ],
        "most_active": [
            {"name": a.name, "purchases": txn_map.get(a.id, {}).get("count", 0),
             "spent": round(txn_map.get(a.id, {}).get("spent", 0), 2)}
            for a in active_consumers
        ],
        "merchants": [
            {"name": m.name, "balance": float(m.balance), "strategy": m.pricing_strategy}
            for m in merchants
        ],
    }


# ── NEW: Recent Transactions Feed ──
def get_transaction_feed(db: Session, limit: int = 30) -> List[dict]:
    """Most recent transactions with agent/product names."""
    txns = (
        db.query(Transaction, Agent.name.label("agent_name"), Product.name.label("product_name"))
        .join(Agent, Transaction.agent_id == Agent.id)
        .join(Product, Transaction.product_id == Product.id)
        .order_by(desc(Transaction.id))
        .limit(limit)
        .all()
    )
    return [
        {"id": t.Transaction.id, "tick": t.Transaction.tick_index,
         "agent": t.agent_name, "product": t.product_name,
         "price": float(t.Transaction.purchase_price)}
        for t in txns
    ]


def get_dashboard_summary(db: Session) -> dict:
    current_tick = db.query(func.max(TickSnapshot.tick_index)).scalar() or 0
    total_agents = db.query(func.count(Agent.id)).filter(Agent.agent_type == "consumer").scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_txn = db.query(func.count(Transaction.id)).scalar() or 0
    total_volume = db.query(func.sum(Transaction.purchase_price)).scalar() or Decimal("0.00")

    latest = db.query(TickSnapshot).order_by(TickSnapshot.tick_index.desc()).first()

    return {
        "current_tick": current_tick,
        "total_agents": total_agents,
        "total_products": total_products,
        "total_transactions": total_txn,
        "total_volume": float(total_volume),
        "current_gini": float(latest.gini_coefficient) if latest else None,
        "avg_price_index": float(latest.avg_price_index) if latest else None,
        "price_trend": get_price_trend(db),
        "gini_trend": get_gini_trend(db),
        "volume_trend": get_volume_trend(db),
        "top_products": get_top_products(db),
        "recent_reviews": get_recent_reviews(db),
        "wealth_distribution": get_wealth_distribution(db),
        "category_breakdown": get_category_breakdown(db),
        "agent_leaderboard": get_agent_leaderboard(db),
        "recent_transactions": get_transaction_feed(db),
    }
