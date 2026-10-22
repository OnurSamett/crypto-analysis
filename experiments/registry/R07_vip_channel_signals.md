# R07: Telegram VIP channel signals — design registered BEFORE any message is seen
Tarih / Date: 2026-10-22 · Durum / Status: REGISTERED (design only; the export has not been opened) · Tür / Type: external signal source

**Özet (TR):** Kanalın sinyalleri tek bir strateji gibi sınanır: mesajdan sonraki fiyattan giriş, TP/SL hangisi önce, rastgele giriş temel çizgisiyle permütasyon testi. Ham mesajlar repoya girmez.

**Hypothesis.** The channel's signals have a positive mean **net R-multiple** per signal that is better than random entries with the same TP/SL geometry. (K = 1 primary test, one-sided.)
**Mechanism.** If the provider has genuine skill or information, entries should beat randomly timed entries after realistic costs and latency. A null result is the common outcome for paid signal channels.

**Parsing (allowed before outcomes).** A parser is developed on message **text only** (never looking at later prices). Parsed fields: time, instrument, direction, entry (if given), TP list, SL. Messages without a stop-loss are counted but cannot form a defined R-multiple; they are reported as a share and excluded from the primary metric. Edited/deleted messages are flagged from the export.
**Simulation rules (fixed now).**
* Entry: the open of the first OKX 1-minute candle starting ≥ message time + **60 seconds** (latency). If 1-minute history is unavailable for old messages, fall back to the next 5-minute, then hourly candle open, and report the share per resolution.
* Costs: 0.10% fee per side + 0.05% slippage per side.
* Exit: candle-by-candle, first of TP1 or SL. If both are inside the same candle, **SL is assumed hit first** (pessimistic). Maximum holding 7 days, then close at the market.
* Shorts (if present): simulated as the inverse spot move, ignoring funding and borrow.
* **R-multiple:** net P&L / (entry-to-SL distance). Also reported: win rate, profit factor, longest losing streak.
**Baseline.** 1000 permutations: random entry times on the **same instruments and the same hour-of-day distribution**, the **same TP/SL distances (in %)** and the same holding limit. p-value = share of permutations with mean R ≥ observed (one-sided).
**Split.** Chronological: the first two thirds of signals = "dev", the last third = "validation" (fixed now). Gate criteria apply as written in Addendum 3 (≥30 / ≥15 signals; if fewer, the result is `INSUFFICIENT`).
**Integrity reports (descriptive, no gate).** Share of deleted/edited messages; share of signals whose stated entry differs from the market price at message time by > 0.5% (stale entries); posting delay patterns; success-rate claims by the channel vs our simulation.
**Privacy.** Raw messages stay in `private/` (git-ignored). Only aggregate statistics without the channel name may be published. Links or instructions inside messages are data, never acted on. Nothing is traded on the basis of these signals.

**Pre-check rule (integrity):** the number of independent events is counted **first**. If it is below the Gate thresholds (30 dev / 15 validation, or the forward counts), the candidate is reported as `INSUFFICIENT` and **no return statistics are computed or shown**.
