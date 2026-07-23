"""
매매 시뮬레이션 (패턴별 익절/손절 청산, 롱/숏 지원)
- 진입: 패턴이 끝난 캔들의 종가에서 롱(매수) 또는 숏(매도)
- 청산: 익절(TP) 또는 손절(SL) 도달 시. (강제 시간청산 없음 — 데이터 끝나면 마지막 종가)
- 보수적 가정: 한 캔들에서 TP·SL 둘 다 닿으면 SL 우선(최악)
- 한 흐름 안에서는 포지션 보유 중 새 진입 안 함(비중복)

롱: 가격이 오르면 이익 (TP=고가가 목표 도달, SL=저가가 손절 도달)
숏: 가격이 내리면 이익 (TP=저가가 목표 도달, SL=고가가 손절 도달)
"""
from __future__ import annotations

import numpy as np


def resolve_exit(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    e: int, direction: str, tp: float, sl: float,
) -> tuple[int, float, str]:
    """진입 e 이후 TP/SL 도달 지점을 찾는다. 없으면 데이터 끝 종가."""
    n = len(close)
    entry = close[e]
    short = direction == "short"
    tp_price = entry * (1.0 - tp) if short else entry * (1.0 + tp)
    sl_price = entry * (1.0 + sl) if short else entry * (1.0 - sl)
    for j in range(e + 1, n):
        if short:
            if high[j] >= sl_price:
                return j, sl_price, "SL"
            if low[j] <= tp_price:
                return j, tp_price, "TP"
        else:
            if low[j] <= sl_price:
                return j, sl_price, "SL"
            if high[j] >= tp_price:
                return j, tp_price, "TP"
    return n - 1, float(close[n - 1]), "END"


def trade_return(entry_price: float, exit_price: float, direction: str, cost: float) -> float:
    move = exit_price / entry_price - 1.0
    return float((-move if direction == "short" else move) - cost)


def simulate(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    entries: list[int], tp: float, sl: float, cost: float,
    index_offset: int = 0, direction: str = "long",
) -> list[dict]:
    """entries(로컬 인덱스) → 거래 목록. 보유 중이면 새 진입 스킵(비중복)."""
    n = len(close)
    trades: list[dict] = []
    next_free = -1
    for e in sorted(entries):
        if e < next_free or e >= n - 1:
            continue
        exit_idx, exit_price, reason = resolve_exit(high, low, close, e, direction, tp, sl)
        ret = trade_return(close[e], exit_price, direction, cost)
        trades.append({
            "entry_idx": int(e + index_offset),
            "exit_idx": int(exit_idx + index_offset),
            "ret": ret, "reason": reason, "direction": direction,
        })
        next_free = exit_idx
    return trades


def simulate_per_entry(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    entry_specs: list[tuple[int, str, float, float]],  # (진입 인덱스, 방향, tp, sl)
    cost: float, index_offset: int = 0,
) -> list[dict]:
    """진입마다 TP/SL이 다른(예: ATR 배수) 시뮬레이션. 비중복은 simulate()와 동일."""
    n = len(close)
    trades: list[dict] = []
    next_free = -1
    for e, direction, tp, sl in sorted(entry_specs):
        if e < next_free or e >= n - 1:
            continue
        exit_idx, exit_price, reason = resolve_exit(high, low, close, e, direction, tp, sl)
        ret = trade_return(close[e], exit_price, direction, cost)
        trades.append({
            "entry_idx": int(e + index_offset),
            "exit_idx": int(exit_idx + index_offset),
            "ret": ret, "reason": reason, "direction": direction,
        })
        next_free = exit_idx
    return trades


def stats(trades: list[dict]) -> dict:
    if not trades:
        return {"n_trades": 0, "win_rate": 0.0, "avg_return": 0.0, "total_return": 0.0}
    rets = np.array([t["ret"] for t in trades], dtype=float)
    return {
        "n_trades": len(trades),
        "win_rate": float((rets > 0).mean()),
        "avg_return": float(rets.mean()),
        "total_return": float(np.prod(1.0 + rets) - 1.0),
    }
