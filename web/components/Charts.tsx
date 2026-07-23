"use client";
import { useMemo } from "react";

// --- 작은 스파크라인: 패턴 '모양'을 보여줌 ---
export function Sparkline({ data, color = "#4c8dff" }: { data: number[]; color?: string }) {
  const W = 240, H = 64, pad = 6;
  const path = useMemo(() => {
    if (!data.length) return "";
    const min = Math.min(...data), max = Math.max(...data);
    const span = max - min || 1;
    return data
      .map((v, i) => {
        const x = pad + (i / (data.length - 1)) * (W - 2 * pad);
        const y = pad + (1 - (v - min) / span) * (H - 2 * pad);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [data]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
    </svg>
  );
}

// --- 캔들 스파크라인: 패턴 '모양'을 캔들로 (ohlc = [시가[], 고가[], 저가[], 종가[]]) ---
export function CandleSparkline({ ohlc }: { ohlc: number[][] }) {
  const W = 240, H = 64, pad = 6;
  const [o, h, l, c] = ohlc;
  const n = c?.length ?? 0;
  if (!n) return null;
  const min = Math.min(...l), max = Math.max(...h);
  const span = max - min || 1;
  const yOf = (v: number) => pad + (1 - (v - min) / span) * (H - 2 * pad);
  const bw = (W - 2 * pad) / n;                 // 캔들 한 칸 너비
  const cw = Math.max(1, Math.min(6, bw * 0.6)); // 몸통 너비
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {c.map((_, i) => {
        const x = pad + (i + 0.5) * bw;
        const up = c[i] >= o[i];
        const color = up ? "#35d07f" : "#ff5c7a";
        const yTop = yOf(Math.max(o[i], c[i]));
        const yBot = yOf(Math.min(o[i], c[i]));
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={yOf(h[i])} y2={yOf(l[i])} stroke={color} strokeWidth={1} />
            <rect x={x - cw / 2} y={yTop} width={cw} height={Math.max(1, yBot - yTop)}
              fill={color} opacity={up ? 0.9 : 0.85} />
          </g>
        );
      })}
    </svg>
  );
}

// --- 매칭 이후 추세(이벤트 스터디): 진입=0% 기준 수익률 경로 겹쳐 그리기 ---
export function ForwardPaths({
  detail, direction, tp, sl,
}: {
  detail: { n_total: number; median: number[]; paths: { hit: boolean; path: number[] }[] };
  direction: "long" | "short";
  tp: number; sl: number;
}) {
  const W = 240, H = 120, padL = 38, padR = 6, padT = 6, padB = 16;
  const maxLen = Math.max(detail.median.length, ...detail.paths.map((p) => p.path.length), 2);
  // 방향 기준 TP/SL 가격선: 롱은 +tp/−sl, 숏은 −tp/+sl
  const tpY = direction === "short" ? -tp : tp;
  const slY = direction === "short" ? sl : -sl;
  let min = Math.min(slY, 0), max = Math.max(tpY, 0);
  detail.paths.forEach((p) => p.path.forEach((v) => { if (v < min) min = v; if (v > max) max = v; }));
  const span = max - min || 1;
  const xOf = (j: number) => padL + (j / (maxLen - 1)) * (W - padL - padR);
  const yOf = (v: number) => padT + (1 - (v - min) / span) * (H - padT - padB);
  const line = (arr: number[]) =>
    arr.map((v, j) => `${j === 0 ? "M" : "L"}${xOf(j).toFixed(1)},${yOf(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {/* 0% 기준선 · TP/SL 가이드 */}
      <line x1={padL} x2={W - padR} y1={yOf(0)} y2={yOf(0)} stroke="#3a4763" strokeWidth={1} strokeDasharray="2 2" />
      <line x1={padL} x2={W - padR} y1={yOf(tpY)} y2={yOf(tpY)} stroke="#35d07f" strokeWidth={0.8} strokeDasharray="3 3" opacity={0.7} />
      <line x1={padL} x2={W - padR} y1={yOf(slY)} y2={yOf(slY)} stroke="#ff5c7a" strokeWidth={0.8} strokeDasharray="3 3" opacity={0.7} />
      {[max, 0, min].map((t, k) => (
        <text key={k} x={padL - 4} y={yOf(t) + 3} fill="#8b94a7" fontSize={9} textAnchor="end">
          {(t * 100).toFixed(1)}%
        </text>
      ))}
      {/* 개별 경로: 이벤트 적중=초록, 미적중=회색 */}
      {detail.paths.map((p, k) => (
        <path key={k} d={line(p.path)} fill="none"
          stroke={p.hit ? "#35d07f" : "#8b94a7"} strokeWidth={0.8} opacity={p.hit ? 0.35 : 0.22} />
      ))}
      {/* 중앙값(전체 매칭 기준) */}
      {detail.median.length > 1 && (
        <path d={line(detail.median)} fill="none" stroke="#4c8dff" strokeWidth={2.2} />
      )}
      <text x={W - padR} y={H - 4} fill="#8b94a7" fontSize={9} textAnchor="end">→ 진입 후 캔들</text>
    </svg>
  );
}

// --- 자산 곡선($): 전략 vs 단순보유 (x축 = 시간, 기준선 = 시드) ---
export function EquityChart({
  strategy, buyHold, seed, timesMs,
}: {
  strategy: { i: number; v: number }[]; buyHold: { i: number; v: number }[];
  seed: number; timesMs: number[];
}) {
  const W = 1000, H = 250, padL = 66, padR = 12, padT = 14, padB = 32;
  const all = [...strategy.map((p) => p.v), ...buyHold.map((p) => p.v), seed];
  const min = Math.min(...all), max = Math.max(...all);
  const span = max - min || 1;
  const iMin = Math.min(strategy[0]?.i ?? 0, buyHold[0]?.i ?? 0);
  const iMax = Math.max(strategy[strategy.length - 1]?.i ?? 1, buyHold[buyHold.length - 1]?.i ?? 1);
  const ispan = iMax - iMin || 1;
  const xOf = (i: number) => padL + ((i - iMin) / ispan) * (W - padL - padR);
  const yOf = (v: number) => padT + (1 - (v - min) / span) * (H - padT - padB);
  const line = (pts: { i: number; v: number }[]) =>
    pts.map((p, k) => `${k === 0 ? "M" : "L"}${xOf(p.i).toFixed(1)},${yOf(p.v).toFixed(1)}`).join(" ");
  const fmt = (v: number) => "$" + Math.round(v).toLocaleString("en-US");
  const fmtT = (ms: number) => {
    const d = new Date(ms); const p = (x: number) => String(x).padStart(2, "0");
    return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  };
  const xticks = Array.from({ length: 5 }, (_, k) => Math.round(iMin + (k / 4) * ispan));
  return (
    <div className="chartwrap">
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", minWidth: 640, height: "auto", display: "block" }}>
        {[max, (max + min) / 2, min].map((t, k) => (
          <g key={k}>
            <line x1={padL} x2={W - padR} y1={yOf(t)} y2={yOf(t)} stroke="#263149" strokeWidth={1} />
            <text x={padL - 6} y={yOf(t) + 3} fill="#8b94a7" fontSize={11} textAnchor="end">{fmt(t)}</text>
          </g>
        ))}
        {xticks.map((i, k) => (
          <text key={`x${k}`} x={xOf(i)} y={H - 12} fill="#8b94a7" fontSize={10.5}
            textAnchor={k === 0 ? "start" : k === 4 ? "end" : "middle"}>
            {fmtT(timesMs[Math.min(timesMs.length - 1, Math.max(0, i))])}
          </text>
        ))}
        <line x1={padL} x2={W - padR} y1={yOf(seed)} y2={yOf(seed)} stroke="#3a4763" strokeWidth={1} strokeDasharray="2 2" />
        <path d={line(buyHold)} fill="none" stroke="#8b94a7" strokeWidth={1.4} strokeDasharray="4 3" />
        <path d={line(strategy)} fill="none" stroke="#4c8dff" strokeWidth={2} />
      </svg>
    </div>
  );
}
