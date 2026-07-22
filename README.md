# AMMS — Autonomous Multi-Agent Market Simulator

A tick-based economic sandbox simulating a marketplace with 50 AI-driven consumer agents and 5 merchant agents. Features real-time WebSocket telemetry, LLM-generated product reviews, and rich analytics.

<img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python"> <img src="https://img.shields.io/badge/fastapi-0.100+-green" alt="FastAPI"> <img src="https://img.shields.io/badge/chart.js-4.x-pink" alt="Chart.js">

---

## Overview

AMMS models a dynamic economy where autonomous agents buy, sell, review, and compete. Each tick, consumers evaluate products through a **5-trait personality heuristic** (price sensitivity, impulsiveness, risk tolerance, brand loyalty, trend alignment), while merchants adapt strategies in real time.

## Key Features

### Core Simulation
- **50 consumer agents** — each with unique personality traits, budget, and social network
- **5 merchant agents** — adaptive pricing strategies: `rational`, `aggressive`, `conservative`, `loss_leader`, `premium`
- **20 products** across 5 categories (Electronics, Food, Fashion, Home, Entertainment)
- **Tick-based engine** — per-tick decision loop with ACID transactions

### v2 Upgrades
- **Market Events** — 6 event types (supply shock, demand surge, price crash, innovation, recession fear, stimulus) trigger randomly ~8%/tick
- **Social Influence Network** — each consumer connected to 3–8 peers; social proof boosts purchase utility up to 30%
- **Category Trend Cycles** — 5 categories drift on random walks (0.5–1.8× multiplier)
- **Bankruptcy Bailout** — consumers below $5 get $100 rescue every 30 ticks
- **LLM Reviews** — AI-generated product reviews via DeepSeek → Qwen → Hunyuan fallback chain
- **5 Simulation Presets** — Default, Extreme Inequality, Price War, Viral Market, Recession

### Analytics
- Gini coefficient & wealth distribution (decile breakdown)
- Price index tracking & transaction velocity
- Category sales/stock/price breakdown with doughnut charts
- Richest/poorest agent leaderboard
- Real-time tick snapshots and historical trends

### Dashboard
- **4 tabs** — Overview, Analytics, Agents, Events
- **Real-time WebSocket** — live transaction feed, auto-updating charts
- **Collapsible panels** — reorder and collapse sections to customize the view
- **Agent search & sort** — filter consumers by wealth, personality, or name
- **Event timeline** — color-coded market events with duration indicators
- **Preset selector** — one-click economy configuration

---

## Quick Start

```bash
git clone https://github.com/simul49/Autonomous-Multi-Agent-Market-Simulator.git
cd Autonomous-Multi-Agent-Market-Simulator/backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open **http://127.0.0.1:8000/app/** — the database auto-seeds with the default preset on first run.

### With MySQL (optional)

```bash
# Set environment variables
DB_ENGINE=mysql
DB_NAME=MarketSimulator
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/simulation/start` | Start auto-loop |
| POST | `/simulation/stop` | Pause |
| POST | `/simulation/step` | Single tick |
| POST | `/simulation/reset` | Reset all data |
| POST | `/simulation/presets/{name}` | Apply a market preset |
| GET | `/simulation/status` | Current state |
| GET | `/analytics/dashboard` | Full telemetry |
| GET | `/analytics/wealth` | Wealth distribution |
| GET | `/analytics/categories` | Category breakdown |
| GET | `/agents/consumers` | Consumer list |
| GET | `/agents/merchants` | Merchant list |
| GET | `/market/listings` | Active products |
| GET | `/market/events` | Market event timeline |
| WS | `/ws` | Real-time stream |

---

## Architecture

```
backend/
├── main.py              # FastAPI app, lifespan, CORS
├── init_db.py           # Database seeding (MySQL)
├── models.py            # SQLAlchemy models
├── database.py          # DB connection (MySQL/SQLite)
├── routers/
│   ├── simulation.py    # Simulation control & presets
│   ├── analytics.py     # Dashboard, charts, wealth
│   ├── agents.py        # Consumer & merchant listing
│   └── market.py        # Products, transactions, events
├── services/
│   ├── simulation_service.py  # Tick engine
│   ├── llm_service.py         # Multi-provider LLM
│   ├── market_service.py      # Transaction logic
│   ├── analytics_service.py   # Gini, snapshots
│   └── ws_manager.py          # WebSocket manager
├── requirements.txt
└── static/ (served via frontend/)

frontend/
├── index.html           # Dashboard UI
├── styles.css           # Glassmorphism theme
└── app.js               # Charts, WebSocket, panels
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy |
| Database | SQLite (default) / MySQL 8.0 |
| Frontend | Vanilla JS, Chart.js 4.x, WebSocket |
| AI / LLM | OpenAI-compatible API (DeepSeek, Qwen, Hunyuan) |

---

## License

MIT
