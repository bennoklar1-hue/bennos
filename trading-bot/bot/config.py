import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


class Config:
    XAI_API_KEY = os.getenv("XAI_API_KEY", "")
    GROK_MODEL = os.getenv("GROK_MODEL", "grok-4-fast")

    EXCHANGE = os.getenv("EXCHANGE", "binance")
    EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY", "")
    EXCHANGE_API_SECRET = os.getenv("EXCHANGE_API_SECRET", "")

    TRADING_PAIRS = [p.strip() for p in os.getenv("TRADING_PAIRS", "BTC/USDT").split(",") if p.strip()]
    RISK_LEVEL = os.getenv("RISK_LEVEL", "balanced").strip().lower()
    STARTING_CAPITAL_EUR = float(os.getenv("STARTING_CAPITAL_EUR", "50"))
    STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "10"))
    STOP_LOSS_COOLDOWN_HOURS = float(os.getenv("STOP_LOSS_COOLDOWN_HOURS", "12"))
    POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "15"))

    DRY_RUN = _bool("DRY_RUN", True)

    def validate(self):
        missing = [name for name in ("XAI_API_KEY",) if not getattr(self, name)]
        if not self.DRY_RUN:
            for name in ("EXCHANGE_API_KEY", "EXCHANGE_API_SECRET"):
                if not getattr(self, name):
                    missing.append(name)
        if missing:
            raise RuntimeError(f"Missing required .env values: {', '.join(missing)}")
        if self.RISK_LEVEL not in ("conservative", "balanced", "aggressive"):
            raise RuntimeError("RISK_LEVEL must be conservative, balanced, or aggressive")


config = Config()
