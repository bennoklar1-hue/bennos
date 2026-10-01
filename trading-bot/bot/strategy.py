import logging

from .config import config
from .exchange_client import ExchangeClient
from .grok_client import ask_grok
from .state import load_state, save_state

log = logging.getLogger("strategy")


def build_market_summary(prices_by_pair: dict, state: dict) -> str:
    lines = [f"Risk level: {config.RISK_LEVEL}", "Watched pairs:"]
    for pair, closes in prices_by_pair.items():
        lines.append(f"  {pair}: last {len(closes)} close prices: {closes}")

    if state["position_amount"] > 0:
        lines.append(f"Current position: open on {state['pair']}, entry price {state['entry_price']}")
    else:
        lines.append("Current position: none")

    lines.append(f"Invested so far: {state['invested_eur']} EUR out of a {config.MAX_TRADE_EUR} EUR budget")
    return "\n".join(lines)


def check_stop_loss(exchange: ExchangeClient, state: dict) -> bool:
    if state["position_amount"] <= 0 or not state["entry_price"]:
        return False

    current_price = exchange.fetch_price(state["pair"])
    drop_percent = (state["entry_price"] - current_price) / state["entry_price"] * 100
    if drop_percent >= config.STOP_LOSS_PERCENT:
        log.warning("Stop-loss triggered on %s at %.2f%% drop, selling.", state["pair"], drop_percent)
        result = exchange.create_market_sell(state["pair"], state["position_amount"])
        log.info("Stop-loss sell result: %s", result)
        save_state({"pair": None, "position_amount": 0.0, "entry_price": None, "invested_eur": 0.0})
        return True
    return False


def run_once(exchange: ExchangeClient):
    state = load_state()

    if check_stop_loss(exchange, state):
        return

    prices_by_pair = {
        pair: [candle[4] for candle in exchange.fetch_ohlcv(pair)]
        for pair in config.TRADING_PAIRS
    }

    summary = build_market_summary(prices_by_pair, state)
    decision = ask_grok(summary)
    log.info("Grok decision: %s", decision)

    if decision["action"] == "buy":
        if state["position_amount"] > 0:
            log.info("Already in a position, ignoring buy signal.")
            return
        pair = decision.get("pair")
        if pair not in config.TRADING_PAIRS:
            log.info("Buy signal named an unwatched pair (%s), ignoring.", pair)
            return
        remaining_budget = config.MAX_TRADE_EUR - state["invested_eur"]
        if remaining_budget <= 0:
            log.info("Budget of %s EUR exhausted, ignoring buy signal.", config.MAX_TRADE_EUR)
            return
        result = exchange.create_market_buy(pair, remaining_budget)
        log.info("Buy result on %s: %s", pair, result)
        save_state({
            "pair": pair,
            "position_amount": result["amount"],
            "entry_price": result["price"],
            "invested_eur": state["invested_eur"] + remaining_budget,
        })

    elif decision["action"] == "sell":
        if state["position_amount"] <= 0:
            log.info("No open position, ignoring sell signal.")
            return
        result = exchange.create_market_sell(state["pair"], state["position_amount"])
        log.info("Sell result on %s: %s", state["pair"], result)
        save_state({"pair": None, "position_amount": 0.0, "entry_price": None, "invested_eur": 0.0})

    else:
        log.info("Holding, no action taken.")
