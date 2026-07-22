"""
Database initialization script.
Creates all tables and seeds initial data (merchants, products, consumers).
Run: python init_db.py
"""
import random
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import engine, SessionLocal, Base
from config import settings

# Create tables
print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Tables created.")

db = SessionLocal()
try:
    from models import Agent
    existing = db.query(Agent).count()
    if existing > 0:
        print(f"Database already has {existing} agents. Skipping seed.")
        sys.exit(0)

    from services.agent_service import (
        create_consumer, create_merchant, NAMES_POOL,
    )
    from models import Product
    from decimal import Decimal

    print(f"Seeding {settings.DEFAULT_MERCHANT_COUNT} merchants...")
    merchant_names = ["MegaMart", "EcoShop", "PrimeStore", "ValueKing", "TrendHub"]
    categories = ["Electronics", "Clothing", "Food", "Books", "Home"]
    merchant_ids = []

    for i in range(settings.DEFAULT_MERCHANT_COUNT):
        name = merchant_names[i % len(merchant_names)]
        m = create_merchant(db, name, random.choice(["adaptive", "aggressive", "conservative"]))
        merchant_ids.append(m.id)

    print(f"Seeding {settings.DEFAULT_PRODUCT_COUNT} products...")
    product_names = [
        "Wireless Earbuds", "USB-C Hub", "Mechanical Keyboard", "4K Monitor",
        "Bluetooth Speaker", "Smart Watch", "Tablet Stand", "Webcam Pro",
        "Denim Jacket", "Running Shoes", "Cotton T-Shirt", "Winter Coat",
        "Sunglasses", "Leather Belt", "Wool Scarf", "Casual Sneakers",
        "Organic Coffee", "Protein Bars", "Green Tea Box", "Dark Chocolate",
        "Trail Mix Pack", "Instant Ramen Set", "Olive Oil Bottle", "Dried Mango",
        "Python Cookbook", "Sci-Fi Novel", "Self-Help Guide", "History Epic",
        "Throwsilk Blanket", "Scented Candle", "Wall Art Print", "Desk Lamp",
        "Plant Pot Set", "Yoga Mat", "Water Bottle", "Notebook Set",
    ]

    for i in range(settings.DEFAULT_PRODUCT_COUNT):
        p = Product(
            name=product_names[i % len(product_names)] + f" #{i+1}",
            merchant_id=random.choice(merchant_ids),
            category=random.choice(categories),
            base_price=Decimal(str(round(random.uniform(5, 200), 2))),
            current_price=Decimal(str(round(random.uniform(5, 200), 2))),
            stock=random.randint(50, 200),
        )
        p.current_price = p.base_price  # Start at base price
        db.add(p)

    print(f"Seeding {settings.DEFAULT_AGENT_COUNT} consumers...")
    used_names = set()
    for i in range(settings.DEFAULT_AGENT_COUNT):
        name = NAMES_POOL[i % len(NAMES_POOL)]
        suffix = 1
        while name in used_names:
            name = f"{NAMES_POOL[i % len(NAMES_POOL)]}-{suffix}"
            suffix += 1
        used_names.add(name)
        create_consumer(db, name)

    db.commit()
    print(f"Seed complete: {settings.DEFAULT_MERCHANT_COUNT} merchants, "
          f"{settings.DEFAULT_PRODUCT_COUNT} products, "
          f"{settings.DEFAULT_AGENT_COUNT} consumers.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()
