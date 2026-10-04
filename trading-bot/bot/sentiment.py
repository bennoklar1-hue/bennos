import logging

import requests

log = logging.getLogger("sentiment")

FNG_URL = "https://api.alternative.me/fng/"


def fetch_fear_greed():
    try:
        response = requests.get(FNG_URL, timeout=10)
        response.raise_for_status()
        data = response.json()["data"][0]
        return {"value": int(data["value"]), "classification": data["value_classification"]}
    except Exception:
        log.warning("Could not fetch Fear & Greed Index, continuing without it.")
        return None
