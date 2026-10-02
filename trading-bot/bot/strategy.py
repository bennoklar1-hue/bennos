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

    if state["positions"]:
        lines.append("Open positions:")
        for pair, pos in state["positions"].items():
            lines.append(f"  {pair}: entry price {pos['entry_price']}")
    else:
        lines.append("Open positions: none")

    lines.append(f"Free available capital: {state['capital_eur']:.2f} EUR")
    return "\n".join(lines)


def check_stop_losses(exchange: ExchangeClient, state: dict) -> bool:
    changed = False
    for pair in list(state["positions"].keys()):
        pos = state["positions"][pair]
        current_price = exchange.fetch_price(pair)
        drop_percent = (pos["entry_price"] - current_price) / pos["entry_price"] * 100
        if drop_percent >= config.STOP_LOSS_PERCENT:
            log.warning("Stop-loss triggered on %s at %.2f%% drop, selling.", pair, drop_percent)
            result = exchange.create_market_sell(pair, pos["amount"])
            proceeds = pos["amount"] * result["price"]
            state["capital_eur"] += proceeds
            del state["positions"][pair]
            log.info("Stop-loss sell result: %s | free capital now: %.2f EUR", result, state["capital_eur"])
            changed = True
    if changed:
        save_state(state)
    return changed


def run_once(exchange: ExchangeClient):
    state = load_state()

    check_stop_losses(exchange, state)

    prices_by_pair = {
        pair: [candle[4] for candle in exchange.fetch_ohlcv(pair)]
        for pair in config.TRADING_PAIRS
    }

    summary = build_market_summary(prices_by_pair, state)
    decision = ask_grok(summary)
    log.info("Grok decision: %s", decision)

    if decision["action"] == "buy":
        pair = decision.get("pair")
        if pair not in config.TRADING_PAIRS:
            log.info("Buy signal named an unwatched pair (%s), ignoring.", pair)
            return
        if pair in state["positions"]:
            log.info("Already holding %s, ignoring buy signal.", pair)
            return
        invest_amount = state["capital_eur"] * decision["size_fraction"]
        if invest_amount <= 0:
            log.info("No capital left, ignoring buy signal.")
            return
        result = exchange.create_market_buy(pair, invest_amount)
        log.info("Buy result on %s (%.0f%% of free capital): %s", pair, decision["size_fraction"] * 100, result)
        state["capital_eur"] -= invest_amount
        state["positions"][pair] = {"amount": result["amount"], "entry_price": result["price"]}
        save_state(state)

    elif decision["action"] == "sell":
        pair = decision.get("pair")
        if pair not in state["positions"]:
            log.info("No open position on %s, ignoring sell signal.", pair)
            return
        pos = state["positions"][pair]
        result = exchange.create_market_sell(pair, pos["amount"])
        proceeds = pos["amount"] * result["price"]
        state["capital_eur"] += proceeds
        del state["positions"][pair]
        log.info("Sell result on %s: %s | free capital now: %.2f EUR", pair, result, state["capital_eur"])
        save_state(state)

    else:
        log.info("Holding, no action taken.")
