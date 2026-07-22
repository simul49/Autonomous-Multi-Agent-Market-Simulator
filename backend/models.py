"""SQLAlchemy ORM models matching the PRD entity schema."""
from sqlalchemy import (
    Column, Integer, String, DECIMAL,
    Text, TIMESTAMP, ForeignKey, Index, func,
)
from database import Base

CATEGORIES = ["Electronics", "Clothing", "Food", "Books", "Home"]


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    agent_type = Column(String(16), nullable=False, default="consumer")  # consumer | merchant
    balance = Column(DECIMAL(12, 2), nullable=False, default=0.00)

    # Personality vector (consumer only, NULL for merchants)
    price_sensitivity = Column(DECIMAL(3, 2), nullable=True)
    impulsiveness = Column(DECIMAL(3, 2), nullable=True)
    risk_tolerance = Column(DECIMAL(3, 2), nullable=True)
    brand_loyalty = Column(DECIMAL(3, 2), nullable=True)
    trend_alignment = Column(DECIMAL(3, 2), nullable=True)

    # Merchant-specific
    pricing_strategy = Column(String(32), nullable=True)  # conservative | aggressive | adaptive
    last_interaction_tick = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_agent_type", "agent_type"),
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    merchant_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    category = Column(String(128), nullable=False)
    base_price = Column(DECIMAL(12, 2), nullable=False)
    current_price = Column(DECIMAL(12, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=100)
    sales_velocity = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_merchant_category", "merchant_id", "category"),
        Index("idx_category", "category"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tick_index = Column(Integer, nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    purchase_price = Column(DECIMAL(12, 2), nullable=False)
    timestamp = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_txn_agent_product_tick", "agent_id", "product_id", "tick_index"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tick_index = Column(Integer, nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    rating_stars = Column(Integer, nullable=False)
    review_text = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_rev_agent_product_tick", "agent_id", "product_id", "tick_index"),
    )


class TickSnapshot(Base):
    """Macro-state record captured at the end of each tick."""
    __tablename__ = "tick_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tick_index = Column(Integer, nullable=False, unique=True, index=True)
    total_transactions = Column(Integer, nullable=False, default=0)
    total_volume = Column(DECIMAL(14, 2), nullable=False, default=0.00)
    gini_coefficient = Column(DECIMAL(5, 4), nullable=True)
    avg_price_index = Column(DECIMAL(10, 4), nullable=True)
    active_consumers = Column(Integer, nullable=False, default=0)
    timestamp = Column(TIMESTAMP, server_default=func.now())
