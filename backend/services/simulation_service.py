"""Tick-based simulation engine v2 — events, social influence, trend cycles, bankruptcy."""
import asyncio
import logging
import random
from decimal import Decimal
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Agent, Product
from services.market_service import get_listings, execute_buy, submit_review
from services.agent_service import add_income_to_all
from services.analytics_service import capture_snapshot
from services.llm_service import generate_review

logger = logging.getLogger("simulation")

# ── Market Event System ──
EVENT_TYPES = {
    "supply_shock": {"icon": "📉", "desc": "Supply chain disruption in {cat}! Stock halved.", "stock_mult": 0.5, "price_mult": 1.3, "duration": (3, 6)},
    "demand_surge": {"icon": "🔥", "desc": "{cat} goes viral! Demand skyrocketing.", "stock_mult": 1.0, "price_mult": 1.5, "duration": (3, 5)},
    "price_crash": {"icon": "💥", "desc": "Price war in {cat}! Prices collapsing.", "stock_mult": 1.0, "price_mult": 0.6, "duration": (2, 4)},
    "innovation": {"icon": "🚀", "desc": "Tech breakthrough in {cat}! New interest.", "stock_mult": 1.5, "price_mult": 1.1, "duration": (4, 8)},
    "recession_fear": {"icon": "⚠️", "desc": "Recession fears! Consumers tightening budgets.", "stock_mult": 1.0, "price_mult": 0.8, "duration": (5, 10), "global": True},
    "stimulus": {"icon": "💰", "desc": "Government stimulus! Extra income for all.", "stock_mult": 1.0, "price_mult": 1.2, "duration": (2, 3), "global": True},
}

CATEGORIES = ["Electronics", "Clothing", "Food", "Books", "Home"]


class MarketEvent:
    def __init__(self, etype: str, category: str, tick: int, duration: int, desc: str, data: dict):
        self.type = etype
        self.category = category
        self.start_tick = tick
        self.duration = duration
        self.description = desc
        self.data = data

    def active(self, current_tick: int) -> bool:
        return current_tick - self.start_tick < self.duration

    def to_dict(self):
        return {
            "type": self.type,
            "category": self.category,
            "start_tick": self.start_tick,
            "duration": self.duration,
            "description": self.description,
            "active": True,
        }


