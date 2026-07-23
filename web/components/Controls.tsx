"use client";
import { Params } from "@/lib/api";

interface Props {
  params: Params;
  symbols: string[];
  timeframes: string[];
  onChange: (p: Params) => void;
  onRun: () => void;
  loading: boolean;
}

export default function Controls({ params, symbols, timeframes, onChange, onRun, loading }: Props) {
  const set = <K extends keyof Params>(k: K, v: Params[K]) => onChange({ ...params, [k]: v });
  const precursor = params.mode === "precursor";

  const Slider = (
    label: string, k: keyof Params, min: number, max: number, step: number, fmt?: (v: number) => string
  ) => (
    <div className="field">
      <label>{label}</label>
      <div className="row">
        <input type="range" min={min} max={max} step={step}
          value={params[k] as number}
          onChange={(e) => set(k, Number(e.target.value) as Params[keyof Params])} />
        <span className="val">{fmt ? fmt(params[k] as number) : (params[k] as number)}</span>
      </div>
    </div>
  );

  return (
    <div className="panel">
      <h2>⚙️ 파라미터</h2>

      <div className="field">
        <label>발견 방식</label>
        <select value={params.mode} onChange={(e) => set("mode", e.target.value as Params["mode"])}>
          <option value="precursor">급등·급락 전조 발견 (v1.5)</option>
          <option value="motif">반복 모양 발견 (v1 · 비교용)</option>
        </select>
      </div>

      <div className="field">
        <label>종목</label>
        <select value={params.symbol} onChange={(e) => set("symbol", e.target.value)}>
          {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="grid2">
        <div className="field">
          <label>분봉</label>
          <select value={params.timeframe} onChange={(e) => set("timeframe", e.target.value)}>
            {timeframes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="field">
          <label>캔들 수</label>
          <input type="number" min={1000} max={100000} step={1000}
            value={params.candles} onChange={(e) => set("candles", Number(e.target.value))} />
        </div>
      </div>
      {!precursor && params.candles > 20000 && (
        <div className="small muted" style={{ marginBottom: 6, color: "var(--red)" }}>
          ⚠️ 반복 모양(v1) 모드는 캔들 20,000개 이하만 지원합니다.
        </div>
      )}

      <div className="field">
        <label className="toggle">
          <input type="checkbox" checked={params.allow_short}
            onChange={(e) => set("allow_short", e.target.checked)} />
          숏 허용 (하락 예고 패턴은 매도로 거래)
        </label>
      </div>

      {Slider("학습 비율", "train_ratio", 0.5, 0.9, 0.05, (v) => `${Math.round(v * 100)}%`)}

      {precursor ? (
        <>
          <h2 style={{ marginTop: 18 }}>⚡ 이벤트 정의 <span className="muted small">(급등/급락)</span></h2>
          <div className="small muted" style={{ marginBottom: 6 }}>
            K캔들 안에 <b>±기준×ATR</b>에 먼저 닿으면 이벤트. 결과 보고 이 정의를 자꾸 바꾸면 과최적화입니다.
          </div>
          {Slider("판정 구간 K (캔들)", "event_horizon", 6, 288, 6)}
          {Slider("이벤트 기준 (×ATR)", "event_tp_atr", 1, 15, 0.5, (v) => `${v}×`)}
          {Slider("무효(반대) 기준 (×ATR)", "event_sl_atr", 0.5, 8, 0.25, (v) => `${v}×`)}

          <h2 style={{ marginTop: 18 }}>🔎 전조 발견</h2>
          <div className="small muted" style={{ marginBottom: 6 }}>
            전조 길이는 최소에서 <b>2배씩</b> 늘려가며 여러 스케일을 동시에 탐색합니다 (예: 24→48→96).
          </div>
          {Slider("전조 길이 최소 (캔들)", "precursor_len_min", 8, 96, 4)}
          {Slider("전조 길이 최대 (캔들)", "precursor_len_max", 16, 192, 4)}
          {Slider("클러스터 수 (방향당)", "n_clusters", 2, 12, 1)}
          {Slider("최소 클러스터 크기", "min_cluster_size", 5, 50, 1)}
          <div className="field">
            <label className="toggle">
              <input type="checkbox" checked={params.use_volume}
                onChange={(e) => set("use_volume", e.target.checked)} />
              거래량 채널 포함 (OHLC + 로그 거래량)
            </label>
          </div>

          <h2 style={{ marginTop: 18 }}>✅ 선별 기준 (리프트)</h2>
          <div className="small muted" style={{ marginBottom: 6 }}>
            리프트 = 매칭 후 이벤트 확률 ÷ 기저율. ×1.0이면 예측력 없음.
          </div>
          {Slider("학습 최소 매칭 수", "min_train_matches", 10, 100, 5)}
          {Slider("학습 최소 리프트", "min_lift_train", 1.0, 3.0, 0.05, (v) => `×${v.toFixed(2)}`)}
          {Slider("검증 최소 매칭 수", "min_test_matches", 5, 60, 5)}
          {Slider("검증 최소 리프트", "min_lift_test", 1.0, 2.5, 0.05, (v) => `×${v.toFixed(2)}`)}
        </>
      ) : (
        <>
          <div className="field">
            <label>패턴 기준</label>
            <select value={params.basis} onChange={(e) => set("basis", e.target.value as Params["basis"])}>
              <option value="ohlc">캔들 (시·고·저·종 4채널)</option>
              <option value="close">종가만 (추세선)</option>
            </select>
          </div>
          {Slider("패턴 길이 (캔들)", "window", 8, 60, 1)}
          {Slider("예상수익 관찰구간 (캔들)", "calib_horizon", 12, 120, 4)}

          <h2 style={{ marginTop: 18 }}>🔎 패턴 발견/선별</h2>
          {Slider("최대 패턴 수", "max_motifs", 3, 30, 1)}
          {Slider("최소 반복 횟수", "min_occurrences", 2, 12, 1)}
          {Slider("선별 최소 승률", "min_win_rate", 0.3, 0.8, 0.01, (v) => `${Math.round(v * 100)}%`)}
        </>
      )}

      <div className="field" style={{ marginTop: 12 }}>
        <label>시드 자본 ($)</label>
        <input type="number" min={100} max={1000000} step={1000}
          value={params.seed_capital} onChange={(e) => set("seed_capital", Number(e.target.value))} />
      </div>
      <div className="small muted" style={{ marginBottom: 4 }}>
        {precursor
          ? <>익절/손절은 <b>이벤트 정의와 동일한 ATR 배수</b>로 진입 시점마다 자동 계산됩니다.</>
          : <>익절/손절은 <b>패턴마다 자동</b>으로 정해집니다 (과거 움직임 기반). 카드에서 개별 조정 가능.</>}
      </div>

      <h2 style={{ marginTop: 18 }}>💸 거래 비용</h2>
      {Slider("수수료 % (편도)", "fee", 0, 0.003, 0.0001, (v) => `${(v * 100).toFixed(2)}%`)}
      {Slider("슬리피지 % (편도)", "slippage", 0, 0.003, 0.0001, (v) => `${(v * 100).toFixed(2)}%`)}

      <button className="run" onClick={onRun} disabled={loading}>
        {loading ? "실행 중…" : "▶ 백테스트 실행"}
      </button>
    </div>
  );
}
