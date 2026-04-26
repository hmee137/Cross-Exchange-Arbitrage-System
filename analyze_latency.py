"""
============================================================
LATENCY ANALYSIS - Module 4 (Phan C v2)
============================================================

Phan tich post-mortem sau khi bot chay xong.
Theo Muc C.3.4 cua de:
    - Trung binh, p50, p95, p99 cua latency
    - Phan tich profit ly thuyet: tong, theo cap, theo gio, theo spread
    - Mo phong: bao nhieu co hoi bien mat neu latency tang gap doi

CHAY:
    python analyze_latency.py

OUTPUT:
    - In thong ke len terminal
    - Tao file logs/latency_report.txt
    - Tao file logs/latency_histogram.png (neu co matplotlib)
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

import config


def percentile(arr, p):
    return np.percentile(arr, p) if len(arr) > 0 else 0


def analyze():
    Path("logs").mkdir(exist_ok=True)

    # Load opportunities
    try:
        df_opp = pd.read_csv(config.OPPORTUNITIES_FILE)
    except FileNotFoundError:
        print(f"[ERROR] Khong tim thay {config.OPPORTUNITIES_FILE}")
        print("Hay chay arbitrage_bot.py truoc de tao log")
        return

    if len(df_opp) == 0:
        print("File log rong - bot chua phat hien co hoi nao.")
        return

    # ============================================================
    # 1. LATENCY ANALYSIS
    # ============================================================
    lat = df_opp["latency_ms"].values

    print("=" * 60)
    print("MODULE 4 - LATENCY ANALYSIS")
    print("=" * 60)
    print(f"So co hoi log: {len(lat)}")
    print(f"  Mean   : {lat.mean():>10.2f} ms")
    print(f"  Median : {percentile(lat, 50):>10.2f} ms  (p50)")
    print(f"  p95    : {percentile(lat, 95):>10.2f} ms")
    print(f"  p99    : {percentile(lat, 99):>10.2f} ms")
    print(f"  Min    : {lat.min():>10.2f} ms")
    print(f"  Max    : {lat.max():>10.2f} ms")
    print(f"  Std    : {lat.std():>10.2f} ms")

    # ============================================================
    # 2. PROFIT THEORETICAL ANALYSIS
    # ============================================================
    print("\n" + "=" * 60)
    print("PROFIT LY THUYET")
    print("=" * 60)
    total_profit = df_opp["profit_theoretical_usdt"].sum()
    print(f"Tong profit ly thuyet:    {total_profit:>10.4f} USDT")
    print(f"Trung binh moi co hoi:    {df_opp['profit_theoretical_usdt'].mean():>10.4f} USDT")
    print(f"Co hoi lon nhat:          {df_opp['profit_theoretical_usdt'].max():>10.4f} USDT")
    print(f"Tong notional simulated:  {df_opp['notional_simulated_usdt'].sum():>10.2f} USDT")

    # ============================================================
    # 3. PHAN PHOI THEO CAP
    # ============================================================
    print("\nTHONG KE THEO CAP:")
    print("-" * 60)
    by_pair = df_opp.groupby("pair").agg(
        count=("pair", "count"),
        total_profit=("profit_theoretical_usdt", "sum"),
        avg_spread_net=("spread_pct_net", "mean"),
        max_spread_net=("spread_pct_net", "max"),
    ).sort_values("count", ascending=False)
    print(by_pair.to_string())

    # ============================================================
    # 4. PHAN PHOI THEO HUONG
    # ============================================================
    if "direction" in df_opp.columns:
        print("\nTHONG KE THEO HUONG:")
        print("-" * 60)
        # NOTE: cot 'direction' khong co trong schema chinh thuc,
        # nhung bot co log them de phuc vu phan tich noi bo
    
    # ============================================================
    # 5. SPREAD DISTRIBUTION
    # ============================================================
    print("\nPHAN PHOI SPREAD NET (%):")
    print("-" * 60)
    bins = [0, 0.25, 0.5, 1.0, 2.0, 5.0, 100]
    counts = pd.cut(df_opp["spread_pct_net"], bins=bins).value_counts().sort_index()
    for interval, n in counts.items():
        bar = "█" * min(int(n / max(counts.values, default=1) * 30), 30)
        print(f"  {str(interval):20s} {n:>5d}  {bar}")

    # ============================================================
    # 6. MO PHONG: Latency tang gap doi -> bao nhieu co hoi mat?
    # ============================================================
    print("\n" + "=" * 60)
    print("MO PHONG: Latency tang gap doi")
    print("=" * 60)
    # Gia su: spread_pct_net giam theo hoi quy ngam tu latency
    # Voi thi truong crypto, spread thuong giam ~50% sau moi 100ms
    # decay rate ~0.005% / ms (gia thuyet bao thu)
    decay_per_ms = 0.005
    df_opp_sim = df_opp.copy()
    new_latency = df_opp_sim["latency_ms"] * 2
    extra_decay = (new_latency - df_opp_sim["latency_ms"]) * decay_per_ms
    df_opp_sim["spread_after"] = df_opp_sim["spread_pct_net"] - extra_decay
    lost = df_opp_sim[df_opp_sim["spread_after"] <= config.SPREAD_NET_THRESHOLD_PCT]
    pct_lost = len(lost) / len(df_opp_sim) * 100 if len(df_opp_sim) > 0 else 0
    print(f"Gia thuyet decay: {decay_per_ms}% / ms")
    print(f"Co hoi ban dau:        {len(df_opp_sim)}")
    print(f"Co hoi mat sau 2x lat: {len(lost)} ({pct_lost:.1f}%)")
    print(f"Profit mat:            {lost['profit_theoretical_usdt'].sum():.4f} USDT "
          f"({lost['profit_theoretical_usdt'].sum() / total_profit * 100 if total_profit > 0 else 0:.1f}%)")

    # ============================================================
    # 7. SAVE BAO CAO
    # ============================================================
    save_report(df_opp, lat, by_pair, total_profit, pct_lost)

    # ============================================================
    # 8. VE BIEU DO (neu co matplotlib)
    # ============================================================
    try:
        plot_histogram(lat)
        print(f"\nDa luu bieu do: logs/latency_histogram.png")
    except ImportError:
        print("\n(Khong co matplotlib, skip bieu do. Cai: pip install matplotlib)")
    except Exception as e:
        print(f"\nLoi ve bieu do: {e}")

    print("\nDa luu bao cao day du: logs/latency_report.txt")


def save_report(df, lat, by_pair, total_profit, pct_lost):
    with open("logs/latency_report.txt", "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("LATENCY & PROFIT POST-MORTEM REPORT\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Tong so co hoi: {len(df)}\n\n")
        f.write("LATENCY (ms):\n")
        f.write(f"  Mean = {lat.mean():.2f}\n")
        f.write(f"  p50  = {percentile(lat, 50):.2f}\n")
        f.write(f"  p95  = {percentile(lat, 95):.2f}\n")
        f.write(f"  p99  = {percentile(lat, 99):.2f}\n")
        f.write(f"  Max  = {lat.max():.2f}\n\n")
        f.write(f"PROFIT THEORETICAL TOTAL: {total_profit:.4f} USDT\n\n")
        f.write("BY PAIR:\n")
        f.write(by_pair.to_string() + "\n\n")
        f.write(f"SIMULATION (latency 2x): {pct_lost:.1f}% co hoi se mat\n")


def plot_histogram(lat):
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    axes[0].hist(lat, bins=50, edgecolor="black", alpha=0.7)
    axes[0].axvline(np.mean(lat), color="red", linestyle="--",
                    label=f"Mean={np.mean(lat):.1f}ms")
    axes[0].axvline(percentile(lat, 95), color="orange", linestyle="--",
                    label=f"p95={percentile(lat, 95):.1f}ms")
    axes[0].axvline(percentile(lat, 99), color="darkred", linestyle="--",
                    label=f"p99={percentile(lat, 99):.1f}ms")
    axes[0].set_xlabel("Latency (ms)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Latency Distribution")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    # Boxplot
    axes[1].boxplot(lat, vert=True)
    axes[1].set_ylabel("Latency (ms)")
    axes[1].set_title("Latency Boxplot")
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("logs/latency_histogram.png", dpi=120)
    plt.close()


if __name__ == "__main__":
    analyze()
