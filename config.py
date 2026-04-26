"""
============================================================
CONFIG - Phần C v2 (Cross-Exchange Arbitrage System)
============================================================

Theo đề thi cập nhật (Muc C.3):
    Module 1: Data Ingestion   - WS Bitget + REST 2Hz MEXC
    Module 2: Spread Engine    - tính spread net (sau phi)
    Module 3: Order Logger     - 12 cot CSV theo schema
    Module 4: Latency Analysis - p50/p95/p99
"""

# ============================================================
# 5 CẶP MỤC TIÊU (tối thiếu 5 cặp theo đề Mục C.3)
# ============================================================
# Major (3 cặp thanh khoản cao):
#   BTCUSDT, ETHUSDT, SOLUSDT
# Altcoin thanh khoản thấp (2 cặp - đề Mục C.3):
#   Có thể chọn: DOGEUSDT, XRPUSDT, AVAXUSDT, LTCUSDT, etc.

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "AVAXUSDT","XRPUSDT","LTCUSDT","LINKUSDT","MATICUSDT","ADAUSDT","NVDAUSDT"]

# ============================================================
# PHÍ GIAO DỊCH ƯỚC TÍNH (từ trang phí hiện tại của Bitget và MEXC)
# ============================================================
# Bitget Spot taker: 0.10%
# MEXC Spot taker:   0.05%
# Vòng arbitrage gồm 2 lần taker (mua + bán) trên 2 sàn khác nhau
FEE_BITGET_TAKER = 0.0010   # 0.10%
FEE_MEXC_TAKER   = 0.0005   # 0.05%
TOTAL_FEE_PCT    = (FEE_BITGET_TAKER + FEE_MEXC_TAKER) * 100  # = 0.15% gop

# ============================================================
# NGƯỠNG TRIGGER ARBITRAGE
# ============================================================
# Đề khuyến nghị > 0.2% (Muc C.3)
# Sau khi trừ phí 0.15% -> cần spread_gross > 0.35% mới có lời
# Ta chọn ngưỡng NET = 0.20% -> tức gross > 0.35%
SPREAD_NET_THRESHOLD_PCT = 0.20

# ============================================================
# POLL & PROCESS
# ============================================================
MEXC_POLL_INTERVAL = 0.5     # 0.5s = 2Hz - đúng yêu cầu đề Mục C.3.1

# ============================================================
# LOGGING
# ============================================================
LOG_FILE         = "logs/arbitrage.log"
OPPORTUNITIES_FILE = "logs/opportunities.csv"   # File log mo phong (Muc C.3.3)
LATENCY_FILE     = "logs/latency.csv"            # Latency raw (Muc C.3.4)
