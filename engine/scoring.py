"""
③ 채점 모듈
핵심 원칙(기획서 1번): "반복되는 패턴을 찾는 것"만으로는 못 번다.
각 패턴이 과거 등장했던 모든 순간의 '이후 결과'를 통계로 매기고,
일관되게 수익 나는 패턴만 골라낸다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .patterns import Motif


def round_trip_cost(fee: float, slippage: float) -> float:
    """진입+청산 왕복 비용률 (근사)."""
    return 2 * (fee + slippage)


def forward_return(
    close: np.ndarray,
    entry_idx: int,
    horizon: int,
    cost: float,
) -> float | None:
    """
    entry_idx(패턴이 끝난 캔들)에서 매수 → horizon 캔들 뒤 매도했을 때
    수수료·슬리피지 차감 순수익률. 데이터가 모자라면 None.
    """
    exit_idx = entry_idx + horizon
    if exit_idx >= len(close):
        return None
    gross = close[exit_idx] / close[entry_idx] - 1.0
    return gross - cost


@dataclass
class Score:
    motif: Motif
    n: int              # 결과를 볼 수 있었던 등장 횟수
    win_rate: float     # 순수익 > 0 비율
    avg_return: float   # 평균 순수익률
    median_return: float
    returns: list[float]

    def passes(self, min_win_rate: float, min_avg_return: float, min_n: int) -> bool:
        return (
            self.n >= min_n
            and self.win_rate >= min_win_rate
            and self.avg_return >= min_avg_return
        )


def score_motif(
    motif: Motif,
    close: np.ndarray,
    window: int,
    horizon: int,
    cost: float,
) -> Score:
    rets: list[float] = []
    for start in motif.occurrences:
        entry_idx = start + window - 1  # 패턴의 마지막 캔들 = 진입 시점
        r = forward_return(close, entry_idx, horizon, cost)
        if r is not None:
            rets.append(r)

    arr = np.array(rets) if rets else np.array([0.0])
    return Score(
        motif=motif,
        n=len(rets),
        win_rate=float((arr > 0).mean()) if rets else 0.0,
        avg_return=float(arr.mean()) if rets else 0.0,
        median_return=float(np.median(arr)) if rets else 0.0,
        returns=rets,
    )


def score_and_select(
    motifs: list[Motif],
    close: np.ndarray,
    window: int,
    horizon: int,
    cost: float,
    min_win_rate: float,
    min_avg_return: float,
    min_n: int,
) -> tuple[list[Score], list[Score]]:
    """전체 채점 결과와, 기준을 통과한 '선별된' 패턴을 함께 반환."""
    scores = [score_motif(m, close, window, horizon, cost) for m in motifs]
    scores.sort(key=lambda s: s.avg_return, reverse=True)
    selected = [s for s in scores if s.passes(min_win_rate, min_avg_return, min_n)]
    return scores, selected
