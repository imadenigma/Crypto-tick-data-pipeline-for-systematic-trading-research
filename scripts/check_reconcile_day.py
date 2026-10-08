from orderflow.data.catalog import DatasetSpec
from orderflow.data.load import raw_zip, read_zip
from orderflow.data.validate import reconcile_trade

MARKET = "futures/um"
SYMBOL = "BTCUSDT"
DAY = "2024-08-05"

agg_spec = DatasetSpec("aggTrades", "daily")
trade_spec = DatasetSpec("trades", "daily")

agg_path = raw_zip(agg_spec, MARKET, SYMBOL, DAY)
trade_path = raw_zip(trade_spec, MARKET, SYMBOL, DAY)

agg = read_zip(agg_path, "aggTrades")
trades = read_zip(trade_path, "trades")

result = reconcile_trade(agg, trades)

for (key, value) in result.items():
    print(f"{key:20s}: {value}")