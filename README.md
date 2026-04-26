# Phần C: Cross-Exchange-Arbitrage-System
**Đề thi giữa kỳ Fintech — Phần nhóm (5-6 sinh viên)**

---

## 1. Kiến trúc hệ thống — 4 Module theo Mục C.3

```
┌────────────────────────────────────────────────────────────┐
│                  ARBITRAGE SYSTEM v2                        │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  Module 1: DATA INGESTION                                    │
│    Bitget WebSocket  ──→  ┐                                 │
│    MEXC REST 2Hz     ──→  ├──→ on_quote callback           │
│                            │                                 │
│  Module 2: SPREAD ENGINE   │                                 │
│    SpreadEngine.on_quote() ┘                                │
│      └→ tính spread_gross 2 hướng                           │
│      └→ trừ phí ước tính → spread_net                       │
│      └→ filter: spread_net > 0.20%                          │
│                                                              │
│  Module 3: ORDER LOGGER                                      │
│    opportunities.csv  ←  log với 12 cột schema             │
│    latency.csv        ←  raw timestamps                     │
│                                                              │
│  Module 4: LATENCY ANALYSIS  (analyze_latency.py)            │
│    p50 / p95 / p99 + biểu đồ + simulation                   │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

## 2. Cấu trúc thư mục

```
phan_c_v2/
├── adapters/
│   ├── __init__.py
│   ├── bitget_ws.py        # Bitget WebSocket (top 5 ticker)
│   └── mexc_rest.py        # MEXC REST polling 2Hz
├── spread_engine.py        # Module 2 - tính spread + filter
├── logger_csv.py           # Module 3 - ghi 2 file CSV
├── arbitrage_bot.py        # Bot chính - liên kết 4 module
├── analyze_latency.py      # Module 4 - post-mortem analysis
├── config.py               # 5 cặp + threshold + fees
└── logs/                   # opportunities.csv, latency.csv, ...
```

## 3. Lý do quyết định kỹ thuật

### 3.1. Tại sao Bitget dùng WebSocket nhưng MEXC dùng REST?

Đề yêu cầu **WebSocket ưu tiên, REST fallback** — chúng tôi tuân thủ tinh thần đó nhưng có lý do kỹ thuật để chọn hybrid:

- **Bitget**: WebSocket public v2 dùng JSON đơn giản, kết nối ổn định, không cần thư viện đặc biệt → dùng WebSocket
- **MEXC**: WebSocket v3 đã chuyển sang **Protocol Buffers** (Protobuf) sau Aug 2025 (theo announcement chính thức). Việc dùng WS MEXC sẽ cần thư viện protobuf phức tạp, dễ break khi MEXC update schema → chọn **REST polling 500ms (2Hz)**.

REST 2Hz vẫn đáp ứng đúng yêu cầu **≥2 snapshot/giây** (Mục C.3.1). Trade-off này là **quyết định kỹ sư** ưu tiên độ tin cậy hơn tốc độ tuyệt đối.

### 3.2. Tại sao threshold spread_net = 0.20%?

Theo Mục C.3.2 đề khuyến nghị **> 0.2%**. Chúng tôi tính chi phí thực tế:
- Phí Bitget Spot taker: **0.10%**
- Phí MEXC Spot taker: **0.05%**
- Tổng phí 1 vòng arbitrage: **0.15%**

Để có lãi sau phí, spread_gross phải > 0.15%. Chọn ngưỡng **net 0.20%** = **gross > 0.35%** đảm bảo:
- Có **biên lợi nhuận 0.20%** sau phí
- Đủ buffer cho slippage và funding khi triển khai thật

### 3.3. Tại sao chọn 5 cặp này?

Theo Mục C.3.1 đề yêu cầu 3 majors + 2 altcoin:
- **Majors**: BTC, ETH, SOL — thanh khoản cao, spread thường nhỏ nhưng khối lượng lớn
- **Altcoin thanh khoản thấp**: DOGE, AVAX — spread thường lớn hơn (cơ hội arbitrage cao) nhưng size khớp nhỏ

## 4. Setup & Chạy

### Cài thư viện
```bash
pip install websocket-client requests pandas numpy matplotlib
```

### Khởi động bot
```bash
cd phan_c_v2
python arbitrage_bot.py
```

Output mẫu:
```
[12:21:44] [Main] ARBITRAGE BOT v2 START
[12:21:44] [Main] Symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'AVAXUSDT']
[12:21:44] [BitgetWS]  Bitget WS connected
[12:21:45] [MEXCRest]  MEXC REST poll start (500ms interval)
[12:22:13] [Main] ⚡ DOGEUSDT BUY_MEXC_SELL_BITGET | gross=0.4123% | net=0.2623% | profit=12.34 USDT | latency=87.5ms
```

### Phân tích sau khi chạy
```bash
python analyze_latency.py
```

Output sẽ in p50/p95/p99 + tạo `logs/latency_histogram.png` + `logs/latency_report.txt`.

## 5. Schema chi tiết file log

### `opportunities.csv` (Mục C.3.3)

| Cột | Loại | Ý nghĩa |
|-----|------|---------|
| timestamp_detected | str | ISO 8601 + millisecond + TZ +07:00 |
| pair | str | VD `BTCUSDT` |
| exchange_buy | str | `BITGET` hoặc `MEXC` |
| price_ask | float | Ask của sàn mua |
| size_available_buy | float | Khối lượng có sẵn tại Ask |
| exchange_sell | str | Sàn được bán |
| price_bid | float | Bid sàn bán |
| size_available_sell | float | Khối lượng tại Bid |
| spread_pct_gross | float | Spread trước phí (%) |
| fee_est_pct | float | Tổng phí ước tính 2 sàn (%) |
| spread_pct_net | float | Spread ròng sau phí |
| notional_simulated_usdt | float | min(size_buy, size_sell) × price |
| profit_theoretical_usdt | float | notional × spread_net / 100 |
| latency_ms | float | End-to-end latency |

### `latency.csv` (Mục C.3.4)

| Cột | Ý nghĩa |
|-----|---------|
| timestamp_iso | Thời điểm phát hiện |
| pair | Cặp |
| ws_receive_ts | epoch giây — khi nhận quote từ sàn |
| detected_ts | epoch giây — khi spread engine xử lý |
| log_written_ts | epoch giây — khi ghi xong CSV |
| latency_ws_to_log_ms | Total latency (ws → log) |
| latency_detect_to_log_ms | Internal processing latency |

## 6. Phân tích báo cáo (Mục C.4)

Sau khi chạy `analyze_latency.py`, bạn sẽ có:

### Latency profile
- **p50 / p95 / p99** — tìm bottleneck đâu
- Histogram + boxplot để xem phân phối

### Profit analysis
- Tổng profit lý thuyết
- Phân phối theo cặp (cặp nào nhiều cơ hội nhất)
- Phân phối theo spread (% cơ hội ở vùng spread nào)

### Simulation: latency tăng gấp đôi
Giả thuyết decay 0.005% / ms (bảo thủ) → tính được:
- Bao nhiêu % cơ hội biến mất
- Bao nhiêu % profit lý thuyết bị bòn rút

→ Đây là core insight của Phần C: **không phải đoán giỏi, mà là hệ thống nhanh hơn**.

## 7. Minh chứng nộp thầy (Mục III.3)

| # | Tên file | Mô tả |
|---|---------|-------|
| 1 | `phan_c_v2/` (source code) | README + 4 module + analysis script |
| 2 | `logs/opportunities.csv` | File log core của Phần C |
| 3 | `logs/latency.csv` | Raw latency timestamps |
| 4 | `logs/latency_report.txt` | Auto-generated report |
| 5 | `logs/latency_histogram.png` | Biểu đồ phân phối |
| 6 | Screenshot terminal đang chạy | ≥1 ảnh khi bot live |
| 7 | Screenshot dashboard real-time | Có thể chụp tab MEXC + Bitget cùng lúc |
  - 1 người check code quality + README
  - 1-2 người làm support cho Phần A/B của các thành viên
