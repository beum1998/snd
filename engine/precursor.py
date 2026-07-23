"""
③-v1.5 전조(precursor) 패턴 발견
급등/급락 이벤트 '직전 L캔들'만 모아 비슷한 모양끼리 클러스터링하고,
각 클러스터의 대표(medoid)를 템플릿으로 삼는다.

- 채널: OHLC (+로그 거래량) — 창마다 채널별 z-정규화 후 이어붙여 벡터화
- 클러스터링: k-means (scipy.cluster.vq.kmeans2, 시드 고정)
- 크기 미달 클러스터는 버림 ("공통 전조가 없다"면 여기서 자연히 걸러짐)
- 매칭 임계값: medoid 템플릿과 멤버들 사이 mass 합산 거리의 최대값

★ 검증의 심장 — evaluate():
  "이 모양이 나타난 뒤 이벤트가 날 확률(precision)"을 기저율과 비교한 리프트.
  학습구간 리프트는 클러스터를 만든 멤버 자신을 반드시 제외하고 계산한다
  (멤버는 전원 이벤트 전조라서 포함하면 리프트가 가짜로 높아짐).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.cluster.vq import kmeans2

from . import patterns


@dataclass
class Template:
    template: np.ndarray      # (채널수, L) 원시 값 — 매칭 시 mass가 알아서 z-정규화
    direction: str            # "long"(급등 전조) | "short"(급락 전조)
    medoid_start: int         # medoid 전조 구간의 시작 인덱스(학습 로컬)
    members: list[int]        # 클러스터 멤버 전조 시작 인덱스들(학습 로컬)
    threshold: float          # 매칭 임계값 (mass 합산 거리)

    @property
    def n_members(self) -> int:
        return len(self.members)


def _znorm(x: np.ndarray) -> np.ndarray:
    s = x.std()
    return (x - x.mean()) / s if s > 0 else x - x.mean()


def _features(channels: list[np.ndarray], starts: list[int], L: int) -> np.ndarray:
    """전조 창들을 (창 수, 채널수×L) 벡터로. 창마다 채널별 z-정규화(모양만 비교)."""
    rows = []
    for s in starts:
        rows.append(np.concatenate([_znorm(c[s:s + L]) for c in channels]))
    return np.asarray(rows, dtype=np.float64)


def cluster(
    channels: list[np.ndarray],
    event_entries: list[int],
    L: int,
    direction: str,
    n_clusters: int,
    min_cluster_size: int,
    seed: int = 42,
) -> list[Template]:
    """
    event_entries: (병합된) 이벤트 시작 인덱스들 — 전조 창은 [e-L+1, e] (이벤트 캔들 미포함).
    비슷한 전조끼리 묶어 크기순 Template 목록을 만든다.
    """
    starts = [e - L + 1 for e in event_entries if e - L + 1 >= 0]
    if len(starts) < max(2, min_cluster_size):
        return []

    X = _features(channels, starts, L)
    k = int(min(n_clusters, len(starts)))
    _, assign = kmeans2(X, k, minit="++", seed=seed)

    out: list[Template] = []
    for c in range(k):
        idx = np.where(assign == c)[0]
        if len(idx) < min_cluster_size:
            continue
        # medoid = 클러스터 안에서 다른 멤버들과의 거리 합이 최소인 실제 표본
        sub = X[idx]
        d2 = ((sub[:, None, :] - sub[None, :, :]) ** 2).sum(axis=2)
        medoid_local = int(idx[int(np.argmin(d2.sum(axis=1)))])
        m_start = starts[medoid_local]
        template = np.array([ch[m_start:m_start + L] for ch in channels])

        # 매칭 임계값: 멤버 위치에서의 mass 합산 거리 최대값 (v1의 max_distance와 동일 스케일)
        dp = patterns.dist_profile(template, channels)
        member_starts = [starts[i] for i in idx]
        dists = [float(dp[s]) for s in member_starts if s < len(dp) and np.isfinite(dp[s])]
        if not dists:
            continue
        out.append(Template(
            template=template, direction=direction, medoid_start=m_start,
            members=sorted(member_starts), threshold=float(max(dists)),
        ))
    out.sort(key=lambda t: t.n_members, reverse=True)
    return out


def evaluate(
    tpl: Template,
    channels: list[np.ndarray],
    event_flags: np.ndarray,     # up 또는 down (채널과 같은 로컬 좌표)
    valid: np.ndarray,
    L: int,
    excl: int,
    exclude_members: bool,
    max_matches: int = 500,
) -> dict:
    """템플릿 매칭 지점들의 이벤트 적중률(precision)과 리프트. entries는 로컬 진입 인덱스."""
    starts = patterns.match(tpl.template, channels, tpl.threshold, excl, max_matches=max_matches)
    entries = [s + L - 1 for s in starts]

    if exclude_members and tpl.members:
        me = np.asarray([s + L - 1 for s in tpl.members])
        entries = [e for e in entries if int(np.abs(me - e).min()) >= excl]

    entries = [e for e in entries if e < len(valid) and valid[e]]
    hits = int(sum(bool(event_flags[e]) for e in entries))
    base = float(event_flags[valid].mean()) if valid.any() else 0.0
    precision = hits / len(entries) if entries else 0.0
    lift = precision / base if base > 0 else 0.0
    return {
        "n_matches": len(entries), "n_hits": hits,
        "precision": precision, "base_rate": base, "lift": lift,
        "entries": entries,
    }
