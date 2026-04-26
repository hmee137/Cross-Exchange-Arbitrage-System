"""
============================================================
SPREAD ENGINE - Phan C v2
============================================================

Module 2 cua he thong arbitrage. Logic:
    1. Luu trang thai gia hien tai cua moi (san, cap)
    2. Khi moi quote moi den -> kiem tra co arbitrage opportunity khong
    3. Spread_gross = (Bid_san_ban - Ask_san_mua) / Ask_san_mua * 100
    4. Spread_net   = Spread_gross - TOTAL_FEE_PCT
    5. Neu Spread_net > nguong -> trigger callback
"""

import time
import threading
import logging
from typing import Callable, Optional
from collections import defaultdict

import config


log = logging.getLogger("Spread")


class SpreadEngine:
    """
    Quan ly state gia tu 2 san + tinh spread real-time.
    """

    def __init__(self, on_opportunity: Callable[[dict], None]):
        """
        on_opportunity: callback nhan dict opportunity day du
                        12 cot theo schema de bai (Muc C.3.3).
        """
        self.on_opportunity = on_opportunity
        # state: {symbol: {exchange: quote_dict}}
        self.state = defaultdict(dict)
        self.lock  = threading.Lock()  # tranh race khi 2 source push cung luc

    def on_quote(self, quote: dict):
        """
        Callback duoc goi tu BitgetWS va MEXCRest.
        Quote da co ws_receive_ts.
        """
        detected_ts = time.time()  # Khi spread engine bat dau xu ly

        with self.lock:
            sym  = quote["symbol"]
            exch = quote["exchange"]
            self.state[sym][exch] = quote

            # Can ca 2 san co data thi moi tinh duoc spread
            if len(self.state[sym]) < 2:
                return

            bg = self.state[sym].get("BITGET")
            mx = self.state[sym].get("MEXC")
            if not bg or not mx:
                return

            self._check_spread(sym, bg, mx, detected_ts)

    def _check_spread(self, symbol: str, bg: dict, mx: dict, detected_ts: float):
        """
        Kiem tra ca 2 huong:
            1. Mua Bitget (gia ASK), ban MEXC (gia BID)
            2. Mua MEXC   (gia ASK), ban Bitget (gia BID)
        Lay huong nao co spread cao hon.
        """
        # Huong 1: Buy Bitget, Sell MEXC
        spread_gross_1 = (mx["bid"] - bg["ask"]) / bg["ask"] * 100
        # Huong 2: Buy MEXC, Sell Bitget
        spread_gross_2 = (bg["bid"] - mx["ask"]) / mx["ask"] * 100

        if spread_gross_1 >= spread_gross_2:
            best = "BUY_BITGET_SELL_MEXC"
            spread_gross = spread_gross_1
            buy_ex,  buy_price,  buy_size  = "BITGET", bg["ask"], bg["ask_size"]
            sell_ex, sell_price, sell_size = "MEXC",   mx["bid"], mx["bid_size"]
            ws_receive_ts = max(bg["ws_receive_ts"], mx["ws_receive_ts"])
        else:
            best = "BUY_MEXC_SELL_BITGET"
            spread_gross = spread_gross_2
            buy_ex,  buy_price,  buy_size  = "MEXC",   mx["ask"], mx["ask_size"]
            sell_ex, sell_price, sell_size = "BITGET", bg["bid"], bg["bid_size"]
            ws_receive_ts = max(bg["ws_receive_ts"], mx["ws_receive_ts"])

        spread_net = spread_gross - config.TOTAL_FEE_PCT

        # Chi log khi vuot nguong
        if spread_net <= config.SPREAD_NET_THRESHOLD_PCT:
            return

        # Tinh notional & profit ly thuyet
        # Lay min cua 2 size de mo phong khoi luong khop duoc
        size_min = min(buy_size, sell_size)
        notional = size_min * buy_price  # quy doi USDT
        profit_theoretical = notional * spread_net / 100

        # Tinh latency end-to-end
        log_written_ts = time.time()
        latency_ms = (log_written_ts - ws_receive_ts) * 1000

        opportunity = {
            "timestamp_detected":     detected_ts,
            "log_written_ts":         log_written_ts,
            "ws_receive_ts":          ws_receive_ts,
            "pair":                   symbol,
            "exchange_buy":           buy_ex,
            "price_ask":              buy_price,
            "size_available_buy":     buy_size,
            "exchange_sell":          sell_ex,
            "price_bid":              sell_price,
            "size_available_sell":    sell_size,
            "spread_pct_gross":       spread_gross,
            "fee_est_pct":            config.TOTAL_FEE_PCT,
            "spread_pct_net":         spread_net,
            "notional_simulated_usdt": notional,
            "profit_theoretical_usdt": profit_theoretical,
            "latency_ms":             latency_ms,
            "direction":              best,
        }

        # Trigger callback (logger se ghi vao CSV)
        self.on_opportunity(opportunity)
