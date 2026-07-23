"use client";
import { useEffect, useMemo, useRef, useState } from "react";

export interface TradeMark {
  entry: number;
  exit: number;
  dir: "long" | "short";
  color: string;
}

export interface EventPoint {
  i: number;
  dir: "up" | "down";
}

const W = 1000, H = 320, padL = 62, padR = 14, padT = 12, padB = 34;
const plotW = W - padL - padR, plotH = H - padT - padB;

function fmtTime(ms: number): string {
  const d = new Date(ms);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function PriceChart({
  close, timesMs, splitIndex, trades, events = [],
}: {
  close: number[]; timesMs: number[]; splitIndex: number; trades: TradeMark[];
  events?: EventPoint[];
}) {
  const n = close.length;
  const [view, setView] = useState<[number, number]>([0, Math.max(1, n - 1)]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; lo: number; hi: number } | null>(null);

  useEffect(() => { setView([0, Math.max(1, n - 1)]); }, [n]);

  const [lo, hi] = view;
  const count = Math.max(2, hi - lo);
  const xOf = (i: number) => padL + ((i - lo) / count) * plotW;

  const { pmin, pmax } = useMemo(() => {
    let a = Infinity, b = -Infinity;
    for (let i = Math.max(0, Math.floor(lo)); i <= Math.min(n - 1, Math.ceil(hi)); i++) {
      const v = close[i]; if (v < a) a = v; if (v > b) b = v;
    }
    return { pmin: a, pmax: b };
  }, [lo, hi, close, n]);
  const pspan = (pmax - pmin) || 1;
  const yOf = (v: number) => padT + (1 - (v - pmin) / pspan) * plotH;

  const path = useMemo(() => {
    const step = Math.max(1, Math.floor(count / plotW));
    let d = "";
    for (let i = Math.max(0, Math.floor(lo)); i <= Math.min(n - 1, Math.ceil(hi)); i += step)
      d += `${d ? "L" : "M"}${xOf(i).toFixed(1)},${yOf(close[i]).toFixed(1)} `;
    return d;
  }, [lo, hi, pmin, pmax, close, n]);

  const visibleTrades = trades.filter((t) => t.exit >= lo - 1 && t.entry <= hi + 1);

  // 이벤트(급등/급락 시작점) 마커: 화면에 너무 많으면 솎아서 표시
  const visibleEvents = useMemo(() => {
    const vis = events.filter((e) => e.i >= lo && e.i <= hi);
    const step = Math.max(1, Math.ceil(vis.length / 400));
    return vis.filter((_, k) => k % step === 0);
  }, [events, lo, hi]);

  // 휠 확대/축소 (커서 중심)
  useEffect(() => {
    const el = wrapRef.current; if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const scale = rect.width / W;
      const frac = Math.min(1, Math.max(0, (e.clientX - rect.left - padL * scale) / (plotW * scale)));
      const center = lo + frac * count;
      const nc = Math.min(n - 1, Math.max(30, count * (e.deltaY < 0 ? 0.85 : 1.18)));
      let nlo = center - frac * nc, nhi = nlo + nc;
      if (nlo < 0) { nhi -= nlo; nlo = 0; }
      if (nhi > n - 1) { nlo -= nhi - (n - 1); nhi = n - 1; }
      setView([Math.max(0, nlo), Math.min(n - 1, nhi)]);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [lo, hi, count, n]);

  const onDown = (e: React.MouseEvent) => { drag.current = { x: e.clientX, lo, hi }; };
  const onMove = (e: React.MouseEvent) => {
    if (!drag.current || !wrapRef.current) return;
    const rect = wrapRef.current.getBoundingClientRect();
    const dc = -((e.clientX - drag.current.x) / (plotW * (rect.width / W))) * count;
    let nlo = drag.current.lo + dc, nhi = drag.current.hi + dc;
    if (nlo < 0) { nhi -= nlo; nlo = 0; }
    if (nhi > n - 1) { nlo -= nhi - (n - 1); nhi = n - 1; }
    setView([Math.max(0, nlo), Math.min(n - 1, nhi)]);
  };
  const onUp = () => { drag.current = null; };

  const yticks = [pmax, (pmax + pmin) / 2, pmin];
  const xticks = Array.from({ length: 5 }, (_, k) => Math.round(lo + (k / 4) * count));
  const splitVisible = splitIndex >= lo && splitIndex <= hi;

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "center", flexWrap: "wrap" }}>
        <span className="small muted">스크롤=확대/축소 · 드래그=이동</span>
        <button className="ghost" style={{ padding: "3px 8px", fontSize: 12 }} onClick={() => setView([0, n - 1])}>전체</button>
        <button className="ghost" style={{ padding: "3px 8px", fontSize: 12 }} onClick={() => setView([splitIndex, n - 1])}>검증구간</button>
        <span className="small" style={{ marginLeft: "auto" }}>
          <span style={{ color: "var(--green)" }}>▲ BUY</span> · <span style={{ color: "var(--red)" }}>▼ SELL</span>
          {events.length > 0 && (
            <> · <span style={{ color: "#35d07f" }}>●급등</span>/<span style={{ color: "#ff5c7a" }}>●급락</span> 이벤트</>
          )}
        </span>
      </div>
      <div ref={wrapRef} className="chartwrap" style={{ cursor: drag.current ? "grabbing" : "grab", userSelect: "none" }}
        onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", minWidth: 640, height: "auto", display: "block" }}>
          {splitVisible && (
            <rect x={xOf(splitIndex)} y={padT} width={Math.max(0, W - padR - xOf(splitIndex))} height={plotH} fill="rgba(76,141,255,0.06)" />
          )}
          {yticks.map((t, k) => (
            <g key={k}>
              <line x1={padL} x2={W - padR} y1={yOf(t)} y2={yOf(t)} stroke="#263149" strokeWidth={1} />
              <text x={padL - 6} y={yOf(t) + 3} fill="#8b94a7" fontSize={11} textAnchor="end">{t.toFixed(0)}</text>
            </g>
          ))}
          {xticks.map((i, k) => (
            <text key={k} x={xOf(i)} y={H - 12} fill="#8b94a7" fontSize={10.5}
              textAnchor={k === 0 ? "start" : k === 4 ? "end" : "middle"}>
              {fmtTime(timesMs[Math.min(n - 1, Math.max(0, i))])}
            </text>
          ))}
          {splitVisible && (
            <>
              <line x1={xOf(splitIndex)} x2={xOf(splitIndex)} y1={padT} y2={padT + plotH} stroke="#ff5c7a" strokeWidth={1} strokeDasharray="4 3" />
              <text x={xOf(splitIndex) + 4} y={padT + 12} fill="#ff5c7a" fontSize={11}>검증 시작</text>
            </>
          )}
          {/* 이벤트 시작점: 가격선 위 작은 점 (급등=초록, 급락=빨강) */}
          {visibleEvents.map((e, k) => (
            <circle key={`e${k}`} cx={xOf(e.i)} cy={yOf(close[e.i] ?? pmin)} r={2.2}
              fill={e.dir === "up" ? "#35d07f" : "#ff5c7a"} opacity={0.55} />
          ))}
          <path d={path} fill="none" stroke="#8b94a7" strokeWidth={1.1} />
          {/* 거래 스팬 선 (진입→청산) */}
          {visibleTrades.map((t, k) => (
            <line key={`s${k}`} x1={xOf(t.entry)} y1={yOf(close[t.entry] ?? pmin)}
              x2={xOf(t.exit)} y2={yOf(close[t.exit] ?? pmin)}
              stroke={t.dir === "long" ? "rgba(53,208,127,.4)" : "rgba(255,92,122,.4)"} strokeWidth={1} />
          ))}
          {/* BUY/SELL 마커: 롱=진입BUY·청산SELL, 숏=진입SELL·청산BUY */}
          {visibleTrades.flatMap((t, k) => {
            const pts = [
              { i: t.entry, buy: t.dir === "long" },
              { i: t.exit, buy: t.dir === "short" },
            ];
            return pts.map((m, j) => {
              const cx = xOf(m.i), base = yOf(close[m.i] ?? pmin), s = 4;
              const cy = base + (m.buy ? 9 : -9);
              const tri = m.buy
                ? `${cx - s},${cy + s} ${cx + s},${cy + s} ${cx},${cy - s}`
                : `${cx - s},${cy - s} ${cx + s},${cy - s} ${cx},${cy + s}`;
              return <polygon key={`m${k}-${j}`} points={tri} fill={m.buy ? "#35d07f" : "#ff5c7a"} stroke="#0b0e14" strokeWidth={0.5} />;
            });
          })}
        </svg>
      </div>
    </div>
  );
}
