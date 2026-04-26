"""
============================================================
ARBITRAGE BOT - Phần C v2
============================================================

Bot chính kết nối 4 module theo bài (Mục C.3):
    Module 1 - Data Ingestion: BitgetWS + MEXCRest
    Module 2 - Spread Engine
    Module 3 - Order Logger (CSV)
    Module 4 - Latency Analysis (xem analyze_latency.py)

CHAY:
    cd phan_c_v2
    python arbitrage_bot.py
"""

import sys
import time
import logging
import signal
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

import config
from adapters import BitgetWebSocket, MEXCRestPoller
from spread_engine import SpreadEngine
from logger_csv import OpportunityLogger


Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-10s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("Main")
VN_TZ = timezone(timedelta(hours=7))


class ArbitrageBot:

    def __init__(self):
        self.opp_logger = OpportunityLogger()

        # Spread engine sẽ gọi opp_logger.log() khi có opportunity
        self.engine = SpreadEngine(on_opportunity=self._on_opportunity)

        # 2 source push quote vào engine
        self.bitget = BitgetWebSocket(config.SYMBOLS, on_quote=self.engine.on_quote)
        self.mexc   = MEXCRestPoller(config.SYMBOLS, on_quote=self.engine.on_quote,
                                     poll_interval=config.MEXC_POLL_INTERVAL)

        self.start_time = None
        self.running = False
        signal.signal(signal.SIGINT,  self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _on_opportunity(self, opp: dict):
        """Callback khi có arbitrage opportunity."""
        self.opp_logger.log(opp)
        log.warning(
            f"⚡ {opp['pair']} {opp['direction']} | "
            f"gross={opp['spread_pct_gross']:.4f}% | "
            f"net={opp['spread_pct_net']:.4f}% | "
            f"profit={opp['profit_theoretical_usdt']:.4f} USDT | "
            f"latency={opp['latency_ms']:.1f}ms"
        )

    def _print_stats_loop(self):
        """In thống kê mỗi 30s để biết bot vẫn đang chạy."""
        while self.running:
            time.sleep(30)
            elapsed = time.time() - self.start_time
            log.info(
                f"[STATUS] Uptime={elapsed/60:.1f}m | "
                f"Opportunities logged: {self.opp_logger.count} | "
                f"Symbols tracked: {len(self.engine.state)}"
            )

    def _shutdown(self, *_):
        log.info("Shutdown signal received...")
        self.running = False
        self.bitget.stop()
        self.mexc.stop()
        log.info(f"FINAL: {self.opp_logger.count} opportunities logged")
        sys.exit(0)

    def run(self):
        log.info("=" * 60)
        log.info("ARBITRAGE BOT v2 START")
        log.info(f"Symbols: {config.SYMBOLS}")
        log.info(f"Threshold (net): {config.SPREAD_NET_THRESHOLD_PCT}%")
        log.info(f"Fee est total:   {config.TOTAL_FEE_PCT:.3f}%")
        log.info(f"MEXC poll:       {config.MEXC_POLL_INTERVAL*1000:.0f}ms")
        log.info(f"Bitget source:   WebSocket native")
        log.info("=" * 60)

        self.running = True
        self.start_time = time.time()

        # Khoi dong MEXC REST poller (chay trong thread rieng)
        self.mexc.start()

        # Stats logger
        threading.Thread(target=self._print_stats_loop, daemon=True).start()

        # Bitget WebSocket chay tren main thread (blocking)
        self.bitget.start()


if __name__ == "__main__":
    ArbitrageBot().run()
