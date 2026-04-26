"""
============================================================
LOGGER - Phan C v2
============================================================

Ghi 2 file CSV theo dung yeu cau de thi:
    1. opportunities.csv - schema 12 cot theo Muc C.3.3
    2. latency.csv       - cac timestamp raw theo Muc C.3.4
"""

import csv
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

import config


VN_TZ = timezone(timedelta(hours=7))


# Schema theo dung de bai Muc C.3.3
OPP_COLS = [
    "timestamp_detected",       # ISO 8601 + millisecond
    "pair",
    "exchange_buy",
    "price_ask",
    "size_available_buy",
    "exchange_sell",
    "price_bid",
    "size_available_sell",
    "spread_pct_gross",
    "fee_est_pct",
    "spread_pct_net",
    "notional_simulated_usdt",
    "profit_theoretical_usdt",
    "latency_ms",
]

# Latency raw theo Muc C.3.4
LAT_COLS = [
    "timestamp_iso",
    "pair",
    "ws_receive_ts",     # epoch sec
    "detected_ts",       # epoch sec
    "log_written_ts",    # epoch sec
    "latency_ws_to_log_ms",
    "latency_detect_to_log_ms",
]


class OpportunityLogger:
    """Ghi co hoi vao opportunities.csv. Thread-safe."""

    def __init__(self, opp_path: str = None, lat_path: str = None):
        self.opp_path = opp_path or config.OPPORTUNITIES_FILE
        self.lat_path = lat_path or config.LATENCY_FILE
        self.lock     = threading.Lock()
        Path("logs").mkdir(exist_ok=True)
        self._init_file(self.opp_path, OPP_COLS)
        self._init_file(self.lat_path, LAT_COLS)
        self.count = 0

    @staticmethod
    def _init_file(path: str, cols: list):
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(cols)

    @staticmethod
    def _iso_with_ms(epoch_sec: float) -> str:
        """Tao ISO 8601 voi milisecond va timezone +07:00."""
        dt = datetime.fromtimestamp(epoch_sec, tz=VN_TZ)
        # ISO format chuan voi millisecond
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(dt.microsecond/1000):03d}+07:00"

    def log(self, opp: dict):
        ts_iso = self._iso_with_ms(opp["timestamp_detected"])

        opp_row = [
            ts_iso,
            opp["pair"],
            opp["exchange_buy"],
            f"{opp['price_ask']:.8f}",
            f"{opp['size_available_buy']:.8f}",
            opp["exchange_sell"],
            f"{opp['price_bid']:.8f}",
            f"{opp['size_available_sell']:.8f}",
            f"{opp['spread_pct_gross']:.6f}",
            f"{opp['fee_est_pct']:.6f}",
            f"{opp['spread_pct_net']:.6f}",
            f"{opp['notional_simulated_usdt']:.4f}",
            f"{opp['profit_theoretical_usdt']:.6f}",
            f"{opp['latency_ms']:.3f}",
        ]

        lat_row = [
            ts_iso, opp["pair"],
            f"{opp['ws_receive_ts']:.6f}",
            f"{opp['timestamp_detected']:.6f}",
            f"{opp['log_written_ts']:.6f}",
            f"{opp['latency_ms']:.3f}",
            f"{(opp['log_written_ts'] - opp['timestamp_detected']) * 1000:.3f}",
        ]

        with self.lock:
            with open(self.opp_path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(opp_row)
            with open(self.lat_path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(lat_row)
            self.count += 1
