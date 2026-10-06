import logging
import time

from .config import config
from .exchange_client import ExchangeClient
from .grok_client import ask_grok
from .indicators import summarize
from .sentiment import fetch_fear_greed
from .state import load_state, save_state

log = logging.getLogger("strategy")

MIN_ORDER_EUR = 10.0


def net_amount_after_fee(result: dict, base_asset: str) -> float:
    amount = result["amount"]
    fee = result.get("fee")
    if fee and fee.get("currency") == base_asset and fee.get("cost"):
        amount -= fee["cost"]
    return amount * 0.999


def net_proceeds_after_fee(result: dict, quote_asset: str) -> float:
    proceeds = result.get("cost") or result["amount"] * result["price"]
    fee = result.get("fee")
    if fee and fee.get("currency") == quote_asset and fee.get("cost"):
        proceeds -= fee["cost"]
    return proceeds


def build_market_summary(candles_by_pair: dict, state: dict) -> str:
    lines = [f"Risk level: {config.RISK_LEVEL}"]

    fng = fetch_fear_greed()
    if fng:
        lines.append(f"Crypto Fear & Greed Index: {fng['value']}/100 ({fng['classification']})")

    lines.append("Watched pairs:")
    for pair, candles in candles_by_pair.items():
        ind = summarize(candles)
        fmt = lambda v, suffix="": f"{v:.4f}{suffix}" if v is not None else "n/a"
        lines.append(
            f"  {pair}: price {fmt(ind['last_price'])}, change over period "
            f"{fmt(ind['pct_change'], '%')}, SMA5 {fmt(ind['sma_short'])}, "
            f"SMA20 {fmt(ind['sma_long'])}, RSI14 {fmt(ind['rsi'])}, "
            f"volume vs avg {fmt(ind['volume_ratio'], 'x')}"
        )

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
        try:
            current_price = exchange.fetch_price(pair)
        except Exception:
            log.exception("Failed to fetch price for stop-loss check on %s, will retry next cycle.", pair)
            continue
        drop_percent = (pos["entry_price"] - current_price) / pos["entry_price"] * 100
        if drop_percent >= config.STOP_LOSS_PERCENT:
            log.warning("Stop-loss triggered on %s at %.2f%% drop, selling.", pair, drop_percent)
            try:
                result = exchange.create_market_sell(pair, pos["amount"])
            except Exception as e:
                log.error(
                    "Stop-loss sell on %s failed (position likely below exchange minimum order "
                    "size, ~%.2f EUR) - can't auto-sell, needs manual clearing on the exchange: %s",
                    pair, pos["amount"] * current_price, e,
                )
                continue
            quote_asset = pair.split("/")[1]
            proceeds = net_proceeds_after_fee(result, quote_asset)
            state["capital_eur"] += proceeds
            del state["positions"][pair]
            state.setdefault("cooldowns", {})[pair] = time.time() + config.STOP_LOSS_COOLDOWN_HOURS * 3600
            log.info("Stop-loss sell result: %s | free capital now: %.2f EUR", result, state["capital_eur"])
            changed = True
    if changed:
        save_state(state)
    return changed


def run_once(exchange: ExchangeClient):
    state = load_state()

    check_stop_losses(exchange, state)

    candles_by_pair = {}
    for pair in config.TRADING_PAIRS:
        try:
            candles_by_pair[pair] = exchange.fetch_ohlcv(pair)
        except Exception:
            log.exception("Failed to fetch data for %s, skipping it this cycle.", pair)

    summary = build_market_summary(candles_by_pair, state)
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
        cooldown_until = state.get("cooldowns", {}).get(pair)
        if cooldown_until and time.time() < cooldown_until:
            log.info(
                "%s is on stop-loss cooldown for another %.1fh, ignoring buy signal.",
                pair, (cooldown_until - time.time()) / 3600,
            )
            return
        invest_amount = state["capital_eur"] * decision["size_fraction"]
        if invest_amount < MIN_ORDER_EUR:
            log.info(
                "Investment amount %.2f EUR below minimum order size (%.2f EUR), skipping buy signal.",
                invest_amount, MIN_ORDER_EUR,
            )
            return
        result = exchange.create_market_buy(pair, invest_amount)
        log.info("Buy result on %s (%.0f%% of free capital): %s", pair, decision["size_fraction"] * 100, result)
        base_asset = pair.split("/")[0]
        amount = net_amount_after_fee(result, base_asset)
        state["capital_eur"] -= invest_amount
        state["positions"][pair] = {"amount": amount, "entry_price": result["price"]}
        save_state(state)

    elif decision["action"] == "sell":
        pair = decision.get("pair")
        if pair not in state["positions"]:
            log.info("No open position on %s, ignoring sell signal.", pair)
            return
        pos = state["positions"][pair]
        try:
            result = exchange.create_market_sell(pair, pos["amount"])
        except Exception as e:
            log.error(
                "Sell on %s failed (position likely below exchange minimum order size) - "
                "can't auto-sell, needs manual clearing on the exchange: %s", pair, e,
            )
            return
        quote_asset = pair.split("/")[1]
        proceeds = net_proceeds_after_fee(result, quote_asset)
        state["capital_eur"] += proceeds
        del state["positions"][pair]
        log.info("Sell result on %s: %s | free capital now: %.2f EUR", pair, result, state["capital_eur"])
        save_state(state)

    else:
        log.info("Holding, no action taken.")
