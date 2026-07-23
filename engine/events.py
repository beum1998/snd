"""
②-v1.5 이벤트 라벨링 모듈 — "급등/급락"을 트리플 배리어로 정의한다.

시점 e의 종가에서 진입했다고 가정하고, 이후 K캔들 안에:
  급등(up):   고가가 +tp_mult×ATR 에 먼저 도달 (그 전에 저가가 -sl_mult×ATR 닿으면 무효)
  급락(down): 저가가 -tp_mult×ATR 에 먼저 도달 (그 전에 고가가 +sl_mult×ATR 닿으면 무효)

ATR 배수 기준이라 변동성 큰 장세/조용한 장세에서 공평하게 이벤트를 잡는다.
같은 캔들에서 익절·손절 배리어를 둘 다 건드리면 보수적으로 '무효' 처리(simulate의 SL 우선과 동일).
이 정의는 처음에 정하고 고정한다 — 결과를 보고 바꾸면 과최적화(기획서 핵심 철학 3번).
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """단순이동평균 ATR. 앞쪽 period-1개는 NaN(판정 불가)."""
    n = len(close)
    tr = np.empty(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    prev = close[:-1]
    tr[1:] = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - prev), np.abs(low[1:] - prev)))
    out = np.full(n, np.nan)
    c = np.cumsum(tr)
    out[period - 1:] = (c[period - 1:] - np.concatenate(([0.0], c[:-period]))) / period
    return out


def _first_hit(hit: np.ndarray, k: int) -> np.ndarray:
    """(m, k) bool 행렬 → 행마다 처음 True인 열 인덱스 (없으면 k)."""
    return np.where(hit.any(axis=1), hit.argmax(axis=1), k)


def label(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, atr_arr: np.ndarray,
    k: int, tp_mult: float, sl_mult: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    모든 시점 e에 대해 (up, down, valid)를 반환.
    valid[e]=True는 ATR이 있고 판정 구간 K캔들이 데이터 안에 온전히 있는 경우.
    up/down 판정은 e+1 ~ e+K 캔들의 고가/저가로 한다 (e 캔들 자체는 미포함 → 누수 없음).
    """
    n = len(close)
    up = np.zeros(n, dtype=bool)
    down = np.zeros(n, dtype=bool)
    valid = np.zeros(n, dtype=bool)
    if n < k + 2:
        return up, down, valid

    m = n - 1 - k                      # 판정 가능한 마지막 시작 인덱스 e = m-1... 정확히는 e <= n-1-k
    if m <= 0:
        return up, down, valid
    e_idx = np.arange(m)               # e = 0 .. n-2-k  (e+1+k <= n-1 보장 위해 아래 슬라이스 사용)

    # e+1부터 K개 캔들의 고가/저가 창: 행 e ↔ high[e+1 : e+1+k]
    hi_win = sliding_window_view(high, k)[1:m + 1]   # (m, k)
    lo_win = sliding_window_view(low, k)[1:m + 1]

    entry = close[e_idx]
    a = atr_arr[e_idx]
    ok = np.isfinite(a) & (a > 0)

    up_bar_tp = entry + tp_mult * a    # 급등 판정: 익절 배리어
    up_bar_sl = entry - sl_mult * a    #            손절 배리어
    dn_bar_tp = entry - tp_mult * a    # 급락 판정(대칭)
    dn_bar_sl = entry + sl_mult * a

    # 급등: TP가 SL보다 '엄격히' 먼저 (같은 캔들이면 보수적으로 무효)
    t_tp = _first_hit(hi_win >= up_bar_tp[:, None], k)
    t_sl = _first_hit(lo_win <= up_bar_sl[:, None], k)
    up[:m] = ok & (t_tp < k) & (t_tp < t_sl)

    # 급락(대칭)
    t_tp = _first_hit(lo_win <= dn_bar_tp[:, None], k)
    t_sl = _first_hit(hi_win >= dn_bar_sl[:, None], k)
    down[:m] = ok & (t_tp < k) & (t_tp < t_sl)

    valid[:m] = ok
    return up, down, valid


def merge_starts(indices: np.ndarray | list[int], gap: int) -> list[int]:
    """겹치는 이벤트 시작점 병합: 앞선 시작점에서 gap캔들 이내는 같은 랠리로 보고 버린다."""
    out: list[int] = []
    last = -gap - 1
    for i in sorted(int(x) for x in indices):
        if i - last >= gap:
            out.append(i)
            last = i
    return out
