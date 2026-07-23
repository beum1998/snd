"""
① 데이터 수집 모듈
바이낸스에서 과거 분봉(OHLCV)을 받아 로컬 parquet로 캐시한다.
- API 키 불필요 (공개 데이터)
- 한 번 받으면 재사용. 매번 API 호출 안 함.
"""
from __future__ import annotations

import ccxt
import pandas as pd

from . import config


def _cache_path(symbol: str, timeframe: str) -> "config.Path":
    safe = symbol.replace("/", "").replace(":", "")
    return config.DATA_DIR / f"{safe}_{timeframe}.parquet"


def fetch_ohlcv(symbol: str, timeframe: str, candles: int) -> pd.DataFrame:
    """바이낸스에서 최근 `candles`개의 분봉을 받아온다. (페이지네이션)"""
    exchange = ccxt.binance({"enableRateLimit": True})
    tf_ms = exchange.parse_timeframe(timeframe) * 1000
    now = exchange.milliseconds()
    since = now - candles * tf_ms

    rows: list[list] = []
    limit = 1000  # 바이낸스 요청당 최대치
    while since < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not batch:
            break
        rows += batch
        since = batch[-1][0] + tf_ms
        if len(batch) < limit:
            break

    df = pd.DataFrame(
        rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    ).drop_duplicates(subset="timestamp")
    df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("time").drop(columns="timestamp").sort_index()
    return df.astype(float)


def load(
    symbol: str = config.SYMBOL,
    timeframe: str = config.TIMEFRAME,
    candles: int = config.CANDLES,
    force_refresh: bool = config.FORCE_REFRESH,
) -> pd.DataFrame:
    """캐시가 있으면 읽고, 없거나 force_refresh면 새로 받아 저장한다."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, timeframe)

    if path.exists() and not force_refresh:
        df = pd.read_parquet(path)
        if len(df) >= candles * 0.9:  # 캐시가 충분하면 그대로 사용
            print(f"[data] 캐시 사용: {path.name} ({len(df)}개 캔들)")
            return df.tail(candles)

    print(f"[data] 바이낸스에서 {symbol} {timeframe} {candles}개 받는 중...")
    df = fetch_ohlcv(symbol, timeframe, candles)
    df.to_parquet(path)
    print(f"[data] 저장 완료: {path.name} ({len(df)}개 캔들)")
    return df


if __name__ == "__main__":
    d = load()
    print(d.tail())
