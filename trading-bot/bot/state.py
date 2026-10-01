import json
import os

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "state.json")

EMPTY_STATE = {"position_amount": 0.0, "entry_price": None, "invested_eur": 0.0}


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return dict(EMPTY_STATE)
    with open(STATE_PATH) as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
