@echo off
echo ============================================
echo  AMMS - Market Simulator Setup & Launch
echo ============================================
echo.

cd /d "%~dp0backend"

echo [1/3] Installing Python dependencies...
pip install -r requirements.txt --quiet

echo [2/3] Initializing database...
python init_db.py

echo [3/3] Starting server...
echo.
echo Dashboard: http://127.0.0.1:8000/app/
echo API Docs: http://127.0.0.1:8000/docs
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
