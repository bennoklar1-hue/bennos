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

    def fetch_ohlcv(self, pair: str, timeframe="15m", limit=20):
        return self.exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)

    def fetch_price(self, pair: str):
        ticker = self.exchange.fetch_ticker(pair)
        return ticker["last"]

    def create_market_buy(self, pair: str, eur_amount: float):
        price = self.fetch_price(pair)
        amount = eur_amount / price
        if config.DRY_RUN:
            return {"dry_run": True, "side": "buy", "amount": amount, "price": price}
        return self.exchange.create_market_buy_order(pair, amount)

    def create_market_sell(self, pair: str, amount: float):
        if config.DRY_RUN:
            price = self.fetch_price(pair)
            return {"dry_run": True, "side": "sell", "amount": amount, "price": price}
        return self.exchange.create_market_sell_order(pair, amount)
