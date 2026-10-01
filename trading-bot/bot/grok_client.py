import json
import requests

from .config import config

XAI_URL = "https://api.x.ai/v1/chat/completions"

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
        "You will be given recent price data for several trading pairs and the "
        "bot's current position state. Respond with ONLY a JSON object, no other "
        "text, in this exact shape: "
        '{"action": "buy" | "sell" | "hold", "pair": "<pair or null>", '
        '"reason": "<one short sentence>"}. '
        "Only choose buy if there is no open position yet, and set pair to the "
        "single pair (from the given list) you want to buy. Only choose sell if "
        "there is an open position, and set pair to that exact open position's "
        "pair. If action is hold, set pair to null."
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
        return {"action": "hold", "pair": None, "reason": f"unparseable model response: {content[:200]}"}

    if decision.get("action") not in ("buy", "sell", "hold"):
        return {"action": "hold", "pair": None, "reason": "model returned an invalid action"}

    decision.setdefault("pair", None)
    return decision
