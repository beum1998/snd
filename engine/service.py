"""
서비스 계층: 파라미터를 받아 전체 파이프라인을 돌리고 UI가 쓸 JSON(dict)을 반환.

두 가지 모드:
  precursor (v1.5, 기본) — 급등/급락(트리플 배리어) 직전 L캔들을 클러스터링해 '전조 템플릿'을
    만들고, 그 템플릿의 리프트(매칭 후 이벤트 확률 ÷ 기저율)를 학습(멤버 제외)·검증에서 잰다.
    거래 TP/SL은 이벤트 정의와 동일한 ±tp×ATR / ∓sl×ATR (진입 시점 ATR 기준).
  motif (v1) — 전 구간에서 자주 반복되는 모양을 발견(mstump). 예측력 없음이 확인된 방식이지만
    비교용으로 남겨둔다. O(n²)라 캔들 수 제한.

공통: 학습/검증 시간 분리, 포트폴리오는 시드 $10,000·한 번에 한 포지션·TP/SL로만 청산.
"""
from __future__ import annotations

import numpy as np

from . import calibrate, config, data, events, patterns, precursor, simulate


def _defaults() -> dict:
    return {
        "mode": config.MODE,
        "symbol": config.SYMBOL,
        "timeframe": config.TIMEFRAME,
        "candles": config.CANDLES,
        "basis": config.PATTERN_BASIS,
        "allow_short": config.ALLOW_SHORT,
        "window": config.WINDOW,
        "calib_horizon": config.CALIB_HORIZON,
        "seed_capital": config.SEED_CAPITAL,
        "train_ratio": config.TRAIN_RATIO,
        "fee": config.FEE,
        "slippage": config.SLIPPAGE,
        # v1 motif 모드
        "max_motifs": config.MAX_MOTIFS,
        "min_occurrences": config.MIN_OCCURRENCES,
        "max_matches": config.MAX_MATCHES,
        "cutoff_pctl": config.MOTIF_CUTOFF_PCTL,
        "min_win_rate": config.MIN_WIN_RATE,
        "min_avg_return": config.MIN_AVG_RETURN,
        # v1.5 precursor 모드
        "atr_period": config.ATR_PERIOD,
        "event_horizon": config.EVENT_HORIZON,
        "event_tp_atr": config.EVENT_TP_ATR,
        "event_sl_atr": config.EVENT_SL_ATR,
        "precursor_len_min": config.PRECURSOR_LEN_MIN,
        "precursor_len_max": config.PRECURSOR_LEN_MAX,
        "use_volume": config.USE_VOLUME,
        "n_clusters": config.N_CLUSTERS,
        "min_cluster_size": config.MIN_CLUSTER_SIZE,
        "min_train_matches": config.MIN_TRAIN_MATCHES,
        "min_test_matches": config.MIN_TEST_MATCHES,
        "min_lift_train": config.MIN_LIFT_TRAIN,
        "min_lift_test": config.MIN_LIFT_TEST,
        "default_weight": 1.0,
        # {pattern_id(str): {tp, sl, weight, enabled, direction}}
        "overrides": {},
    }


def _znorm(x: np.ndarray) -> list[float]:
    x = np.asarray(x, dtype=float)
    s = x.std()
    z = (x - x.mean()) / s if s > 0 else x - x.mean()
    return [round(float(v), 4) for v in z]


def _znorm_ohlc(tpl: np.ndarray) -> list[list[float]]:
    """OHLC 4채널을 '공통' 평균/표준편차로 z-정규화 — 채널별로 하면 고가<저가처럼
    캔들 형태가 깨지므로 반드시 함께 정규화한다. (UI 캔들 표시용)"""
    ohlc = np.asarray(tpl[:4], dtype=float)
    mu, sd = ohlc.mean(), ohlc.std()
    z = (ohlc - mu) / sd if sd > 0 else ohlc - mu
    return [[round(float(v), 4) for v in row] for row in z]


def _max_drawdown(equity: list[float]) -> float:
    if not equity:
        return 0.0
    arr = np.array(equity, dtype=float)
    peak = np.maximum.accumulate(arr)
    return float(((arr - peak) / peak).min())


def _score(n: int, hits: int, base: float, z: float = 1.645) -> float:
    """추천 점수(학습 전용) = 적중률의 Wilson 95% 신뢰하한 ÷ 기저율.
    '우연이 아니라고 95% 확신할 수 있는 최소 리프트' — 표본이 적으면 자동으로 깎인다.
    검증구간 수치는 절대 넣지 않는다(넣는 순간 검증이 선택에 오염됨)."""
    if n <= 0 or base <= 0:
        return 0.0
    p = hits / n
    z2 = z * z
    lower = (p + z2 / (2 * n) - z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5)) / (1 + z2 / n)
    return float(max(0.0, lower) / base)


