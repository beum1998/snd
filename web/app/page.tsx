"use client";
import { useEffect, useMemo, useState } from "react";
import {
  BacktestResult, Override, Params, getDefaults, runBacktest, pct, signClass, usd,
} from "@/lib/api";
import Controls from "@/components/Controls";
import PatternCard from "@/components/PatternCard";
import { EquityChart } from "@/components/Charts";
import { PriceChart, TradeMark } from "@/components/PriceChart";

const PALETTE = [
  "#4c8dff", "#35d07f", "#ffb020", "#ff5c7a", "#b388ff",
  "#00c2d7", "#ff8a5c", "#7dd3fc", "#f472b6", "#a3e635",
  "#f59e0b", "#22d3ee", "#c084fc", "#4ade80", "#fb7185",
];
const colorOf = (i: number) => PALETTE[i % PALETTE.length];

export default function Home() {
  const [params, setParams] = useState<Params | null>(null);
  const [meta, setMeta] = useState<{ symbols: string[]; timeframes: string[] }>({ symbols: [], timeframes: [] });
  const [overrides, setOverrides] = useState<Record<string, Override>>({});
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDefaults()
      .then((d) => { setParams(d.defaults); setMeta({ symbols: d.symbols, timeframes: d.timeframes }); })
      .catch((e) => setError(`API 연결 실패: ${e.message}. FastAPI 서버(8000)가 켜져 있나요?`));
  }, []);

  async function run() {
    if (!params) return;
    setLoading(true); setError(null);
    try {
      const r = await runBacktest(params, overrides);
      if (!r.ok) { setError(r.error ?? "알 수 없는 오류"); setResult(null); }
      else setResult(r);
    } catch (e) {
      setError((e as Error).message);
    } finally { setLoading(false); }
  }

  // 구조적 파라미터가 바뀌면 패턴별 오버라이드는 초기화(패턴이 달라지므로)
  const STRUCTURAL: (keyof Params)[] = [
    "mode", "symbol", "timeframe", "candles", "train_ratio", "basis",
    "window", "max_motifs",
    "event_horizon", "event_tp_atr", "event_sl_atr",
    "precursor_len_min", "precursor_len_max",
    "use_volume", "n_clusters", "min_cluster_size",
  ];
  function changeParams(next: Params) {
    if (params && STRUCTURAL.some((k) => next[k] !== params[k])) {
      setOverrides({});
    }
    setParams(next);
  }

  const setOverride = (id: number, ov: Override) =>
    setOverrides((prev) => ({ ...prev, [id]: ov }));

  const chartTrades = useMemo<TradeMark[]>(() => {
    if (!result) return [];
    const out: TradeMark[] = [];
    result.patterns.forEach((p) => {
      const enabled = overrides[p.id]?.enabled ?? p.enabled;
      if (!enabled) return;
      p.test.trades.forEach((t) =>
        out.push({ entry: t.entry_idx, exit: t.exit_idx, dir: t.direction, color: colorOf(p.id) }));
    });
    return out;
  }, [result, overrides]);

  // 단순보유 자산곡선($): 시드로 split 시점에 매수해 보유
  const buyHoldCurve = useMemo(() => {
    if (!result) return [];
    const { close, split_index: s, n_candles: n } = result.data;
    const seed = result.portfolio.seed_capital;
    const base = close[s];
    const step = Math.max(1, Math.floor((n - s) / 500));
    const out: { i: number; v: number }[] = [];
    for (let i = s; i < n; i += step) out.push({ i, v: seed * (close[i] / base) });
    return out;
  }, [result]);

  const strategyCurve = useMemo(
    () => (result ? result.portfolio.equity_curve.map((p) => ({ i: p.i, v: p.equity })) : []),
    [result]
  );

  if (error && !params)
    return <div className="app"><div className="err">{error}</div></div>;
  // select 옵션(meta)이 준비된 뒤에만 렌더 → controlled select value 동기화 보장
  if (!params || meta.timeframes.length === 0)
    return <div className="app"><div className="loading">로딩 중…</div></div>;

  const pf = result?.portfolio;
  const beatsBH = pf ? pf.total_return > pf.buy_hold_return : false;

  return (
    <div className="app">
      <div className="header">
        <h1>크립토 패턴 봇</h1>
        <span className="tag">테스트베드 · 실거래 아님</span>
      </div>
      <div className="subtitle">
        급등·급락 <b>직전 구간(전조)</b>에서 공통 패턴을 발견하고, 그 패턴의 <b>리프트</b>(매칭 후
        이벤트 확률 ÷ 기저율)를 검증구간(처음 보는 데이터)에서 확인합니다.
      </div>

      <div className="layout">
        <Controls
          params={params} symbols={meta.symbols} timeframes={meta.timeframes}
          onChange={changeParams} onRun={run} loading={loading}
        />

        <div>
          {error && <div className="err" style={{ marginBottom: 16 }}>{error}</div>}
          {!result && !loading && (
            <div className="panel"><div className="loading">
              왼쪽에서 파라미터를 정하고 <b>▶ 백테스트 실행</b>을 눌러보세요.
            </div></div>
          )}
          {loading && <div className="panel"><div className="loading">패턴 발견 → 매칭 → 매매 계산 중…</div></div>}

          {result && pf && (
            <>
              {result.labeling && (
                <div className="panel">
                  <h2>⚡ 이벤트 라벨링 <span className="muted small">(±{result.params.event_tp_atr}×ATR · {result.params.event_horizon}캔들 판정)</span></h2>
                  <div className="stats">
                    <div className="stat"><div className="k">학습 급등 이벤트</div>
                      <div className="v pos">{result.labeling.n_events_up_train}개</div>
                      <div className="small muted">기저율 {pct(result.labeling.base_up_train)}</div></div>
                    <div className="stat"><div className="k">학습 급락 이벤트</div>
                      <div className="v neg">{result.labeling.n_events_down_train}개</div>
                      <div className="small muted">기저율 {pct(result.labeling.base_down_train)}</div></div>
                    <div className="stat"><div className="k">검증 기저율 (급등/급락)</div>
                      <div className="v neu">{pct(result.labeling.base_up_test)} / {pct(result.labeling.base_down_test)}</div></div>
                    <div className="stat"><div className="k">ATR 중앙값 (÷가격)</div>
                      <div className="v neu">{pct(result.labeling.atr_frac_median)}</div>
                      <div className="small muted">TP≈{pct(result.labeling.atr_frac_median * result.params.event_tp_atr)} · 왕복비용 {pct(2 * (result.params.fee + result.params.slippage))}</div></div>
                  </div>
                  <div className="small muted" style={{ marginTop: 8 }}>
                    리프트 ×1.0 = 예측력 없음. 기저율이 높으면 “이벤트”가 흔하다는 뜻이니 기준(×ATR)을 올려보세요.
                    단, 결과를 보고 정의를 계속 바꾸는 건 과최적화입니다.
                  </div>
                </div>
              )}
              <div className="panel">
                <h2>📊 포트폴리오 성과 <span className="muted small">(검증구간 · 시드 {usd(pf.seed_capital)} · 한 번에 한 포지션)</span></h2>
                <div className="stats">
                  <div className="stat"><div className="k">전략 최종자산</div>
                    <div className={`v ${signClass(pf.total_return)}`}>{usd(pf.final_equity)}</div>
                    <div className={`small ${signClass(pf.total_return)}`}>{pct(pf.total_return)}</div></div>
                  <div className="stat"><div className="k">단순보유 최종</div>
                    <div className={`v ${signClass(pf.buy_hold_return)}`}>{usd(pf.buy_hold_final)}</div>
                    <div className={`small ${signClass(pf.buy_hold_return)}`}>{pct(pf.buy_hold_return)}</div></div>
                  <div className="stat"><div className="k">체결 / 승률</div>
                    <div className="v neu">{pf.n_trades} · {pf.n_trades ? Math.round(pf.win_rate * 100) : 0}%</div></div>
                  <div className="stat"><div className="k">최대낙폭(MDD)</div>
                    <div className="v neg">{pct(pf.max_drawdown)}</div></div>
                </div>
                <div className={`verdict ${beatsBH && pf.n_trades > 0 ? "good" : "bad"}`}>
                  {pf.n_trades === 0
                    ? "⚠️ 활성화된 패턴/체결이 없습니다. 아래 카드에서 패턴을 켜고 다시 실행하세요."
                    : beatsBH
                      ? "✅ 검증구간에서 단순보유보다 나은 성과입니다. 단, 체결 수가 충분한지·다른 기간에도 통하는지 반드시 재검증하세요."
                      : "❌ 단순보유보다 못합니다. 지금 패턴들로는 예측력이 약하다는 뜻일 수 있어요 (흔하고 정상적인 결과)."}
                </div>
                <div style={{ marginTop: 14 }}>
                  <div className="legend">
                    <span><span className="dot" style={{ background: "#4c8dff" }} />전략 자산($)</span>
                    <span><span className="dot" style={{ background: "#8b94a7" }} />단순보유($)</span>
                  </div>
                  <EquityChart strategy={strategyCurve} buyHold={buyHoldCurve} seed={pf.seed_capital} timesMs={result.data.times_ms} />
                </div>
              </div>

              <div className="panel">
                <h2>📈 가격 + 매수/매도 시점</h2>
                <div className="small muted" style={{ marginBottom: 8 }}>
                  활성화된 패턴의 진입·청산이 BUY(초록▲)/SELL(빨강▼)로 표시됩니다.
                  {chartTrades.length === 0 && " (아래 카드에서 패턴을 켜세요.)"}
                </div>
                <PriceChart
                  close={result.data.close}
                  timesMs={result.data.times_ms}
                  splitIndex={result.data.split_index}
                  trades={chartTrades}
                  events={result.events ?? []}
                />
              </div>

              <div className="panel">
                <h2>🧩 발견된 패턴 <span className="muted small">
                  ({result.patterns.length}개 · 설정 바꾼 뒤 “다시 실행”)</span></h2>
                <div className="small muted" style={{ marginBottom: 12 }}>
                  각 패턴의 <b>모양</b>과, 학습구간·검증구간 성과를 보여줍니다.
                  익절/손절/비중을 조절하고 다시 실행하면 패턴별 수익이 갱신됩니다.
                </div>
                <div className="gallery">
                  {result.patterns.map((p, idx) => (
                    <PatternCard
                      key={p.id} pattern={p} color={colorOf(p.id)}
                      rank={p.score != null ? idx + 1 : undefined}
                      override={overrides[p.id] ?? {}}
                      onOverride={(ov) => setOverride(p.id, ov)}
                    />
                  ))}
                </div>
                <button className="run" style={{ marginTop: 14 }} onClick={run} disabled={loading}>
                  {loading ? "실행 중…" : "↻ 이 설정으로 다시 실행"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
