"""
============================================================
MEXC SPOT REST POLLER - Phan C v2
============================================================

REST polling 2Hz cho MEXC Spot best bid/ask.
TAI SAO REST thay vi WebSocket?
    MEXC v3 WebSocket da chuyen sang Protocol Buffers (Protobuf)
    sau Aug 2025, can thu vien protobuf parse phuc tap. De don gian
    va dang tin cay, ta dung REST endpoint
    /api/v3/ticker/bookTicker poll 500ms (2Hz - dung yeu cau de bai).

    Thuc te: REST 2Hz cho MEXC + WebSocket cho Bitget la trade-off
    hop ly nhat ve do don gian va kha thi.

Endpoint: https://api.mexc.com/api/v3/ticker/bookTicker?symbol=BTCUSDT
Khong can API key.
"""

import time
import threading
import logging
from typing import Callable
import requests


log = logging.getLogger("MEXCRest")


class MEXCRestPoller:
    """REST poller cho MEXC Spot - poll 2Hz."""

    BASE_URL = "https://api.mexc.com/api/v3/ticker/bookTicker"

    def __init__(self, symbols: list[str], on_quote: Callable[[dict], None],
                 poll_interval: float = 0.5):
        """
        symbols: ['BTCUSDT', 'ETHUSDT', ...]
        on_quote: callback giong BitgetWebSocket
        poll_interval: giay giua 2 lan poll (mac dinh 0.5s = 2Hz)
        """
        self.symbols       = symbols
        self.on_quote      = on_quote
        self.poll_interval = poll_interval
        self.running       = False
        self.session       = requests.Session()
        self._thread       = None

    def _poll_once(self):
        """Lay ticker cua tat ca symbol trong 1 request."""
        try:
            # Endpoint khong co param symbol -> tra ve TAT CA -> filter
            r = self.session.get(self.BASE_URL, timeout=5)
            ws_receive_ts = time.time()
            data = r.json()
            # data la list dict {symbol, bidPrice, bidQty, askPrice, askQty}
            wanted = set(self.symbols)
            for d in data:
                if d.get("symbol") not in wanted:
                    continue
                try:
                    quote = {
                        "exchange":      "MEXC",
                        "symbol":        d["symbol"],
                        "bid":           float(d["bidPrice"]),
                        "bid_size":      float(d.get("bidQty", 0)),
                        "ask":           float(d["askPrice"]),
                        "ask_size":      float(d.get("askQty", 0)),
                        "ws_receive_ts": ws_receive_ts,
                    }
                    self.on_quote(quote)
                except (KeyError, ValueError) as e:
                    log.warning(f"MEXC parse error: {e}")
        except Exception as e:
            log.error(f"MEXC poll error: {e}")

    def _loop(self):
        log.info(f"MEXC REST poll start ({self.poll_interval*1000:.0f}ms interval)")
        while self.running:
            self._poll_once()
            time.sleep(self.poll_interval)

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