def _forward_detail(close, times_ms, entries, flags, horizon: int,
                    max_paths: int = 50, pts: int = 48) -> dict:
    """매칭 진입 이후 horizon캔들 수익률 경로(이벤트 스터디 시각화용).
    중앙값은 전체 매칭으로 계산, 개별 경로는 최대 max_paths개만 균등 샘플(payload 절약)."""
    n = len(close)
    step = max(1, horizon // pts)
    items, full = [], []
    for e in entries:
        end = min(e + horizon, n - 1)
        if end <= e:
            continue
        path = close[e:end + 1] / close[e] - 1.0
        items.append((int(e), path))
        if end == e + horizon:
            full.append(path)

    med = np.median(np.vstack(full), axis=0) if full else None
    if len(items) > max_paths:
        pick = sorted(set(np.linspace(0, len(items) - 1, max_paths).astype(int).tolist()))
        shown = [items[i] for i in pick]
    else:
        shown = items

    def ds(a) -> list[float]:
        return [round(float(v), 4) for v in a[::step]]

    return {
        "n_total": len(items),
        "median": ds(med) if med is not None else [],
        "paths": [{
            "i": e, "t_ms": times_ms[e], "hit": bool(flags[e]),
            "final": round(float(path[-1]), 4), "path": ds(path),
        } for e, path in shown],
    }


def _portfolio(signals: list[dict], high, low, close, times_ms, seed: float,
               cost: float, split: int, n: int, n_discovered: int, n_enabled: int) -> dict:
    """시드 $, 한 번에 한 포지션(보유 중 신규진입 금지), TP/SL로만 청산."""
    signals = sorted(signals, key=lambda s: s["g"])
    equity = seed
    pos_until = -1
    eq_curve = [{"i": split, "t_ms": times_ms[split], "equity": round(seed, 2)}] if split < n else []
    port_trades: list[dict] = []
    for s in signals:
        g = s["g"]
        if g <= pos_until or g >= n - 1:
            continue
        ex_idx, ex_price, reason = simulate.resolve_exit(high, low, close, g, s["direction"], s["tp"], s["sl"])
        ret = simulate.trade_return(close[g], ex_price, s["direction"], cost)
        equity *= (1.0 + s["weight"] * ret)
        pos_until = ex_idx
        port_trades.append({"entry_idx": g, "exit_idx": ex_idx, "ret": ret,
                            "direction": s["direction"], "pattern_id": s["pid"], "reason": reason})
        eq_curve.append({"i": ex_idx, "t_ms": times_ms[ex_idx], "equity": round(equity, 2)})

    rets = np.array([t["ret"] for t in port_trades], dtype=float)
    te_cl = close[split:]
    bh_ret = float(te_cl[-1] / te_cl[0] - 1.0) if len(te_cl) > 1 else 0.0
    return {
        "seed_capital": seed,
        "final_equity": round(equity, 2),
        "n_patterns_discovered": n_discovered,
        "n_patterns_enabled": n_enabled,
        "n_trades": len(port_trades),
        "win_rate": float((rets > 0).mean()) if len(rets) else 0.0,
        "total_return": float(equity / seed - 1.0),
        "buy_hold_return": bh_ret,
        "buy_hold_final": round(seed * (1.0 + bh_ret), 2),
        "max_drawdown": _max_drawdown([e["equity"] for e in eq_curve]),
        "equity_curve": eq_curve,
    }


def run(params: dict | None = None) -> dict:
    p = _defaults()
    if params:
        p.update({k: v for k, v in params.items() if v is not None})

    df = data.load(p["symbol"], p["timeframe"], int(p["candles"]))
    open_ = df["open"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    close = df["close"].to_numpy(dtype=np.float64)
    volume = df["volume"].to_numpy(dtype=np.float64)
    # datetime 해상도(ms/ns)에 무관하게 epoch ms로 변환 (pandas 3.0은 해상도 보존)
    times_ms = df.index.tz_localize(None).astype("datetime64[ms]").astype("int64").tolist()

    if p["mode"] == "motif":
        if len(close) > config.MOTIF_MAX_CANDLES:
            raise ValueError(
                f"motif 모드는 O(n²)라 캔들 {config.MOTIF_MAX_CANDLES:,}개 이하만 지원합니다. "
                f"캔들 수를 줄이거나 전조(precursor) 모드를 쓰세요.")
        return _run_motif(p, open_, high, low, close, times_ms)
    return _run_precursor(p, open_, high, low, close, volume, times_ms)


# ──────────────────────────────────────────────────────────────
# v1.5 precursor 모드
# ──────────────────────────────────────────────────────────────

def _run_precursor(p, open_, high, low, close, volume, times_ms) -> dict:
    overrides = p.get("overrides") or {}
    n = len(close)
    split = int(n * float(p["train_ratio"]))
    K = int(p["event_horizon"])
    tp_atr = float(p["event_tp_atr"])
    sl_atr = float(p["event_sl_atr"])
    seed = float(p["seed_capital"])
    cost = 2 * (float(p["fee"]) + float(p["slippage"]))
    allow_short = bool(p["allow_short"])

    # 전조 길이: 최소~최대에서 2배씩 (촘촘히 다 돌리면 다중 비교 폭증 → 스케일만 다양화)
    lmin = max(4, int(p["precursor_len_min"]))
    lmax = max(lmin, int(p["precursor_len_max"]))
    lengths: list[int] = []
    _l = lmin
    while _l <= lmax:
        lengths.append(_l)
        _l *= 2

    # --- 라벨링 ---
    atr_arr = events.atr(high, low, close, int(p["atr_period"]))
    up, down, valid = events.label(high, low, close, atr_arr, K, tp_atr, sl_atr)

    # 학습 라벨: 판정(K캔들)이 학습구간 안에서 끝나는 것만 → 검증 데이터 미리보기 방지
    train_valid = valid.copy()
    train_valid[max(0, split - K):] = False
    # 검증 진입은 검증 슬라이스 안에서 매칭되므로 전조가 검증구간 안에 있는 게 자동 보장됨
    #  (매칭 시작 s ≥ 0 → 진입 = s + L - 1 ≥ L - 1)

    channels = [open_, high, low, close]
    if bool(p["use_volume"]):
        channels.append(np.log1p(np.maximum(volume, 0.0)))
    train_channels = [c[:split] for c in channels]
    test_channels = [c[split:] for c in channels]

    # --- 학습 이벤트 → 전조 클러스터링 ---
    up_train = events.merge_starts(np.where(up & train_valid)[0], K)
    dn_train = events.merge_starts(np.where(down & train_valid)[0], K)

    templates = []
    for L in lengths:
        templates += precursor.cluster(
            train_channels, up_train, L, "long",
            int(p["n_clusters"]), int(p["min_cluster_size"]))
        if allow_short:
            templates += precursor.cluster(
                train_channels, dn_train, L, "short",
                int(p["n_clusters"]), int(p["min_cluster_size"]))

    # 진입 시점 ATR 기반 TP/SL (이벤트 정의와 동일한 배수)
    atr_frac = np.where(close > 0, atr_arr / close, np.nan)
    med_frac = float(np.nanmedian(atr_frac[:split])) if split > 0 else 0.005

    def tp_sl_at(g: int, tp_ov, sl_ov) -> tuple[float, float]:
        f = atr_frac[g] if np.isfinite(atr_frac[g]) else med_frac
        tp = float(tp_ov) if tp_ov is not None else float(tp_atr * f)
        sl = float(sl_ov) if sl_ov is not None else float(sl_atr * f)
        return tp, sl

    pattern_out: list[dict] = []
    signals: list[dict] = []

    for pid, t in enumerate(templates):
        ov = overrides.get(str(pid), {})
        flags = up if t.direction == "long" else down
        L = t.template.shape[1]          # 템플릿마다 전조 길이가 다름
        excl = max(1, L // 2)

        # ★ 리프트: 학습은 클러스터 멤버 자신을 제외(전원 이벤트라 포함하면 가짜로 높아짐)
        tr_ev = precursor.evaluate(t, train_channels, flags[:split], train_valid[:split],
                                   L, excl, exclude_members=True)
        te_ev = precursor.evaluate(t, test_channels, flags[split:], valid[split:],
                                   L, excl, exclude_members=False)

        direction = ov.get("direction") if ov.get("direction") in ("long", "short") else t.direction
        weight = float(ov.get("weight", p["default_weight"]))
        tp_ov, sl_ov = ov.get("tp"), ov.get("sl")
        disp_tp, disp_sl = tp_sl_at(t.medoid_start + L - 1, tp_ov, sl_ov)

        # 학습 단독 성과: 멤버 제외 매칭 진입만(정직한 out-of-member 성과)
        train_specs = [(e, direction, *tp_sl_at(e, tp_ov, sl_ov)) for e in tr_ev["entries"]]
        train_stats = simulate.stats(simulate.simulate_per_entry(
            high[:split], low[:split], close[:split], train_specs, cost))

        # 자동선별은 '학습' 기준만 사용 (검증 성과로 고르면 검증이 오염됨)
        selected = (tr_ev["n_matches"] >= int(p["min_train_matches"])
                    and tr_ev["lift"] >= float(p["min_lift_train"]))
        # 검증 통과 배지: 검증구간에서도 리프트가 재현되는가 (표시용 판정)
        test_pass = (te_ev["n_matches"] >= int(p["min_test_matches"])
                     and te_ev["lift"] >= float(p["min_lift_test"]))
        enabled = bool(ov.get("enabled", selected))

        # 검증 단독 성과: 전역 인덱스로 시뮬(청산은 데이터 끝까지 스캔)
        test_entries_g = [split + e for e in te_ev["entries"]]
        test_specs = [(g, direction, *tp_sl_at(g, tp_ov, sl_ov)) for g in test_entries_g]
        test_trades = simulate.simulate_per_entry(high, low, close, test_specs, cost)
        test_stats = simulate.stats(test_trades)

        if enabled:
            for g in test_entries_g:
                if g < n - 1:
                    tp, sl = tp_sl_at(g, tp_ov, sl_ov)
                    signals.append({"g": g, "direction": direction, "tp": tp, "sl": sl,
                                    "weight": weight, "pid": pid})

        # 예상 수익률(참고용): 학습 적중률 기준 기대값
        expected = tr_ev["precision"] * disp_tp - (1 - tr_ev["precision"]) * disp_sl - cost

        pattern_out.append({
            "id": pid, "seed_index": t.medoid_start, "length": L,
            "n_occurrences": t.n_members, "template": _znorm(t.template[3]),
            "template_ohlc": _znorm_ohlc(t.template),
            "direction": direction, "tp": disp_tp, "sl": disp_sl, "weight": weight,
            "expected_return": float(expected),
            "auto_tp": disp_tp, "auto_sl": disp_sl, "auto_direction": t.direction,
            "train": train_stats, "test": {**test_stats, "trades": test_trades},
            "selected": selected, "enabled": enabled,
            "test_pass": test_pass,
            "score": round(_score(tr_ev["n_matches"], tr_ev["n_hits"], tr_ev["base_rate"]), 4),
            "lift": {
                "train": {k: v for k, v in tr_ev.items() if k != "entries"},
                "test": {k: v for k, v in te_ev.items() if k != "entries"},
            },
            # 매칭 이후 추세(이벤트 스터디): 학습=멤버 제외 매칭, 검증=검증 매칭
            "detail": {
                "horizon": K,
                "train": _forward_detail(close, times_ms, tr_ev["entries"], flags, K),
                "test": _forward_detail(close, times_ms, test_entries_g, flags, K),
            },
        })

    # 추천 점수순 정렬(학습 전용 점수). id는 유지 — 오버라이드 매핑이 깨지지 않게.
    pattern_out.sort(key=lambda x: x["score"], reverse=True)

    portfolio = _portfolio(signals, high, low, close, times_ms, seed, cost, split, n,
                           n_discovered=len(templates),
                           n_enabled=sum(1 for x in pattern_out if x["enabled"]))

    # 차트 표시용 이벤트 마커(전체 구간, 병합)
    ev_out = (
        [{"i": e, "t_ms": times_ms[e], "dir": "up"}
         for e in events.merge_starts(np.where(up & valid)[0], K)]
        + [{"i": e, "t_ms": times_ms[e], "dir": "down"}
           for e in events.merge_starts(np.where(down & valid)[0], K)]
    )

    return {
        "ok": True,
        "params": {k: p[k] for k in _defaults() if k != "overrides"},
        "data": {
            "symbol": p["symbol"], "timeframe": p["timeframe"],
            "n_candles": n, "split_index": split,
            "times_ms": times_ms, "close": [round(float(c), 2) for c in close],
        },
        "patterns": pattern_out,
        "portfolio": portfolio,
        "events": ev_out,
        "labeling": {
            "n_events_up_train": len(up_train),
            "n_events_down_train": len(dn_train),
            "base_up_train": float(up[train_valid].mean()) if train_valid.any() else 0.0,
            "base_down_train": float(down[train_valid].mean()) if train_valid.any() else 0.0,
            "base_up_test": float(up[split:][valid[split:]].mean()) if valid[split:].any() else 0.0,
            "base_down_test": float(down[split:][valid[split:]].mean()) if valid[split:].any() else 0.0,
            "atr_frac_median": med_frac,
        },
    }


# ──────────────────────────────────────────────────────────────
# v1 motif 모드 (비교용으로 유지)
# ──────────────────────────────────────────────────────────────

def _run_motif(p, open_, high, low, close, times_ms) -> dict:
    overrides = p.get("overrides") or {}
    n = len(close)
    split = int(n * float(p["train_ratio"]))
    window = int(p["window"])
    horizon = int(p["calib_horizon"])
    seed = float(p["seed_capital"])
    cost = 2 * (float(p["fee"]) + float(p["slippage"]))
    allow_short = bool(p["allow_short"])
    excl = max(1, window // 2)
    entry_end = window - 1

    full_channels = [open_, high, low, close] if p["basis"] == "ohlc" else [close]
    train_channels = [c[:split] for c in full_channels]
    test_channels = [c[split:] for c in full_channels]

    motifs = patterns.discover(
        train_channels, window, int(p["max_motifs"]), int(p["min_occurrences"]),
        max_matches=int(p["max_matches"]), cutoff_pctl=float(p["cutoff_pctl"]),
    )

    tr_hi, tr_lo, tr_cl = high[:split], low[:split], close[:split]
    te_hi, te_lo, te_cl = high[split:], low[split:], close[split:]
    pattern_out: list[dict] = []
    signals: list[dict] = []

    for pid, m in enumerate(motifs):
        ov = overrides.get(str(pid), {})
        train_entries = [i + entry_end for i in m.occurrences]

        cal = calibrate.calibrate(train_entries, tr_hi, tr_lo, tr_cl, horizon, allow_short)
        direction = ov.get("direction") if ov.get("direction") in ("long", "short") else cal["direction"]
        tp = float(ov.get("tp", cal["tp"]))
        sl = float(ov.get("sl", cal["sl"]))
        weight = float(ov.get("weight", p["default_weight"]))

        train_stats = simulate.stats(simulate.simulate(
            tr_hi, tr_lo, tr_cl, train_entries, tp, sl, cost, direction=direction))
        selected = (
            train_stats["n_trades"] >= int(p["min_occurrences"])
            and train_stats["win_rate"] >= float(p["min_win_rate"])
            and train_stats["avg_return"] >= float(p["min_avg_return"])
        )
        enabled = bool(ov.get("enabled", selected))

        raw = patterns.match(m.template, test_channels, m.max_distance, excl, max_matches=200)
        test_entries = [i + entry_end for i in raw]
        test_trades = simulate.simulate(
            te_hi, te_lo, te_cl, test_entries, tp, sl, cost,
            index_offset=split, direction=direction)
        test_stats = simulate.stats(test_trades)

        if enabled:
            for i in test_entries:
                if 0 <= i < len(te_cl):
                    signals.append({"g": split + i, "direction": direction,
                                    "tp": tp, "sl": sl, "weight": weight, "pid": pid})

        pattern_out.append({
            "id": pid, "seed_index": m.seed_index, "length": window,
            "n_occurrences": m.n, "template": _znorm(m.template[-1]),
            "template_ohlc": _znorm_ohlc(m.template) if p["basis"] == "ohlc" else None,
            "direction": direction, "tp": tp, "sl": sl, "weight": weight,
            "expected_return": cal["expected_return"],
            "auto_tp": cal["tp"], "auto_sl": cal["sl"], "auto_direction": cal["direction"],
            "train": train_stats, "test": {**test_stats, "trades": test_trades},
            "selected": selected, "enabled": enabled,
        })

    portfolio = _portfolio(signals, high, low, close, times_ms, seed, cost, split, n,
                           n_discovered=len(motifs),
                           n_enabled=sum(1 for x in pattern_out if x["enabled"]))

    return {
        "ok": True,
        "params": {k: p[k] for k in _defaults() if k != "overrides"},
        "data": {
            "symbol": p["symbol"], "timeframe": p["timeframe"],
            "n_candles": n, "split_index": split,
            "times_ms": times_ms, "close": [round(float(c), 2) for c in close],
        },
        "patterns": pattern_out,
        "portfolio": portfolio,
        "events": [],
        "labeling": None,
    }
