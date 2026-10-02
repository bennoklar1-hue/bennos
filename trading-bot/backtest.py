import json
import logging
from datetime import datetime, timezone

import ccxt

from bot.config import config
from bot.grok_client import ask_grok
from bot.indicators import summarize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backtest")

BACKTEST_DAYS = 45
DECISION_INTERVAL_HOURS = 4
CANDLE_TIMEFRAME = "15m"
CANDLE_MINUTES = 15
LOOKBACK_CANDLES = 30


def fetch_full_history(exchange, pair, since_ms, until_ms):
    all_candles = []
    cursor = since_ms
    while cursor < until_ms:
        batch = exchange.fetch_ohlcv(pair, timeframe=CANDLE_TIMEFRAME, since=cursor, limit=1000)
        if not batch:
            break
        all_candles.extend(batch)
        last_ts = batch[-1][0]
        if last_ts <= cursor:
            break
        cursor = last_ts + 1
        if len(batch) < 1000:
            break
    return [c for c in all_candles if c[0] <= until_ms]


def build_market_summary(prices_by_pair: dict, state: dict) -> str:
    lines = [f"Risk level: {config.RISK_LEVEL}", "Watched pairs:"]
    for pair, closes in prices_by_pair.items():
        ind = summarize(closes)
        fmt = lambda v, suffix="": f"{v:.4f}{suffix}" if v is not None else "n/a"
        lines.append(
            f"  {pair}: price {fmt(ind['last_price'])}, change over period "
            f"{fmt(ind['pct_change'], '%')}, SMA5 {fmt(ind['sma_short'])}, "
            f"SMA20 {fmt(ind['sma_long'])}, RSI14 {fmt(ind['rsi'])}"
        )
    if state["positions"]:
        lines.append("Open positions:")
        for pair, pos in state["positions"].items():
            lines.append(f"  {pair}: entry price {pos['entry_price']}")
    else:
        lines.append("Open positions: none")
    lines.append(f"Free available capital: {state['capital_eur']:.2f} EUR")
    return "\n".join(lines)


