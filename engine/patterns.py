"""
② 패턴 발견 모듈 (캔들/OHLC 다변량 지원)
- 종가 하나만 보면 사실상 추세선. 시가·고가·저가·종가 4채널을 함께 보면 캔들 '모양'을 본다.
- 채널별 z-정규화 거리(stumpy.mass)의 합으로 "닮음"을 정의 → 다변량 모티프 발견/매칭.
- 학습(training) 없음. 계산만. 눈으로 검증 가능.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import stumpy

warnings.filterwarnings("ignore", category=UserWarning, module="stumpy")


@dataclass
class Motif:
    template: np.ndarray          # (채널수, window) — 대표 캔들 모양
    seed_index: int
    occurrences: list[int] = field(default_factory=list)
    max_distance: float = 0.0     # 그룹 내부 최대(합)거리 → 매칭 임계값

    @property
    def n(self) -> int:
        return len(self.occurrences)


def dist_profile(template: np.ndarray, channels: list[np.ndarray]) -> np.ndarray:
    """채널별 z-정규화 거리(mass)의 합 = 다변량 거리 프로파일."""
    dp = None
    for q, T in zip(template, channels):
        d = np.asarray(stumpy.mass(q, T), dtype=np.float64)
        dp = d if dp is None else dp + d
    return dp


def _extract(dp: np.ndarray, threshold: float, excl: int, max_matches: int) -> list[int]:
    """거리 프로파일에서 임계값 이하 지점을 겹치지 않게(exclusion) 뽑는다."""
    d = dp.copy()
    out: list[int] = []
    while len(out) < max_matches:
        i = int(np.argmin(d))
        if not np.isfinite(d[i]) or d[i] > threshold:
            break
        out.append(i)
        lo, hi = max(0, i - excl), min(len(d), i + excl + 1)
        d[lo:hi] = np.inf
    return sorted(out)


def match(template: np.ndarray, channels: list[np.ndarray],
          threshold: float, excl: int, max_matches: int = 200) -> list[int]:
    """검증구간 등에서 template 모양이 나타나는 시작 인덱스들."""
    return _extract(dist_profile(template, channels), threshold, excl, max_matches)


def _combined_mp(channels: list[np.ndarray], window: int) -> np.ndarray:
    """모든 채널을 함께 본 matrix profile(값이 작을수록 어딘가에 닮은 게 있음)."""
    if len(channels) == 1:
        mp = stumpy.stump(channels[0], m=window)
        return mp[:, 0].astype(np.float64)
    T = np.vstack(channels).astype(np.float64)
    P, _ = stumpy.mstump(T, window)
    return P[len(channels) - 1].astype(np.float64)  # 전 채널 합산 거리


def discover(
    channels: list[np.ndarray],
    window: int,
    max_motifs: int,
    min_occurrences: int,
    max_matches: int = 40,
    cutoff_pctl: float = 45.0,
) -> list[Motif]:
    """
    channels: 1개(종가) 또는 4개(OHLC)의 1D 배열 리스트.
    가장 잘 반복되는 모양부터 그룹으로 묶어 Motif 목록을 만든다.
    """
    channels = [np.asarray(c, dtype=np.float64) for c in channels]
    profile = _combined_mp(channels, window)  # 순위 매기기용(스케일 무관)
    if not np.isfinite(profile).any():
        return []
    excl = max(1, window // 2)
    order = np.argsort(profile)          # 가장 반복적인(거리 작은) 후보부터

    # 임계값(cutoff)은 실제 거리 프로파일(mass 합산)과 같은 스케일에서 정한다:
    # 전 구간에 고르게 뽑은 표본들의 '최근접 이웃 거리' 분포의 백분위.
    l = len(profile)
    sample = sorted({int(s) for s in np.linspace(0, l - 1, min(l, 120)).astype(int)
                     if np.isfinite(profile[int(s)])})
    nn: list[float] = []
    for s in sample:
        tmpl = np.array([c[s:s + window] for c in channels])
        d = dist_profile(tmpl, channels).copy()
        d[max(0, s - excl):min(len(d), s + excl + 1)] = np.inf
        if np.isfinite(d).any():
            nn.append(float(np.min(d)))
    if not nn:
        return []
    cutoff = float(np.percentile(nn, cutoff_pctl))
    covered = np.zeros(len(profile), dtype=bool)
    motifs: list[Motif] = []
    attempts = 0
    for seed in order:
        if len(motifs) >= max_motifs or attempts > max_motifs * 8:
            break
        seed = int(seed)
        if covered[seed] or not np.isfinite(profile[seed]) or profile[seed] > cutoff:
            continue
        attempts += 1
        template = np.array([c[seed:seed + window] for c in channels])
        dp = dist_profile(template, channels)
        occ = _extract(dp, cutoff, excl, max_matches)
        if len(occ) < min_occurrences:
            covered[seed] = True
            continue
        for i in occ:                    # 겹치는 구간은 이후 후보에서 제외
            lo, hi = max(0, i - excl), min(len(covered), i + excl + 1)
            covered[lo:hi] = True
        motifs.append(Motif(
            template=template, seed_index=seed, occurrences=occ,
            max_distance=float(max(dp[i] for i in occ)),
        ))
    return motifs
