"""
CLI 실행 진입점 (웹 UI 없이 콘솔로 빠르게 확인할 때).
  python -m engine.main

* 웹 UI로 보려면: README의 '실행법' 참고 (FastAPI + Next.js).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from . import config, service


def _pct(x: float) -> str:
    return f"{x * 100:+.2f}%"


def main() -> None:
    print("=" * 56)
    print(f" 크립토 패턴 봇 — {config.SYMBOL} {config.TIMEFRAME}")
    print("=" * 56)
    r = service.run()
    d, pf = r["data"], r["portfolio"]
    print(f"데이터: {d['n_candles']}개 캔들, 검증 시작 index={d['split_index']}")
    lab = r.get("labeling")
    if lab:
        print(f"학습 이벤트: 급등 {lab['n_events_up_train']}개 / 급락 {lab['n_events_down_train']}개  "
              f"(기저율 up {lab['base_up_train']*100:.1f}% · down {lab['base_down_train']*100:.1f}%)")
    print(f"발견 패턴: {pf['n_patterns_discovered']}개 / 자동선별·활성: {pf['n_patterns_enabled']}개")
    print(f"검증 체결: {pf['n_trades']}회, 승률 {_pct(pf['win_rate'])}")
    print(f"전략 누적수익 {_pct(pf['total_return'])}  vs  단순보유 {_pct(pf['buy_hold_return'])}")
    print(f"최대낙폭(MDD) {_pct(pf['max_drawdown'])}")
    print("\n패턴별:")
    for p in r["patterns"]:
        line = (f"  P{p['id']:<2} {'숏' if p['direction']=='short' else '롱'} "
                f"L={p['length']:<3} 멤버 {p['n_occurrences']:>3}회  검증 {p['test']['n_trades']:>3}건  "
                f"선별={'O' if p['selected'] else 'X'}")
        if p.get("lift"):
            tr, te = p["lift"]["train"], p["lift"]["test"]
            line += (f"  점수 ×{p['score']:.2f}"
                     f"  학습리프트 ×{tr['lift']:.2f}({tr['n_matches']}건)"
                     f"  검증리프트 ×{te['lift']:.2f}({te['n_matches']}건)"
                     f"  검증통과={'O' if p.get('test_pass') else 'X'}")
        print(line)
    print("\n💡 웹 UI로 조작·시각화하려면 README의 실행법을 참고하세요.")


if __name__ == "__main__":
    main()
