import json
import requests

from .config import config

XAI_URL = "https://api.x.ai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a cautious crypto trading assistant. You will be given recent "
    "price data for one trading pair and the bot's current position state. "
    "Respond with ONLY a JSON object, no other text, in this exact shape: "
    '{"action": "buy" | "sell" | "hold", "reason": "<one short sentence>"}. '
    "Only choose buy if there is no open position yet. Only choose sell if "
    "there is an open position. Be conservative - prefer hold when signals "
    "are mixed or unclear."
)


def ask_grok(market_summary: str) -> dict:
    headers = {
        "Authorization": f"Bearer {config.XAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.GROK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
        return {"action": "hold", "reason": f"unparseable model response: {content[:200]}"}

    if decision.get("action") not in ("buy", "sell", "hold"):
        return {"action": "hold", "reason": "model returned an invalid action"}

    return decision
