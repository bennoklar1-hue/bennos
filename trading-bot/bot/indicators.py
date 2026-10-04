def sma(values: list, period: int):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(values: list, period: int = 14):
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        diff = values[i] - values[i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(-diff)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def pct_change(values: list):
    if len(values) < 2 or values[0] == 0:
        return None
    return (values[-1] - values[0]) / values[0] * 100


def volume_ratio(volumes: list):
    if len(volumes) < 2:
        return None
    baseline = volumes[:-1]
    avg = sum(baseline) / len(baseline)
    if avg == 0:
        return None
    return volumes[-1] / avg


def summarize(candles: list) -> dict:
    closes = [c[4] for c in candles]
    volumes = [c[5] for c in candles]
    return {
        "last_price": closes[-1] if closes else None,
        "pct_change": pct_change(closes),
        "sma_short": sma(closes, 5),
        "sma_long": sma(closes, 20),
        "rsi": rsi(closes, 14),
        "volume_ratio": volume_ratio(volumes),
    }
