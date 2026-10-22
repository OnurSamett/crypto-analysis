# Forward paper-trading record (English translation)

Turkish original: [`START.md`](START.md). Per Protocol Addendum 1 (see [`../PROTOCOL.en.md`](../PROTOCOL.en.md)). Configuration, thresholds and parameters are **not changed** during this process.

| | E3 (regime filter) | E4 (regime + entry confirmation) |
|---|---|---|
| Configuration | `experiments/e3_regime.toml` | `experiments/e4_confirm.toml` |
| config_hash | `52813d434468` | `07eb693eccb5` |
| Start | 2026-10-22 08:19 UTC | 2026-10-22 08:19 UTC |
| Executor | `sim` (local ledger, no real orders) | `sim` |
| Starting capital | 10,000 USDT | 10,000 USDT |
| First trades | bought BTC, ETH, SOL | bought BTC, ETH; SOL waited for lack of confirmation |

Run (one round after the daily candle close at 00:00 UTC; the loop waits by itself):

```bash
python3 -m okx_karar --config experiments/e3_regime.toml paper --executor sim
python3 -m okx_karar --config experiments/e4_confirm.toml paper --executor sim
```

Evaluation: at least 180 days **and** at least 15 completed trades (whichever comes later). Criterion: Sharpe and maximum drawdown relative to
buy-and-hold over the same period. State files are under `state/` (not committed); trade records and a daily equity summary will be added here during evaluation.

Known limitation: paper trading uses no resting orders and simulates fills at the close (the backtest fills at the next open).
E3/E4 run without stops, so the stop limitation does not affect these two configurations.
