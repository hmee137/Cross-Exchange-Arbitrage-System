"""
============================================================
BITGET WEBSOCKET ADAPTER - Phan C v2
============================================================

Ket noi WebSocket public cua Bitget de stream best bid/ask
real-time cho 5 cap. Tan so push tu nhien khi co thay doi gia.

Endpoint: wss://ws.bitget.com/v2/ws/public
Channel: 'books5' (top 5 levels) hoac 'ticker' (best bid/ask)

LOI ICH WS so voi REST:
    - Push proactive khi gia thay doi -> latency thap hon
    - Khong ton bandwidth khi gia khong doi
    - Bitget cho phep 240 subscribe/hour, max 1000 channel/connection
"""

import json
import time
import threading
import logging
from typing import Callable, Optional
import websocket  # pip install websocket-client


log = logging.getLogger("BitgetWS")


class BitgetWebSocket:
    """Bitget public WebSocket client cho top 5 orderbook."""

    URL = "wss://ws.bitget.com/v2/ws/public"

    def __init__(self, symbols: list[str], on_quote: Callable[[dict], None]):
        """
        symbols: list cap dang ["BTCUSDT", "ETHUSDT", ...]
        on_quote: callback nhan dict {
            'exchange': 'BITGET',
            'symbol':   'BTCUSDT',
            'bid':      float, 'bid_size': float,
            'ask':      float, 'ask_size': float,
            'ws_receive_ts': float (epoch sec, time.time())
        }
        """
        self.symbols   = symbols
        self.on_quote  = on_quote
        self.ws        = None
        self.running   = False
        self._ping_thread = None

    def _on_open(self, ws):
        log.info("Bitget WS connected")
        # Subscribe ticker channel cho moi symbol
        args = [
            {"instType": "SPOT", "channel": "ticker", "instId": s}
            for s in self.symbols
        ]
        ws.send(json.dumps({"op": "subscribe", "args": args}))

        # Bitget yeu cau ping moi 30s
        def ping_loop():
            while self.running:
                time.sleep(20)
                try:
                    ws.send("ping")
                except Exception:
                    break
        self._ping_thread = threading.Thread(target=ping_loop, daemon=True)
        self._ping_thread.start()

    def _on_message(self, ws, message):
        # Server tra ve "pong" cho moi ping -> bo qua
        if message == "pong":
            return
        ws_receive_ts = time.time()
        try:
            msg = json.loads(message)
        except Exception:
            return

        # Subscription confirmation -> bo qua
        if msg.get("event") == "subscribe":
            return

        # Data push
        if msg.get("action") in ("snapshot", "update"):
            arg  = msg.get("arg", {})
            data = msg.get("data", [])
            if arg.get("channel") != "ticker" or not data:
                return
            for d in data:
                try:
                    quote = {
                        "exchange":      "BITGET",
                        "symbol":        d["instId"],
                        "bid":           float(d["bidPr"]),
                        "bid_size":      float(d.get("bidSz", 0)),
                        "ask":           float(d["askPr"]),
                        "ask_size":      float(d.get("askSz", 0)),
                        "ws_receive_ts": ws_receive_ts,
                    }
                    self.on_quote(quote)
                except (KeyError, ValueError) as e:
                    log.warning(f"Bitget parse error: {e}, raw={d}")

    def _on_error(self, ws, error):
        log.error(f"Bitget WS error: {error}")

    def _on_close(self, ws, code, msg):
        log.warning(f"Bitget WS closed: code={code} msg={msg}")
        self.running = False

    def start(self):
        """Chay vong lap WebSocket. Tu reconnect neu lost."""
        self.running = True
        while self.running:
            try:
                self.ws = websocket.WebSocketApp(
                    self.URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                log.error(f"Bitget WS crashed: {e}")
            if self.running:
                log.info("Bitget WS reconnect after 5s...")
                time.sleep(5)

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()