class SimulationEngine:
    """Orchestrates discrete tick-based market simulation with events & social dynamics."""

    def __init__(self):
        self._running = False
        self._tick = 0
        self._task: Optional[asyncio.Task] = None
        self._tick_callbacks = []
        self._speed_ms = 2000
        self._events: List[MarketEvent] = []
        self._event_history: List[dict] = []
        self._social_graph: Dict[int, List[int]] = {}  # agent_id → [peer_ids]
        self._category_trends: Dict[str, float] = {c: 1.0 for c in CATEGORIES}
        self._purchase_history: Dict[int, set] = {}  # agent_id → {product_ids bought}
        self._bankruptcy_cooldown: Dict[int, int] = {}  # agent_id → tick when recoverable

    # ── Properties ──
    @property
    def running(self) -> bool:
        return self._running

    @property
    def current_tick(self) -> int:
        return self._tick

    @property
    def tick_speed_ms(self) -> int:
        return self._speed_ms

    def set_speed(self, ms: int):
        self._speed_ms = max(100, min(10000, ms))

    def on_tick(self, callback):
        self._tick_callbacks.append(callback)

    def get_active_events(self) -> List[dict]:
        return [e.to_dict() for e in self._events if e.active(self._tick)]

    def get_event_history(self) -> List[dict]:
        return self._event_history[-20:]

    # ── Lifecycle ──
    async def start(self, start_tick: int = 0):
        if self._running:
            return
        self._running = True
        self._tick = start_tick
        self._build_social_graph()
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Simulation started at tick {self._tick}")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Simulation stopped at tick {self._tick}")

    async def step_once(self) -> int:
        db = SessionLocal()
        try:
            await self._execute_tick(db, self._tick + 1)
            self._tick += 1
            for cb in self._tick_callbacks:
                try:
                    cb(self._tick)
                except Exception:
                    pass
            return self._tick
        finally:
            db.close()

    # ── Main Loop ──
    async def _loop(self):
        while self._running:
            db = SessionLocal()
            try:
                self._tick += 1
                start = asyncio.get_event_loop().time()
                await self._execute_tick(db, self._tick)
                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                logger.info(f"Tick {self._tick} completed in {elapsed:.0f}ms")

                for cb in self._tick_callbacks:
                    try:
                        cb(self._tick)
                    except Exception:
                        pass

                wait = max(0, self._speed_ms - elapsed) / 1000.0
                await asyncio.sleep(wait)
            except asyncio.CancelledError:
                db.close()
                raise
            except Exception:
                logger.exception(f"Error during tick {self._tick}")
            finally:
                if db.is_active:
                    db.close()

    # ── Tick Pipeline ──
    async def _execute_tick(self, db: Session, tick_index: int):
        # Phase 0: Category trend drift
        self._drift_category_trends()

        # Phase 0.5: Random market events (~8% chance per tick)
        if random.random() < 0.08:
            self._generate_event(tick_index)

        # Phase 1: Periodic income
        from config import settings
        if tick_index % settings.INCOME_INTERVAL_TICKS == 1:
            add_income_to_all(db, Decimal(str(settings.INCOME_PER_TICK)), tick_index)

        # Active global events can add/subtract income
        for ev in self._events:
            if ev.active(tick_index) and ev.data.get("global"):
                if ev.type == "stimulus" and tick_index % 5 == 1:
                    add_income_to_all(db, Decimal("25.00"), tick_index)
                elif ev.type == "recession_fear" and tick_index % 10 == 1:
                    add_income_to_all(db, Decimal("5.00"), tick_index)

        # Phase 2: Consumer decisions
        consumers = db.query(Agent).filter(Agent.agent_type == "consumer").all()
        listings = get_listings(db)

        # Apply market event modifiers to listings
        self._apply_event_modifiers(listings, tick_index)
        # Apply category trend modifiers
        self._apply_trend_modifiers(listings)

        purchase_count = 0
        review_count = 0

        for consumer in consumers:
            if not listings or float(consumer.balance) <= 0:
                continue

            # Bankruptcy check for consumers
            if float(consumer.balance) < 5:
                cooldown = self._bankruptcy_cooldown.get(consumer.id, 0)
                if tick_index - cooldown > 30:
                    # Bailout
                    consumer.balance += Decimal("100.00")
                    self._bankruptcy_cooldown[consumer.id] = tick_index
                    logger.info(f"💰 Bailout for {consumer.name}: +$100")
                    db.commit()

            scored = []
            for item in listings:
                if item.get("_effective_stock", item["stock"]) <= 0:
                    continue
                utility = self._compute_utility(consumer, item)
                if utility > 0:
                    scored.append((utility, item))

            if not scored:
                continue

            scored.sort(key=lambda x: x[0], reverse=True)

            impulsiveness = float(consumer.impulsiveness or 0.5)
            if random.random() < impulsiveness:
                idx = min(random.randint(0, 2), len(scored) - 1)
            else:
                pool = scored[: min(10, len(scored))]
                weights = [s[0] for s in pool]
                total_w = sum(weights)
                if total_w <= 0:
                    continue
                probs = [w / total_w for w in weights]
                idx = random.choices(range(len(pool)), weights=probs, k=1)[0]

            _, chosen = scored[idx]

            risk = float(consumer.risk_tolerance or 0.5)
            if chosen["review_count"] == 0 and random.random() > risk:
                continue

            result = execute_buy(db, consumer.id, chosen["id"], tick_index)
            if result.success:
                purchase_count += 1
                # Track purchase history
                if consumer.id not in self._purchase_history:
                    self._purchase_history[consumer.id] = set()
                self._purchase_history[consumer.id].add(chosen["id"])

                review_chance = 0.3 + 0.4 * float(consumer.trend_alignment or 0.5)
                if random.random() < review_chance:
                    utility_score = scored[idx][0]
                    price_ratio = chosen["current_price"] / max(chosen["base_price"], 0.01)
                    base_rating = min(5, max(1, int(utility_score * 5) + 3))
                    if price_ratio > 1.5:
                        base_rating = max(1, base_rating - 1)
                    elif price_ratio < 0.7:
                        base_rating = min(5, base_rating + 1)

                    use_llm = random.random() < 0.05
                    await submit_review(
                        db, tick_index, consumer.id, chosen["id"],
                        base_rating, use_llm=use_llm,
                    )
                    review_count += 1

        # Phase 3: Merchant adaptation
        self._merchant_adaptation(db, tick_index)

        # Phase 4: Merchant bankruptcy check
        self._check_merchant_bankruptcy(db, tick_index)

        # Phase 5: Finalize
        capture_snapshot(db, tick_index)

        logger.info(
            f"Tick {tick_index}: {purchase_count} buys, {review_count} reviews, "
            f"{len(consumers)} consumers, {len(self._events)} active events"
        )

    # ── Social Graph ──
    def _build_social_graph(self):
        """Build sparse social influence network between agents."""
        self._social_graph = {}
        db = SessionLocal()
        try:
            agents = db.query(Agent).filter(Agent.agent_type == "consumer").all()
            agent_ids = [a.id for a in agents]
            for aid in agent_ids:
                num_peers = random.randint(3, 8)
                peers = random.sample([x for x in agent_ids if x != aid], min(num_peers, len(agent_ids) - 1))
                self._social_graph[aid] = peers
        finally:
            db.close()

    def _get_social_proof(self, agent_id: int, product_id: int) -> float:
        """How many of this agent's peers bought this product?"""
        peers = self._social_graph.get(agent_id, [])
        if not peers:
            return 0.0
        bought_count = sum(1 for pid in peers if product_id in self._purchase_history.get(pid, set()))
        return min(1.0, bought_count / max(1, len(peers)))

    # ── Market Events ──
    def _generate_event(self, tick: int):
        """Generate a random market event."""
        etype = random.choice(list(EVENT_TYPES.keys()))
        cfg = EVENT_TYPES[etype]
        category = random.choice(CATEGORIES) if not cfg.get("global") else "ALL"
        dur = random.randint(*cfg["duration"])
        desc = cfg["desc"].format(cat=category)

        event = MarketEvent(
            etype=etype,
            category=category,
            tick=tick,
            duration=dur,
            desc=desc,
            data={
                "stock_mult": cfg["stock_mult"],
                "price_mult": cfg["price_mult"],
                "global": cfg.get("global", False),
                "icon": cfg["icon"],
            },
        )
        self._events.append(event)
        self._event_history.append({
            "tick": tick,
            "type": etype,
            "category": category,
            "description": desc,
            "icon": cfg["icon"],
            "duration": dur,
        })
        logger.info(f"📢 EVENT @ Tick {tick}: {desc} (lasts {dur} ticks)")

    def _apply_event_modifiers(self, listings: list, tick: int):
        """Modify listing prices/stock based on active events."""
        for ev in self._events:
            if not ev.active(tick):
                continue
            dm = ev.data
            for item in listings:
                if dm.get("global") or item["category"] == ev.category:
                    item["_effective_stock"] = max(0, int(item["stock"] * dm["stock_mult"]))
                    item["_event_price"] = item["current_price"] * dm["price_mult"]

    # ── Category Trends ──
    def _drift_category_trends(self):
        """Random-walk category trend scores."""
        for cat in CATEGORIES:
            drift = random.uniform(-0.03, 0.03)
            self._category_trends[cat] = max(0.5, min(1.8, self._category_trends[cat] + drift))

    def _apply_trend_modifiers(self, listings: list):
        """Boost/cut utility based on category trends."""
        for item in listings:
            trend = self._category_trends.get(item["category"], 1.0)
            item["_trend_mult"] = trend

    # ── Utility Computation ──
    def _compute_utility(self, agent: Agent, item: dict) -> float:
        if agent.agent_type != "consumer":
            return 0.0

        sp = float(agent.price_sensitivity or 0.5)
        im = float(agent.impulsiveness or 0.5)
        rt = float(agent.risk_tolerance or 0.5)
        lb = float(agent.brand_loyalty or 0.5)
        at = float(agent.trend_alignment or 0.5)

        # Use event-modified price if present
        price = item.get("_event_price", item["current_price"])
        base_price = item["base_price"]
        avg_rating = item["avg_rating"]
        review_count = item["review_count"]
        velocity = item["sales_velocity"]

        value_ratio = base_price / max(price, 0.01)
        price_factor = value_ratio ** (sp * 3)
        impul_bonus = 1.0 + im * 0.15

        risk_factor = 1.0
        if review_count < 2:
            risk_factor = 0.3 + rt * 0.7

        loyalty_factor = 1.0
        if velocity > 50:
            loyalty_factor = 1.0 + lb * 0.2

        trend_factor = 1.0
        if velocity > 20 or avg_rating >= 4.0:
            trend_factor = 1.0 + at * 0.25

        # Category trend multiplier
        cat_trend = item.get("_trend_mult", 1.0)
        trend_factor *= (0.8 + cat_trend * 0.4)

        # Social proof bonus
        social_proof = self._get_social_proof(agent.id, item["id"])
        social_bonus = 1.0 + social_proof * at * 0.3

        review_bonus = 1.0 + (avg_rating - 3.0) * 0.1

        utility = (
            value_ratio
            * price_factor
            * impul_bonus
            * risk_factor
            * loyalty_factor
            * trend_factor
            * social_bonus
            * review_bonus
        )

        if float(agent.balance) < price:
            return 0.0

        return max(0.0, utility)

    # ── Merchant Adaptation ──
    def _merchant_adaptation(self, db: Session, tick_index: int):
        merchants = db.query(Agent).filter(Agent.agent_type == "merchant").all()
        for merchant in merchants:
            products = db.query(Product).filter(Product.merchant_id == merchant.id).all()
            for p in products:
                if p.stock <= 0:
                    continue

                strategy = merchant.pricing_strategy or "adaptive"
                velocity = p.sales_velocity or 1

                if strategy == "aggressive":
                    if velocity > 10:
                        p.current_price = p.current_price * Decimal("1.06")
                    elif velocity < 3:
                        p.current_price = p.current_price * Decimal("0.96")
                    else:
                        p.current_price = p.current_price * Decimal("1.01")
                elif strategy == "conservative":
                    if velocity > 15:
                        p.current_price = p.current_price * Decimal("1.02")
                    elif velocity < 3:
                        p.current_price = p.current_price * Decimal("0.99")
                elif strategy == "loss_leader":
                    # Keep prices low to attract volume
                    if velocity > 20:
                        p.current_price = p.current_price * Decimal("1.01")
                    else:
                        p.current_price = p.current_price * Decimal("0.97")
                elif strategy == "premium":
                    # Always trend up, quality over volume
                    if velocity > 5:
                        p.current_price = p.current_price * Decimal("1.04")
                    else:
                        p.current_price = p.current_price * Decimal("1.01")
                else:  # adaptive
                    adj = Decimal("1.0") + Decimal("0.005") * (velocity - 5)
                    adj = max(Decimal("0.85"), min(Decimal("2.0"), adj))
                    p.current_price = p.current_price * adj

                floor = p.base_price * Decimal("0.2")
                cap = p.base_price * Decimal("5.0")
                p.current_price = max(floor, min(cap, p.current_price))
                p.current_price = p.current_price.quantize(Decimal("0.01"))

            db.commit()

    def _check_merchant_bankruptcy(self, db: Session, tick_index: int):
        """Restructure bankrupt merchants."""
        merchants = db.query(Agent).filter(Agent.agent_type == "merchant").all()
        for m in merchants:
            if float(m.balance) < -500:
                cooldown = self._bankruptcy_cooldown.get(m.id, 0)
                if tick_index - cooldown > 20:
                    m.balance = Decimal("3000.00")
                    self._bankruptcy_cooldown[m.id] = tick_index
                    # Clear old stock
                    products = db.query(Product).filter(Product.merchant_id == m.id).all()
                    for p in products:
                        p.sales_velocity = max(0, p.sales_velocity // 2)
                    db.commit()
                    self._event_history.append({
                        "tick": tick_index,
                        "type": "bankruptcy",
                        "category": m.name,
                        "description": f"🏚️ {m.name} restructured! Balance reset to $3000.",
                        "icon": "🏚️",
                        "duration": 1,
                    })
                    logger.info(f"🏚️ Merchant {m.name} bankrupt, restructured")


# Singleton
engine = SimulationEngine()
