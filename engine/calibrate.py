"""
패턴별 익절(TP)/손절(SL)·예상수익률 자동 산출.
아이디어: "패턴을 찾는 것"에서 그치지 않고, 그 패턴이 과거(학습구간)에
진입 이후 실제로 얼마나 움직였는지를 보고 각 패턴에 맞는 목표/손절과
'예상 수익률'을 정한다.

- MFE(최대 유리 이동) / MAE(최대 불리 이동)을 등장마다 측정
- 방향: 관찰구간 평균 수익률의 부호 (숏 허용 시 음수면 숏)
- TP = 그 방향 MFE의 중앙값, SL = 그 방향 MAE의 중앙값
- 예상수익률 = 관찰구간 평균 이동폭(방향 반영)
"""
from __future__ import annotations

import numpy as np

TP_MIN, TP_MAX = 0.002, 0.10
SL_MIN, SL_MAX = 0.002, 0.10


def _clamp(x: float, lo: float, hi: float) -> float:
    return float(min(max(x, lo), hi))


def calibrate(
    entries: list[int],
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    horizon: int,
    allow_short: bool,
) -> dict:
    """entries(진입 캔들 인덱스)들의 이후 움직임으로 방향·TP·SL·예상수익을 산출."""
    n = len(close)
    frs, mfe_long, mae_long, mfe_short, mae_short = [], [], [], [], []
    for e in entries:
        end = min(e + horizon, n - 1)
        if end <= e:
            continue
        entry = close[e]
        hi = float(high[e + 1:end + 1].max())
        lo = float(low[e + 1:end + 1].min())
        frs.append(close[end] / entry - 1.0)
        up = max(hi / entry - 1.0, 0.0)      # 위로 간 최대폭
        down = max(1.0 - lo / entry, 0.0)    # 아래로 간 최대폭
        mfe_long.append(up);  mae_long.append(down)
        mfe_short.append(down); mae_short.append(up)  # 숏은 반대

    if not frs:
        return {"direction": "long", "tp": TP_MIN, "sl": SL_MIN, "expected_return": 0.0}

    mean_fr = float(np.mean(frs))
    if allow_short and mean_fr < 0:
        direction = "short"
        tp = float(np.median(mfe_short)); sl = float(np.median(mae_short))
        expected = abs(mean_fr)
    else:
        direction = "long"
        tp = float(np.median(mfe_long)); sl = float(np.median(mae_long))
        expected = mean_fr

    return {
        "direction": direction,
        "tp": _clamp(tp, TP_MIN, TP_MAX),
        "sl": _clamp(sl, SL_MIN, SL_MAX),
        "expected_return": float(expected),
    }
