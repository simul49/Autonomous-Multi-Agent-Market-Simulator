# AMMS - Autonomous Multi-Agent Market Simulator

**Live Demo**: [Dashboard](http://d209267f428c46c9968ea65c8faa147b.codebuddy.cloudstudio.run/app/) | [API Docs](http://d209267f428c46c9968ea65c8faa147b.codebuddy.cloudstudio.run/docs)

A tick-based economic sandbox with 50 AI consumer agents, 5 merchant agents, real-time WebSocket telemetry, and multi-provider LLM review generation.

## Deployed on Cloud Studio

| URL | Description |
|-----|-------------|
| `/app/` | Real-time dashboard with charts, agent grid, and simulation controls |
| `/docs` | Interactive Swagger API documentation |
| `/` | API health check |

## Quick Start (Local)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/app/

### Local MySQL Setup
```bash
# Set environment variables
DB_ENGINE=mysql
DB_NAME=MarketSimulator
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306

python init_db.py   # Create tables & seed data
```

## Architecture

- **Backend**: Python FastAPI + SQLAlchemy (MySQL/SQLite)
- **Frontend**: Vanilla JS + Chart.js (WebSocket real-time)
- **LLM Providers**: DeepSeek → Qwen → Hunyuan (auto-fallback)
- **Analytics**: Gini coefficient, price index, transaction velocity

## Simulation Engine

Each tick:
1. Periodic income distribution (every 10 ticks)
2. All 50 consumers evaluate products using 5-trait personality heuristic
3. Purchases via ACID transactions (SELECT FOR UPDATE)
4. LLM-generated reviews (~5% chance)
5. Merchant price adjustment (adaptive/aggressive/conservative)
6. Macro-state snapshot (Gini, price index)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/simulation/start` | Start auto-loop |
| POST | `/simulation/stop` | Pause simulation |
| POST | `/simulation/step` | Single tick |
| POST | `/simulation/reset` | Reset all data |
| GET | `/simulation/status` | Current state |
| GET | `/market/listings` | All active products |
| POST | `/market/buy` | Manual purchase |
| GET | `/analytics/dashboard` | Full telemetry |
| GET | `/agents/consumers` | Consumer list |
| WS | `/ws` | Real-time WebSocket stream |
