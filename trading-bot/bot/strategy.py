import logging

from .config import config
from .exchange_client import ExchangeClient
from .grok_client import ask_grok
from .state import load_state, save_state

log = logging.getLogger("strategy")


def build_market_summary(ohlcv, state) -> str:
    closes = [candle[4] for candle in ohlcv]
    lines = [
        f"Pair: {config.TRADING_PAIR}",
        f"Last {len(closes)} close prices: {closes}",
        f"Current position: {'open, entry price ' + str(state['entry_price']) if state['position_amount'] > 0 else 'none'}",
        f"Invested so far: {state['invested_eur']} EUR out of a {config.MAX_TRADE_EUR} EUR budget",
    ]
    return "\n".join(lines)


def run_once(exchange: ExchangeClient):
    state = load_state()
    ohlcv = exchange.fetch_ohlcv()
    current_price = ohlcv[-1][4]

    if state["position_amount"] > 0 and state["entry_price"]:
        drop_percent = (state["entry_price"] - current_price) / state["entry_price"] * 100
        if drop_percent >= config.STOP_LOSS_PERCENT:
            log.warning("Stop-loss triggered at %.2f%% drop, selling.", drop_percent)
            result = exchange.create_market_sell(state["position_amount"])
            log.info("Stop-loss sell result: %s", result)
            save_state({"position_amount": 0.0, "entry_price": None, "invested_eur": 0.0})
            return

    summary = build_market_summary(ohlcv, state)
    decision = ask_grok(summary)
    log.info("Grok decision: %s", decision)

    if decision["action"] == "buy":
        remaining_budget = config.MAX_TRADE_EUR - state["invested_eur"]
        if state["position_amount"] > 0:
            log.info("Already in a position, ignoring buy signal.")
            return
        if remaining_budget <= 0:
            log.info("Budget of %s EUR exhausted, ignoring buy signal.", config.MAX_TRADE_EUR)
            return
        result = exchange.create_market_buy(remaining_budget)
        log.info("Buy result: %s", result)
        save_state({
            "position_amount": result["amount"],
            "entry_price": result["price"],
            "invested_eur": state["invested_eur"] + remaining_budget,
        })

    elif decision["action"] == "sell":
        if state["position_amount"] <= 0:
            log.info("No open position, ignoring sell signal.")
            return
        result = exchange.create_market_sell(state["position_amount"])
        log.info("Sell result: %s", result)
        save_state({"position_amount": 0.0, "entry_price": None, "invested_eur": 0.0})

    else:
        log.info("Holding, no action taken.")
