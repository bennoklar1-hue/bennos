import logging
import time

from bot.config import config
from bot.exchange_client import ExchangeClient
from bot.strategy import run_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("main")


def main():
    config.validate()
    log.info(
        "Starting bot | pairs=%s risk=%s budget=%sEUR dry_run=%s",
        config.TRADING_PAIRS, config.RISK_LEVEL, config.MAX_TRADE_EUR, config.DRY_RUN,
    )
    exchange = ExchangeClient()

    while True:
        try:
            run_once(exchange)
        except Exception:
            log.exception("Error during trading cycle, will retry next interval.")
        time.sleep(config.POLL_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
