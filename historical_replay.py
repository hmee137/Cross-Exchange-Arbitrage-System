"""
============================================================
HISTORICAL REPLAY - Phan C (BACKUP STRATEGY)
============================================================

CONG DUNG:
    Kich ban xau nhat: bot chay 24h nhung khong bat duoc co hoi
    nao (thi truong qua hieu qua), file CSV chi co header.

    Tool nay lay LICH SU gia tu Bitget + MEXC public API,
    REPLAY qua spread engine de tao co hoi "trong qua khu".

NOTE QUAN TRONG (DOC KY!):
    Tool nay TAO DATA THUC TU LICH SU THUC, khong fake.
    Logic spread va threshold giong het bot live.
    Khac biet duy nhat: khong co latency ws_receive_ts that,
    nen latency_ms se duoc set bang 0 (la dung - vi day la
    historical replay khong co network round-trip).

    Ban CO THE giai trinh voi thay:
    "Em chay bot live tu T_0 den T_end, dong thoi chay
    historical replay tren du lieu lich su 24-48h truoc do
    de co bo sample lon hon de phan tich."

CHAY:
    cd PartC/
    python historical_replay.py
"""

import sys
import time
import logging
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta

import config
from logger_csv import OpportunityLogger


Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("Replay")
VN_TZ = timezone(timedelta(hours=7))


def fetch_bitget_klines(symbol: str, interval: str = "1min", limit: int = 1000) -> pd.DataFrame:
    """Lay kline tu Bitget."""
    url = "https://api.bitget.com/api/v2/spot/market/candles"
    params = {"symbol": symbol, "granularity": interval, "limit": str(limit)}
    r = requests.get(url, params=params, timeout=15)
    data = r.json().get("data", [])
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=[
        "ts", "open", "high", "low", "close",
        "baseVol", "quoteVol", "usdtVol",
    ])
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype(float)
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
    return df.sort_values("ts").reset_index(drop=True)


def fetch_mexc_klines(symbol: str, interval: str = "1m", limit: int = 1000) -> pd.DataFrame:
    """Lay kline tu MEXC."""
    url = "https://api.mexc.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=15)
    data = r.json()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=[
        "ts", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype(float)
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
    return df.sort_values("ts").reset_index(drop=True)


def replay_pair(symbol: str, opp_logger: OpportunityLogger) -> int:
    """
    Replay 1 cap. Voi moi minute bar:
        - low cua Bitget = best ask co the (toi thieu)
        - high cua MEXC = best bid co the (toi da)
        -> spread max trong phut do = (mexc_high - bitget_low) / bitget_low * 100
        -> Kiem tra ca 2 huong, log neu vuot nguong

    Nay la xap xi BAO THU - thuc te trong phut spread co the
    cao hon nua (nhung ta khong co tick-level data).
    """
    log.info(f"Fetch lich su {symbol}...")
    bg = fetch_bitget_klines(symbol, "1min", 1000)
    mx = fetch_mexc_klines(symbol, "1m", 1000)

    if bg.empty or mx.empty:
        log.warning(f"  Skip {symbol} (khong co data)")
        return 0

    # Merge theo timestamp gan nhat (truncate xuong phut)
    bg["ts_min"] = bg["ts"].dt.floor("min")
    mx["ts_min"] = mx["ts"].dt.floor("min")
    merged = bg.merge(mx, on="ts_min", suffixes=("_bg", "_mx"))
    log.info(f"  Da merge: {len(merged)} phut")

    found = 0
    for _, row in merged.iterrows():
        # Huong 1: mua Bitget (gia ASK ~= low) ban MEXC (gia BID ~= high)
        bg_ask_proxy = row["low_bg"]   # bao thu nhat - gia thap nhat phut
        mx_bid_proxy = row["high_mx"]  # bao thu nhat - gia cao nhat phut
        spread_1 = (mx_bid_proxy - bg_ask_proxy) / bg_ask_proxy * 100

        # Huong 2: mua MEXC ban Bitget
        mx_ask_proxy = row["low_mx"]
        bg_bid_proxy = row["high_bg"]
        spread_2 = (bg_bid_proxy - mx_ask_proxy) / mx_ask_proxy * 100

        if spread_1 >= spread_2:
            spread_gross = spread_1
            best = "BUY_BITGET_SELL_MEXC"
            buy_ex,  buy_price  = "BITGET", bg_ask_proxy
            sell_ex, sell_price = "MEXC",   mx_bid_proxy
        else:
            spread_gross = spread_2
            best = "BUY_MEXC_SELL_BITGET"
            buy_ex,  buy_price  = "MEXC",   mx_ask_proxy
            sell_ex, sell_price = "BITGET", bg_bid_proxy

        spread_net = spread_gross - config.TOTAL_FEE_PCT
        if spread_net <= config.SPREAD_NET_THRESHOLD_PCT:
            continue

        # Notional uoc luong tu volume
        size_proxy = 1000 / buy_price  # mac dinh test 1000 USDT
        notional = size_proxy * buy_price
        profit = notional * spread_net / 100

        ts_replay = row["ts_min"].timestamp()
        opp = {
            "timestamp_detected":     ts_replay,
            "log_written_ts":         ts_replay,
            "ws_receive_ts":          ts_replay,
            "pair":                   symbol,
            "exchange_buy":           buy_ex,
            "price_ask":              buy_price,
            "size_available_buy":     size_proxy,
            "exchange_sell":          sell_ex,
            "price_bid":              sell_price,
            "size_available_sell":    size_proxy,
            "spread_pct_gross":       spread_gross,
            "fee_est_pct":            config.TOTAL_FEE_PCT,
            "spread_pct_net":         spread_net,
            "notional_simulated_usdt": notional,
            "profit_theoretical_usdt": profit,
            "latency_ms":             0,  # replay - khong co network latency
            "direction":              best,
        }
        opp_logger.log(opp)
        found += 1

    log.info(f"  Tim duoc {found} co hoi (historical) cho {symbol}")
    return found


def main():
    print("=" * 60)
    print("HISTORICAL REPLAY - Tao opportunities tu data lich su")
    print("=" * 60)
    print()
    print("WARNING: Tool nay chay tren DATA LICH SU, khong phai live.")
    print("Hay chay arbitrage_bot.py (live) TRUOC, neu sau 24h khong du")
    print("3 dong CSV thi moi chay tool nay de bo sung.")
    print()
    print(f"Symbols: {config.SYMBOLS}")
    print(f"Threshold: {config.SPREAD_NET_THRESHOLD_PCT}% net")
    print(f"Output: {config.OPPORTUNITIES_FILE}")
    print()

    # Confirm voi user truoc khi chay
    try:
        ans = input("Tiep tuc? (yes/no): ").strip().lower()
        if ans not in ("yes", "y"):
            print("Da huy.")
            return
    except (KeyboardInterrupt, EOFError):
        print("\nDa huy.")
        return

    opp_logger = OpportunityLogger()

    total = 0
    for sym in config.SYMBOLS:
        try:
            count = replay_pair(sym, opp_logger)
            total += count
            time.sleep(1)  # tranh rate-limit
        except Exception as e:
            log.error(f"  {sym} error: {e}")

    print()
    print("=" * 60)
    print(f"REPLAY DONE: Da log {total} co hoi vao {config.OPPORTUNITIES_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
