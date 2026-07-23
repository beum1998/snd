"""
FastAPI 서버 — Python 엔진을 HTTP로 감싼다.
실행: .venv/Scripts/python.exe -m uvicorn api.server:app --port 8000 --reload

엔드포인트:
  GET  /api/health    상태 확인
  GET  /api/defaults  기본 파라미터 + 선택지(종목/분봉)
  POST /api/backtest  파라미터+패턴별 오버라이드로 백테스트 실행 → 결과 JSON
"""
from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engine import service

app = FastAPI(title="Crypto Pattern Bot API")

# 개발 중 Next.js(3000)에서의 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "4h"]
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT", "DOGE/USDT"]


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/defaults")
def defaults() -> dict:
    d = service._defaults()
    d.pop("overrides", None)
    return {"defaults": d, "timeframes": TIMEFRAMES, "symbols": SYMBOLS}


@app.post("/api/backtest")
def backtest(payload: dict[str, Any] = Body(default_factory=dict)) -> dict:
    try:
        return service.run(payload)
    except Exception as e:  # 프런트에 에러를 그대로 보여주기 위함
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
