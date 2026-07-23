// Python FastAPI 엔진과 통신하는 클라이언트 + 타입 정의

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type Basis = "ohlc" | "close";
export type Direction = "long" | "short" | "auto";
export type Mode = "precursor" | "motif";

export interface Params {
  mode: Mode;
  symbol: string;
  timeframe: string;
  candles: number;
  basis: Basis;
  allow_short: boolean;
  window: number;
  calib_horizon: number;
  seed_capital: number;
  train_ratio: number;
  fee: number;
  slippage: number;
  max_motifs: number;
  min_occurrences: number;
  max_matches: number;
  cutoff_pctl: number;
  min_win_rate: number;
  min_avg_return: number;
  // v1.5 전조(precursor) 모드
  atr_period: number;
  event_horizon: number;
  event_tp_atr: number;
  event_sl_atr: number;
  precursor_len_min: number;
  precursor_len_max: number;
  use_volume: boolean;
  n_clusters: number;
  min_cluster_size: number;
  min_train_matches: number;
  min_test_matches: number;
  min_lift_train: number;
  min_lift_test: number;
  default_weight: number;
}

export interface Override {
  tp?: number;
  sl?: number;
  weight?: number;
  enabled?: boolean;
  direction?: Direction;
}

export interface Trade {
  entry_idx: number;
  exit_idx: number;
  ret: number;
  reason: "TP" | "SL" | "END";
  direction: "long" | "short";
}

// 리프트 = 매칭 후 이벤트 확률(precision) ÷ 기저율(base_rate)
export interface LiftStats {
  n_matches: number;
  n_hits: number;
  precision: number;
  base_rate: number;
  lift: number;
}

export interface TradeStats {
  n_trades: number;
  win_rate: number;
  avg_return: number;
  total_return: number;
}

export interface Pattern {
  id: number;
  seed_index: number;
  length: number;
  n_occurrences: number;
  template: number[];
  // [시가[], 고가[], 저가[], 종가[]] — 공통 z-정규화(캔들 형태 보존). close 기준 모드면 null
  template_ohlc?: number[][] | null;
  direction: "long" | "short";
  train: TradeStats;
  test: TradeStats & { trades: Trade[] };
  selected: boolean;
  enabled: boolean;
  tp: number;
  sl: number;
  weight: number;
  expected_return: number;
  auto_tp: number;
  auto_sl: number;
  auto_direction: "long" | "short";
  // 전조 모드에서만 존재
  test_pass?: boolean;
  // 추천 점수 = 학습 적중률의 Wilson 95% 신뢰하한 ÷ 기저율 (검증 데이터 미사용)
  score?: number;
  lift?: { train: LiftStats; test: LiftStats };
  detail?: PatternDetail;
}

// 매칭 이후 추세(이벤트 스터디) — 진입 대비 수익률 경로
export interface MatchPath {
  i: number;
  t_ms: number;
  hit: boolean;      // 이벤트 적중 여부
  final: number;     // horizon 끝(또는 데이터 끝) 수익률
  path: number[];    // 다운샘플된 수익률 경로 (진입=0)
}

export interface ForwardDetail {
  n_total: number;   // 전체 매칭 수 (paths는 최대 50개 샘플)
  median: number[];  // 전체 매칭 기준 중앙값 경로
  paths: MatchPath[];
}

export interface PatternDetail {
  horizon: number;
  train: ForwardDetail;
  test: ForwardDetail;
}

export interface EventMark {
  i: number;
  t_ms: number;
  dir: "up" | "down";
}

export interface Labeling {
  n_events_up_train: number;
  n_events_down_train: number;
  base_up_train: number;
  base_down_train: number;
  base_up_test: number;
  base_down_test: number;
  atr_frac_median: number;
}

export interface EquityPoint { i: number; t_ms: number; equity: number; }

export interface Portfolio {
  seed_capital: number;
  final_equity: number;
  n_patterns_discovered: number;
  n_patterns_enabled: number;
  n_trades: number;
  win_rate: number;
  total_return: number;
  buy_hold_return: number;
  buy_hold_final: number;
  max_drawdown: number;
  equity_curve: EquityPoint[];
}

export const usd = (x: number) =>
  "$" + x.toLocaleString("en-US", { maximumFractionDigits: 0 });

export interface BacktestResult {
  ok: boolean;
  error?: string;
  params: Params;
  data: {
    symbol: string;
    timeframe: string;
    n_candles: number;
    split_index: number;
    times_ms: number[];
    close: number[];
  };
  patterns: Pattern[];
  portfolio: Portfolio;
  events: EventMark[];
  labeling: Labeling | null;
}

export interface DefaultsResponse {
  defaults: Params;
  timeframes: string[];
  symbols: string[];
}

export async function getDefaults(): Promise<DefaultsResponse> {
  const r = await fetch(`${API_BASE}/api/defaults`);
  if (!r.ok) throw new Error(`defaults 요청 실패 (${r.status})`);
  return r.json();
}

export async function runBacktest(
  params: Partial<Params>,
  overrides: Record<string, Override>
): Promise<BacktestResult> {
  const r = await fetch(`${API_BASE}/api/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...params, overrides }),
  });
  if (!r.ok) throw new Error(`backtest 요청 실패 (${r.status})`);
  return r.json();
}

export const pct = (x: number) => `${(x * 100).toFixed(2)}%`;
export const signClass = (x: number) => (x > 0 ? "pos" : x < 0 ? "neg" : "neu");
