from async_fetch_ohlcv import start_fetch_ohlcv

exchange_name = ['bitmex']*12
currency = ['ETH/USD','BTC/USD']*6
timeframe = ['1m']*2 + ['5m']*2 + ['15m']*2 + ['30m']*2 + ['1h']*2 + ['1d']*2
start = ['2013-01-01 00:00:00']*12
start_fetch_ohlcv(exchange_name,currency,timeframe,start)