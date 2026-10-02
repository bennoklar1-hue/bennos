import json
import requests

from .config import config

XAI_URL = "https://api.x.ai/v1/chat/completions"

CONFIDENCE_TO_FRACTION = {"high": 1.0, "medium": 0.5, "low": 0.25}

RISK_INSTRUCTIONS = {
    "conservative": (
        "Be very cautious. Only choose buy or sell when the signal is strong and "
        "unambiguous. When in doubt, hold."
    ),
    "balanced": (
        "Be reasonably cautious. Prefer hold when signals are mixed, but act on "
        "clear trends."
    ),
    "aggressive": (
        "Be willing to act on moderate signals and smaller edges. Do not wait for "
        "perfect certainty, but still avoid clearly bad setups."
    ),
}


def build_system_prompt() -> str:
    risk_text = RISK_INSTRUCTIONS[config.RISK_LEVEL]
    return (
        "You are a crypto trading assistant. Risk setting: "
        f"{config.RISK_LEVEL}. {risk_text} "
        "For each watched pair you will be given: the current price, its "
        "percent change over the recent period, a short-term moving average "
        "(SMA5), a longer-term moving average (SMA20), and RSI14 (0-100; "
        "above 70 typically means overbought/due for a pullback, below 30 "
        "means oversold/due for a bounce; SMA5 above SMA20 suggests upward "
        "momentum, SMA5 below SMA20 suggests downward momentum). You will "
        "also be given the bot's currently open positions (if any) and its "
        "free available capital. You can hold positions in several different "
        "pairs at the same time - you are not limited to one. Respond with "
        "ONLY a JSON "
        "object, no other text, in this exact shape: "
        '{"action": "buy" | "sell" | "hold", "pair": "<pair or null>", '
        '"confidence": "high" | "medium" | "low", "reason": "<one short '
        'sentence>"}. '
        "Only choose buy for a pair that is not already an open position, "
        "using free capital. Only choose sell for a pair that is currently an "
        "open position. If action is hold, set pair to null. "
        "Set confidence to how strong and unambiguous the signal is - this "
        "controls position size: high means use all available free capital, "
        "medium means use half of it, low means use a quarter. Use medium or "
        "low instead of skipping a reasonable but not fully certain "
        "opportunity."
    )


def ask_grok(market_summary: str) -> dict:
    headers = {
        "Authorization": f"Bearer {config.XAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.GROK_MODEL,
        "messages": [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": market_summary},
        ],
        "temperature": 0.2,
    }

    response = requests.post(XAI_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"].strip()

    try:
        decision = json.loads(content)
    except json.JSONDecodeError:
        return {"action": "hold", "pair": None, "size_fraction": 0.0, "reason": f"unparseable model response: {content[:200]}"}

    if decision.get("action") not in ("buy", "sell", "hold"):
        return {"action": "hold", "pair": None, "size_fraction": 0.0, "reason": "model returned an invalid action"}

    decision.setdefault("pair", None)
    confidence = str(decision.get("confidence", "medium")).strip().lower()
    decision["size_fraction"] = CONFIDENCE_TO_FRACTION.get(confidence, 0.5)
    return decision
