"use client";
import { useState } from "react";
import { Override, Pattern, pct, signClass } from "@/lib/api";
import { CandleSparkline, ForwardPaths, Sparkline } from "./Charts";

const fmtDT = (ms: number) => {
  const d = new Date(ms);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

interface Props {
  pattern: Pattern;
  color: string;
  override: Override;
  onOverride: (ov: Override) => void;
  rank?: number;   // 추천 점수순 순위 (전조 모드)
}

export default function PatternCard({ pattern, color, override, onOverride, rank }: Props) {
  const p = pattern;
  const enabled = override.enabled ?? p.enabled;
  const tp = override.tp ?? p.tp;
  const sl = override.sl ?? p.sl;
  const weight = override.weight ?? p.weight;
  const [showDetail, setShowDetail] = useState(false);
  const [seg, setSeg] = useState<"train" | "test">("train");
  const dts = p.detail;             // const로 잡아야 클로저 안에서도 타입 내로잉 유지
  const det = dts ? dts[seg] : null;

  return (
    <div className={`pcard ${enabled ? "on" : ""}`}>
      <div className="top">
        <span className="pid" style={{ color }}>
          {rank != null && <span className="muted" style={{ marginRight: 6 }}>#{rank}</span>}
          패턴 P{p.id}
        </span>
        <span style={{ display: "flex", gap: 6 }}>
          <span className="badge" style={{
            color: p.direction === "short" ? "var(--red)" : "var(--green)",
            borderColor: p.direction === "short" ? "rgba(255,92,122,.5)" : "rgba(53,208,127,.5)",
          }}>{p.direction === "short" ? "숏 ▼" : "롱 ▲"}</span>
          {p.selected && <span className="badge sel">자동선별</span>}
          {p.test_pass && <span className="badge" style={{
            color: "var(--green)", borderColor: "rgba(53,208,127,.5)",
          }}>검증 통과</span>}
        </span>
      </div>

      {p.template_ohlc
        ? <CandleSparkline ohlc={p.template_ohlc} />
        : <Sparkline data={p.template} color={color} />}

      {p.lift && (
        <div className="mini" style={{ marginBottom: 6 }}>
          {p.score != null && (<>
            <span className="lbl"><b>추천 점수</b> (학습만)</span>
            <span className={`num ${p.score >= 1 ? "pos" : "neu"}`}>×{p.score.toFixed(2)}</span>
          </>)}
          <span className="lbl">학습 리프트</span>
          <span className={`num ${p.lift.train.lift >= 1.5 ? "pos" : p.lift.train.lift < 1 ? "neg" : "neu"}`}>
            ×{p.lift.train.lift.toFixed(2)}
          </span>
          <span className="lbl">학습 매칭·적중</span>
          <span className="num">{p.lift.train.n_matches}건 · {pct(p.lift.train.precision)}</span>
          <span className="lbl">검증 리프트</span>
          <span className={`num ${p.lift.test.lift >= 1.2 ? "pos" : p.lift.test.lift < 1 ? "neg" : "neu"}`}>
            ×{p.lift.test.lift.toFixed(2)}
          </span>
          <span className="lbl">검증 매칭·적중</span>
          <span className="num">{p.lift.test.n_matches}건 · {pct(p.lift.test.precision)}</span>
          <span className="lbl">기저율 (학습/검증)</span>
          <span className="num">{pct(p.lift.train.base_rate)} / {pct(p.lift.test.base_rate)}</span>
          <span className="lbl">전조 멤버</span>
          <span className="num">{p.n_occurrences}회</span>
          <span className="lbl">전조 길이</span>
          <span className="num">{p.length}캔들</span>
        </div>
      )}

      <div className="mini">
        <span className="lbl">예상 수익률</span>
        <span className={`num ${signClass(p.expected_return)}`}>{pct(p.expected_return)}</span>
        {!p.lift && (<>
          <span className="lbl">학습 등장</span>
          <span className="num">{p.n_occurrences}회</span>
        </>)}
        <span className="lbl">학습 승률</span>
        <span className="num">{pct(p.train.win_rate)}</span>
        <span className="lbl">검증 체결</span>
        <span className="num">{p.test.n_trades}회</span>
        <span className="lbl">검증 승률</span>
        <span className="num">{p.test.n_trades ? pct(p.test.win_rate) : "–"}</span>
        <span className="lbl">검증 수익</span>
        <span className={`num ${signClass(p.test.total_return)}`}>
          {p.test.n_trades ? pct(p.test.total_return) : "–"}
        </span>
      </div>

      {dts && (
        <button className="ghost" style={{ width: "100%", padding: "5px 8px", fontSize: 12, margin: "6px 0" }}
          onClick={() => setShowDetail(!showDetail)}>
          {showDetail ? "▴ 매칭 이후 추세 접기" : "▾ 매칭 이후 추세 보기 (이벤트 스터디)"}
        </button>
      )}

      {showDetail && dts && det && (
        <div style={{ margin: "4px 0 8px" }}>
          <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
            {(["train", "test"] as const).map((s) => (
              <button key={s} className="ghost" onClick={() => setSeg(s)}
                style={{
                  flex: 1, padding: "3px 6px", fontSize: 11.5,
                  borderColor: seg === s ? color : undefined, color: seg === s ? color : undefined,
                }}>
                {s === "train" ? "학습" : "검증"} 매칭 {dts[s].n_total}건
              </button>
            ))}
          </div>
          <div className="small muted" style={{ marginBottom: 4 }}>
            매칭 진입(0%) 이후 {dts.horizon}캔들 수익률 경로.
            <span style={{ color: "#35d07f" }}> 초록=이벤트 적중</span> ·
            <span style={{ color: "#8b94a7" }}> 회색=미적중</span> ·
            <span style={{ color: "#4c8dff" }}> 파랑=중앙값</span> · 점선=TP/SL
            {det.n_total > det.paths.length && ` (${det.n_total}건 중 ${det.paths.length}건 표시)`}
          </div>
          <ForwardPaths detail={det} direction={p.direction} tp={tp} sl={sl} />
          <div style={{
            maxHeight: 130, overflowY: "auto", marginTop: 6,
            border: "1px solid #263149", borderRadius: 6, padding: "2px 6px",
          }}>
            {det.paths.map((m, k) => (
              <div key={k} className="small" style={{
                display: "flex", justifyContent: "space-between", gap: 8, padding: "2px 0",
                borderBottom: k < det.paths.length - 1 ? "1px solid #1c2436" : undefined,
              }}>
                <span className="muted">{fmtDT(m.t_ms)}</span>
                <span style={{ color: m.hit ? "var(--green)" : "#8b94a7" }}>
                  {m.hit ? "● 적중" : "○ 미적중"}
                </span>
                <span className={signClass(m.final)}>{pct(m.final)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <label className="toggle">
        <input type="checkbox" checked={enabled}
          onChange={(e) => onOverride({ ...override, enabled: e.target.checked })} />
        이 패턴으로 매매 (포트폴리오에 포함)
      </label>

      {enabled && (
        <div className="settings">
          <div className="rowf">
            <label>방향</label>
            <select value={override.direction ?? "auto"}
              onChange={(e) => onOverride({ ...override, direction: e.target.value as Override["direction"] })}>
              <option value="auto">자동</option>
              <option value="long">롱 (매수)</option>
              <option value="short">숏 (매도)</option>
            </select>
          </div>
          <div className="rowf">
            <label>익절 %</label>
            <input type="number" min={0.1} max={10} step={0.1}
              value={(tp * 100).toFixed(1)}
              onChange={(e) => onOverride({ ...override, tp: Number(e.target.value) / 100 })} />
            <span className="small muted">자동 {(p.auto_tp * 100).toFixed(1)}</span>
          </div>
          <div className="rowf">
            <label>손절 %</label>
            <input type="number" min={0.1} max={10} step={0.1}
              value={(sl * 100).toFixed(1)}
              onChange={(e) => onOverride({ ...override, sl: Number(e.target.value) / 100 })} />
            <span className="small muted">자동 {(p.auto_sl * 100).toFixed(1)}</span>
          </div>
          <div className="rowf">
            <label>비중</label>
            <input type="number" min={0.1} max={3} step={0.1}
              value={weight}
              onChange={(e) => onOverride({ ...override, weight: Number(e.target.value) })} />
          </div>
        </div>
      )}
    </div>
  );
}
