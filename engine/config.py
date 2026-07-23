"""
MVP 설정값 한 곳 모음.
여기 숫자들을 바꿔가며 실험하면 됩니다. (기획서 10번 "다음에 정할 것들")
"""
from pathlib import Path

# --- 경로 ---
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

# --- 데이터 ---
SYMBOL = "BTC/USDT"      # 검증 대상 종목 (MVP는 1종목)
TIMEFRAME = "5m"         # 분봉 단위
CANDLES = 50000          # 받아올 캔들 개수 (5m * 50000 ≈ 약 6개월) — 전조 모드는 이벤트가 수백 개 필요
FORCE_REFRESH = False    # True면 캐시 무시하고 새로 받음

# --- 모드 ---
MODE = "precursor"       # "precursor"(v1.5 급등·급락 전조 발견) | "motif"(v1 반복 모양 발견)
MOTIF_MAX_CANDLES = 20000  # motif 모드는 O(n²)라 이 이상이면 거부(서버 멈춤 방지)

# --- v1.5 전조(precursor) 모드 ---
# ★ 이벤트 정의는 원칙에서 역산해 정하고 고정한다. 결과 보고 바꾸면 과최적화. ★
# 원칙(2026-07-21 확정): TP ≥ 왕복비용(0.30%)×5 = 1.5%.
#   5m ATR 중앙값 ~0.15% → TP=10×ATR(≈1.5%), SL=5×ATR(손익비 2:1), K=144(√K≥10 도달 가능성).
#   (구 정의 3×/1.5×/K=24는 TP 0.46%로 수수료가 65%를 먹어 구조적으로 승산 없음이 확인됨)
ATR_PERIOD = 14          # ATR 기간
EVENT_HORIZON = 144      # 이벤트 판정 구간 K (5m*144 = 12시간)
EVENT_TP_ATR = 10.0      # 급등/급락: ±10×ATR 에 먼저 도달해야 이벤트 (≈1.5%)
EVENT_SL_ATR = 5.0       # 그 전에 반대로 5×ATR 가면 무효 (손절선)
PRECURSOR_LEN_MIN = 24   # 전조 길이 최소 (5m*24 = 2시간)
PRECURSOR_LEN_MAX = 96   # 전조 길이 최대 (5m*96 = 8시간). 최소에서 2배씩 증가: 24→48→96
                         # (촘촘히 다 돌리면 다중 비교로 우연 발견 확률↑ — 스케일만 다양화)
USE_VOLUME = True        # 전조 채널에 로그 거래량 포함 (OHLC+V 5채널)
N_CLUSTERS = 6           # 방향당 클러스터 수 (많이 만들수록 다중 비교 위험↑)
MIN_CLUSTER_SIZE = 10    # 이보다 작은 클러스터는 폐기
MIN_TRAIN_MATCHES = 30   # 학습 리프트 판단 최소 매칭 수 (멤버 제외)
MIN_TEST_MATCHES = 15    # 검증 리프트 판단 최소 매칭 수
MIN_LIFT_TRAIN = 1.5     # 학습구간 리프트 기준 (이상이어야 자동선별)
MIN_LIFT_TEST = 1.2      # 검증구간 리프트 기준 (넘으면 '검증 통과' 배지)

# --- 패턴 엔진 (v1 motif 모드) ---
PATTERN_BASIS = "ohlc"   # "ohlc"(시가·고가·저가·종가 4채널) | "close"(종가만)
ALLOW_SHORT = True       # 하락 예고 패턴은 숏으로 거래
WINDOW = 24              # 패턴 길이(캔들 수). 5m*24 = 2시간짜리 모양
CALIB_HORIZON = 48       # 패턴의 TP/SL·예상수익 산출용 관찰 구간(캔들). 실매매엔 강제청산 없음
SEED_CAPITAL = 10000     # 시드 자본($)
MAX_MOTIFS = 15          # 발견할 패턴 후보 최대 개수
MIN_OCCURRENCES = 4      # 학습구간에서 최소 이만큼 반복돼야 후보로 인정
MAX_MATCHES = 40         # 한 패턴당 학습구간에서 모을 최대 등장 횟수
MOTIF_CUTOFF_PCTL = 45   # 이 백분위 이하로 닮은 구간만 같은 패턴으로 인정(낮을수록 엄격)

# --- 채점 / 선별 ---
MIN_WIN_RATE = 0.55      # 이 승률 이상인 패턴만 실전 투입
MIN_AVG_RETURN = 0.0     # 수수료 차감 후 기대수익이 이 값보다 커야 함

# --- 거래 비용 (백테스트 현실화의 핵심) ---
FEE = 0.001              # 편도 수수료 0.1% (바이낸스 spot taker 기준)
SLIPPAGE = 0.0005        # 편도 슬리피지 0.05% 가정 (주문가와 실제 체결가 차이)

# --- 백테스트 ---
TRAIN_RATIO = 0.7        # 앞 70%로 패턴 발견, 뒤 30%로 검증(처음 보는 데이터)
