"""Pydantic request/response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


# ── Agent ──
class AgentPersonality(BaseModel):
    price_sensitivity: float = Field(ge=0.0, le=1.0)
    impulsiveness: float = Field(ge=0.0, le=1.0)
    risk_tolerance: float = Field(ge=0.0, le=1.0)
    brand_loyalty: float = Field(ge=0.0, le=1.0)
    trend_alignment: float = Field(ge=0.0, le=1.0)


class AgentCreate(BaseModel):
    name: str
    agent_type: str = "consumer"
    balance: float = 500.00
    personality: Optional[AgentPersonality] = None
    pricing_strategy: Optional[str] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    agent_type: str
    balance: float
    price_sensitivity: Optional[float] = None
    impulsiveness: Optional[float] = None
    risk_tolerance: Optional[float] = None
    brand_loyalty: Optional[float] = None
    trend_alignment: Optional[float] = None
    pricing_strategy: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Product ──
class ProductCreate(BaseModel):
    name: str
    merchant_id: int
    category: str
    base_price: float
    stock: int = 100


class ProductResponse(BaseModel):
    id: int
    name: str
    merchant_id: int
    category: str
    base_price: float
    current_price: float
    stock: int
    sales_velocity: int

    model_config = {"from_attributes": True}


# ── Market ──
class BuyRequest(BaseModel):
    agent_id: int
    product_id: int


class BuyResponse(BaseModel):
    success: bool
    message: str
    transaction_id: Optional[int] = None
    purchase_price: Optional[float] = None


class ReviewRequest(BaseModel):
    agent_id: int
    product_id: int
    rating_stars: int = Field(ge=1, le=5)
    review_text: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    tick_index: int
    agent_id: int
    product_id: int
    rating_stars: int
    review_text: Optional[str] = None
    timestamp: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Simulation ──
class SimulationConfig(BaseModel):
    agent_count: int = Field(default=50, ge=1, le=500)
    product_count: int = Field(default=20, ge=1, le=200)
    merchant_count: int = Field(default=5, ge=1, le=50)
    income_per_tick: float = Field(default=15.0, ge=0)
    income_interval_ticks: int = Field(default=10, ge=1)


class SimulationStatus(BaseModel):
    running: bool
    tick: int
    agents_count: int
    products_count: int
    total_transactions: int
    current_gini: Optional[float] = None


# ── Analytics ──
class MacroMetrics(BaseModel):
    tick_index: int
    total_transactions: int
    total_volume: float
    gini_coefficient: Optional[float] = None
    avg_price_index: Optional[float] = None
    active_consumers: int


class DashboardSummary(BaseModel):
    current_tick: int
    total_agents: int
    total_products: int
    total_transactions: int
    total_volume: float
    current_gini: Optional[float] = None
    avg_price_index: Optional[float] = None
    price_trend: List[dict]
    gini_trend: List[dict]
    volume_trend: List[dict]
    top_products: List[dict]
    recent_reviews: List[dict]
