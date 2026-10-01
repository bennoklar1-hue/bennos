import ccxt

from .config import config


class ExchangeClient:
    def __init__(self):
        exchange_class = getattr(ccxt, config.EXCHANGE)
        self.exchange = exchange_class({
            "apiKey": config.EXCHANGE_API_KEY,
            "secret": config.EXCHANGE_API_SECRET,
            "enableRateLimit": True,
        })

    def fetch_ohlcv(self, timeframe="15m", limit=50):
        return self.exchange.fetch_ohlcv(config.TRADING_PAIR, timeframe=timeframe, limit=limit)

    def fetch_price(self):
        ticker = self.exchange.fetch_ticker(config.TRADING_PAIR)
        return ticker["last"]

    def create_market_buy(self, eur_amount: float):
        price = self.fetch_price()
        amount = eur_amount / price
        if config.DRY_RUN:
            return {"dry_run": True, "side": "buy", "amount": amount, "price": price}
        return self.exchange.create_market_buy_order(config.TRADING_PAIR, amount)

    def create_market_sell(self, amount: float):
        if config.DRY_RUN:
            price = self.fetch_price()
            return {"dry_run": True, "side": "sell", "amount": amount, "price": price}
        return self.exchange.create_market_sell_order(config.TRADING_PAIR, amount)
