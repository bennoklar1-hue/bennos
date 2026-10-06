import json
import os

from .config import config

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state.json")


def _empty_state() -> dict:
    return {
        "capital_eur": config.STARTING_CAPITAL_EUR,
        "positions": {},  # pair -> {"amount": float, "entry_price": float}
        "cooldowns": {},  # pair -> unix timestamp until which buys are blocked
    }


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return _empty_state()
    with open(STATE_PATH) as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