def main():
    exchange = ccxt.binance({"enableRateLimit": True})
    now = exchange.milliseconds()
    since = now - BACKTEST_DAYS * 24 * 60 * 60 * 1000
    warmup_ms = LOOKBACK_CANDLES * CANDLE_MINUTES * 60 * 1000
    fetch_since = since - warmup_ms

    log.info("Fetching %s days of %s history for %d pairs (no API key needed, public data)...",
              BACKTEST_DAYS, CANDLE_TIMEFRAME, len(config.TRADING_PAIRS))
    history = {}
    for pair in config.TRADING_PAIRS:
        try:
            candles = fetch_full_history(exchange, pair, fetch_since, now)
            history[pair] = candles
            log.info("  %s: %d candles", pair, len(candles))
        except Exception:
            log.exception("Failed to fetch history for %s, skipping it entirely.", pair)

    starting_capital = config.STARTING_CAPITAL_EUR
    state = {"capital_eur": starting_capital, "positions": {}}
    trades = []

    benchmark_value = 0.0
    priced_pairs = 0
    for pair, candles in history.items():
        start_candles = [c for c in candles if c[0] >= since]
        if not start_candles or not candles:
            continue
        start_price = start_candles[0][4]
        end_price = candles[-1][4]
        benchmark_value += (end_price / start_price)
        priced_pairs += 1
    if priced_pairs:
        benchmark_value = starting_capital * (benchmark_value / priced_pairs)
    else:
        benchmark_value = starting_capital

    decision_step_ms = DECISION_INTERVAL_HOURS * 60 * 60 * 1000
    t = since
    decision_count = 0

    while t <= now:
        for pair in list(state["positions"].keys()):
            pos = state["positions"][pair]
            window = [c for c in history.get(pair, []) if pos["since_ts"] < c[0] <= t]
            for c in window:
                price = c[4]
                drop = (pos["entry_price"] - price) / pos["entry_price"] * 100
                if drop >= config.STOP_LOSS_PERCENT:
                    proceeds = pos["amount"] * price
                    state["capital_eur"] += proceeds
                    trades.append({"pair": pair, "type": "stop_loss_sell", "price": price,
                                   "ts": c[0], "proceeds": proceeds})
                    del state["positions"][pair]
                    break

        prices_by_pair = {}
        for pair, candles in history.items():
            window = [c[4] for c in candles if c[0] <= t][-LOOKBACK_CANDLES:]
            if len(window) >= 21:
                prices_by_pair[pair] = window

        if prices_by_pair:
            summary = build_market_summary(prices_by_pair, state)
            try:
                decision = ask_grok(summary)
            except Exception:
                log.exception("Grok call failed at t=%s, treating as hold.",
                               datetime.fromtimestamp(t / 1000, tz=timezone.utc))
                decision = {"action": "hold", "pair": None, "size_fraction": 0.0}
            decision_count += 1
            log.info("[%s] decision: %s", datetime.fromtimestamp(t / 1000, tz=timezone.utc), decision)

            pair = decision.get("pair")
            if decision["action"] == "buy" and pair in prices_by_pair and pair not in state["positions"]:
                invest = state["capital_eur"] * decision.get("size_fraction", 0)
                if invest > 0:
                    price = prices_by_pair[pair][-1]
                    amount = invest / price
                    state["capital_eur"] -= invest
                    state["positions"][pair] = {"amount": amount, "entry_price": price, "since_ts": t}
                    trades.append({"pair": pair, "type": "buy", "price": price, "ts": t, "invest": invest})
            elif decision["action"] == "sell" and pair in state["positions"]:
                pos = state["positions"][pair]
                price = prices_by_pair[pair][-1] if pair in prices_by_pair else pos["entry_price"]
                proceeds = pos["amount"] * price
                state["capital_eur"] += proceeds
                trades.append({"pair": pair, "type": "sell", "price": price, "ts": t, "proceeds": proceeds})
                del state["positions"][pair]

        t += decision_step_ms

    for pair, pos in list(state["positions"].items()):
        candles = history.get(pair, [])
        final_price = candles[-1][4] if candles else pos["entry_price"]
        proceeds = pos["amount"] * final_price
        state["capital_eur"] += proceeds
        trades.append({"pair": pair, "type": "final_close", "price": final_price, "ts": now, "proceeds": proceeds})
    state["positions"] = {}

    final_capital = state["capital_eur"]
    total_return_pct = (final_capital - starting_capital) / starting_capital * 100
    benchmark_return_pct = (benchmark_value - starting_capital) / starting_capital * 100

    buys = [tr for tr in trades if tr["type"] == "buy"]
    sells = [tr for tr in trades if tr["type"] in ("sell", "stop_loss_sell", "final_close")]

    print("\n" + "=" * 50)
    print("BACKTEST REPORT")
    print("=" * 50)
    print(f"Period: {BACKTEST_DAYS} days, decision every {DECISION_INTERVAL_HOURS}h")
    print(f"Grok calls made: {decision_count}")
    print(f"Starting capital: {starting_capital:.2f} EUR")
    print(f"Final capital:    {final_capital:.2f} EUR")
    print(f"Bot return:       {total_return_pct:+.2f}%")
    print(f"Buy & hold return (equal split across pairs): {benchmark_return_pct:+.2f}%")
    print(f"Total buys: {len(buys)}, total sells/closes: {len(sells)}")
    print("=" * 50)

    with open("backtest_result.json", "w") as f:
        json.dump({
            "starting_capital": starting_capital,
            "final_capital": final_capital,
            "total_return_pct": total_return_pct,
            "benchmark_return_pct": benchmark_return_pct,
            "decision_count": decision_count,
            "trades": trades,
        }, f, indent=2, default=str)
    print("Full trade log saved to backtest_result.json")


if __name__ == "__main__":
    main()
