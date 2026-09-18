# Softpaws — aggr.trade flow workspaces

Tape-derived order-flow screens for [aggr.trade](https://aggr.trade), one workspace per asset. Each answers the same three questions from the trade tape alone: **what is the market doing** (flow), **who is doing it right now** (activity), and **how much of it is just BTC** (beta).

```
workspaces/
  softpaws-btc-flow.json      BTC. No Beta pane (nothing to regress on) and no Tape-backed band; 5m Activity pane is full-height
  softpaws-avax-flow.json     original alt build (AVAX)
  softpaws-eth-flow.json      generated from AVAX, thresholds x10, beta default 1.2
  softpaws-sol-flow.json      generated from AVAX, thresholds x4,  beta default 1.5
tools/
  convert_asset.py            clones a workspace to a new asset (see "Converting to another asset")
```

## Import

1. aggr.trade → workspace menu (top-left) → **Import** → pick the `.json`.
2. If you have an older copy with the same `id` loaded, delete it first. Same-id imports can silently overwrite or duplicate.
3. Open the market selector on any pane. Anything red is a symbol the public server does not carry — remove it. The lists were built by exchange convention and pruned to symbols known to exist, but coverage changes.
4. Check `Settings → timezone`. The files carry UTC-4; fix it if your other screens differ.
5. Turn audio on in Settings and let the perp tape run for a minute. If it is silent, lower the threshold slider on the tape pane; if it is a wall of sound, raise it. The dollar levels are a starting point, not a calibration.

## Screen layout

24 × 24 grid. Left to right:

| x | pane | tf | what it is |
|---|---|---|---|
| 0–3 | **Spot Trades** (tall) + stats strip | live | spot tape, all spot venues. Stats: TRADES, VOLUME, TRADES Δ |
| 3–6 | **Perp Trades** (upper) | live | perp tape, all perp venues. Stats: TRADES, VOLUME Δ, TRADES Δ, 1m LIQUIDATIONS |
| 3–6 | **Liquidations** (lower, unnamed) | live | perp *liquidation-only* tape. Nothing here is a trade |
| 6–16 | **30m** | 30m | the main flow chart, 12 bands |
| 16–24 | **Activity 5m** (upper) | 5m | z-scored size-bucket and venue activity |
| 16–24 | **Beta vs BTC** (lower) | 30m | ratio, rolling beta, alpha residual |

Read it top-down on the 30m chart, glance right for who is doing it and whether BTC explains it, and let the tapes tell you when to look up.

## The 30m flow chart, band by band

Bands are listed in screen order. Colours: **blue** = buy / spot-led, **pink** = sell / perp-led, **green** = positive / alpha bid, **red** = negative / alpha offer, unless noted.

### Price + Keltner Channel
Aggregate candles across every non-hidden market in the pane. Keltner is a 200-EMA basis with a ±10 × average-range envelope — a slow regime frame, not a signal. Price living outside the cloud means the 30m trend is stretched relative to its own range.

### CVD / CVD SPOT / CVD PERP (one band, three overlaid lines)
Cumulative volume delta (market buys − market sells, running total). Aggregate, spot only, perp only. Each is on its own scale so the shapes are comparable, not the magnitudes.

- All three rising with price → real bid.
- Perp CVD rising while spot CVD flat or falling → leveraged chase; tends to round-trip.
- Spot CVD rising while price flat → absorption at the offer, or spot accumulating into perp selling. Check the Absorption band.
- Divergence between price and CVD is the primary "something is off" tell on this screen.

### Spot-Perp Aggression
Per-bar buy-aggression ratio of spot minus that of perps, each bounded [−1, +1], smoothed 6 bars.
**Blue above zero** = spot is being bought harder than perps (spot-led; tends to hold). **Pink below zero** = perp-led (tends to fade). A rally with the bar pink the whole way is a rally to sell into.

### Tape-backed moves
Bar return in bps, split by whether volume was above or below its 50-bar average.
**Bright yellow/orange** = price moved on *thin* tape — market makers repricing off the BTC beta, no real flow arrived. **Dim blue/pink** = the move happened on real volume. On an alt, a screen full of bright bars means you are watching BTC, not the asset. Combine with the Beta pane's residual to confirm.

### Delta Spot / Delta Perp
Per-bar net delta for spot and for perps, as histograms. Bar colour is bright when that bar's volume exceeded mean + 1σ (14-bar), dim otherwise. Read bright bars only; the rest is noise. Bright perp delta against dim spot delta is the classic squeeze fuel.

### Premium
(Aggregate spot − aggregate perp) / perp, in bps, as a cloud around zero. Above zero: spot trades over perps (perp funding pressure is negative, shorts crowded). Below zero: perps over spot (longs paying). Scale-free, so it reads the same in every regime.

### CB Premium
Coinbase `X-USD` vs Binance `Xusdt`, in bps. Two things are drawn on the same band:

**Histogram — the signal.** Deviation of the premium from its own 24-hour mean. **Green above zero** = the US bid is strengthening versus its own norm, **orange below zero** = weakening. Relative, never absolute.

**Raw level — two lines.** The raw premium usually sits a few bps *negative* because USDT trades off par, so its sign rarely flips and is easy to miss. It is therefore split: **blue line above zero** = Coinbase is printing over Binance (Coinbase blue; rare, and a real US bid when it happens); **yellow line below zero** = Binance over Coinbase (Binance yellow; the normal state). Whichever half is inactive lies flat on the zero line. aggr fixes a line's colour at creation, so this split is how a "line that changes colour" is done.

Read: histogram green *and* blue line visible = US spot leading with conviction. Histogram green but only yellow below = US bid improving from a weak base; less weight.

### Absorption
Bars where the close direction disagrees with the net delta *on elevated volume* (> mean + 0.5σ over 50 bars).
**Green up-bar** = bar closed up while net delta was negative — market sells hit resting bids and price still rose (passive accumulation). **Red down-bar** = closed down on net buying — market buys hit resting offers and price still fell (passive distribution). Height is |delta| absorbed. Two or three in a row at a level is a level worth respecting.

### Liquidations + Liq Cascade (one band)
Base histogram: short liquidations up, long liquidations down, in USD. Overlaid in bright **magenta (shorts) / yellow (longs)** are bars where total liquidations exceeded mean + 2σ over 100 bars — the cascade flag. A cascade *into* a level with CVD holding is the sweep-then-move setup; a cascade with CVD breaking is continuation.

### Volume
Aggregate volume with delta overlay. Bars exceeding mean + 2σ (100-bar) are highlighted. Mostly a sanity check for the bands above: if nothing here is highlighted, treat everything else on the bar as thin-tape noise.

## Activity 5m — who is doing it right now

The cumulative CVDs above tell you *level* and *who is bigger*. This pane answers a different question: **is a given participant doing something unusual for them, right now.** Every line is a z-score of that participant's own smoothed net flow against its own last 24 hours (288 × 5m bars), so a +2 from a small bucket and a +2 from a big bucket render the same height. Dotted lines at ±2σ.

### Spot Size Activity / Perp Size Activity
Trades are bucketed by average size per market order (volume ÷ order count) against an adaptive 50-bar band: **Big** (> mean + 1σ), **Mid** (within the band), **Small** (< mean − 1σ). Three lines per pane: big (thick), mid, small.

- Big above +2 while price is flat → size is loading quietly. Watch for the move.
- Small above +2 while Big is near zero or negative → retail chasing, size not participating. Fade-prone.
- Big and Small diverging in sign → the transfer is happening. Direction of Big wins more often than not.

### Venue z (one band, six lines + reference bands)
Same z-score construction per venue: BINANCE spot, BINANCE_FUTURES, BYBIT (spot + perp), COINBASE (spot + INTX perp), HYPERLIQUID, OKEX (spot + swaps). Each venue's net flow is the sum of every market it has *in this pane*, so the script is regenerated when the market list changes.

Read it as *which crowd is moving*: Coinbase = US spot, Binance spot = global spot, Binance Futures / Bybit / OKX = offshore leverage, Hyperliquid = on-chain perps. A US-spot-led move (Coinbase leading, spot aggression blue) and an offshore-perp-led move (Bybit/Binance Futures leading, aggression pink) look identical on price and behave completely differently afterwards.

## Beta vs BTC — how much of this is just Bitcoin

All three indicators reference `BINANCE_FUTURES:btcusdt`, which is in the pane's market list and hidden so it does not contaminate the aggregate bar. Both legs are Binance perps for the tightest, best-covered comparison.

### X/BTC ratio
Asset priced in BTC, scaled for readability (AVAX ×1e6, ETH ×1e3, SOL ×1e5). Rising = outperforming BTC. This is the line that answers "is the alt bid real" on a multi-day view.

### Rolling beta
Regression slope through the origin of the asset's 30m close-to-close returns on BTC's, over 288 bars (~6 days). ~1 = chop regime, the asset just tracks BTC. Drifting well above 1 = impulse regime, the asset is amplifying BTC. Typical impulse readings: ETH ~2, SOL 2–3, AVAX 3–4. The residual below computes its own (longer-window) β; this line is the regime read.

### Beta residual
Asset return minus (β × BTC return) in bps, smoothed 3 bars. The part of the move that BTC does **not** explain.
**Green above zero** = outperformed its beta → an alpha bid exists. **Red below zero** = underperformed → alpha offer. **Flat around zero** = it is all BTC; stop looking at the asset and look at BTC.

β is computed inside the indicator as a through-origin regression over `betaWindow` bars — default **1440 × 30m = 30 days**, the structural beta. That window is a deliberate choice: with a long window, a regime shift to higher beta *shows up as alpha* (a week of 3× beta in an impulse prints green throughout); with a short window it gets absorbed into β and vanishes from the residual. The Rolling beta line above uses 6 days, so the two disagreeing is itself information — the residual is green *because* the regime changed.

Untick `toggleRolling` to fall back to the manual `beta` option (AVAX 1.4, ETH 1.2, SOL 1.5). The first 30 days of loaded history compute β over fewer bars and are noisier; if the public server serves less than 30 days of 30m bars, β is effectively over whatever is loaded — shorten `betaWindow` if the line looks jumpy.

## Reading the three together

A rough decision flow, top-down:

1. **Beta residual flat?** Then this is a BTC trade wearing an alt costume. Trade BTC or wait.
2. **Residual green + Tape-backed bars dim (real volume) + Spot-Perp Aggression blue** → spot-led alpha bid. The setup that holds.
3. **Residual green + Tape-backed bright (thin) + Aggression pink** → perp-led repricing on no flow. Expect a round-trip; look for the Liq Cascade to mark the exhaustion.
4. **CVD spot rising, price flat, Absorption green stacking** → someone is accumulating into sellers. Direction is up when the offers run out; the Perp tape going loud is the trigger.
5. **Venue z: Coinbase leading** → US spot money; slower, stickier. **Bybit/Binance Futures leading** → fast money; take profits faster.
6. **Size Activity: Big above +2, Small below 0** → size is positioned against retail. Take the side of Big.

## Tape thresholds (audio and colour)

Trades panes colour and sound by USD size. Four trade tiers plus four liquidation tiers per tape. Current starting points:

| tape | AVAX | ETH (×10) | SOL (×4) |
|---|---|---|---|
| Perp trades | 1.3k / 13k / 38k / 128k | 13k / 130k / 380k / 1.3M | 5.1k / 51k / 150k / 510k |
| Spot trades | 620 / 6.2k / 19k / 62k | 6.2k / 62k / 190k / 620k | 2.5k / 25k / 74k / 250k |
| Liquidation tape | 1k / 10k / 30k / 100k | 10k / 100k / 300k / 1M | 4k / 40k / 120k / 400k |

Use the multiplier slider on each pane rather than editing amounts. The right level is the one where a normal minute produces a few sounds and a real move produces a lot.

## Converting to another asset

`tools/convert_asset.py` clones a workspace to a new asset. It swaps the asset token in every market symbol (case-preserved, so each exchange's convention survives), rewrites bare market refs in scripts, **regenerates the venue-z sums from the resulting market list**, renames the ratio indicator, sets the beta default, scales every USD threshold, and asserts the source asset string is gone.

```sh
python3 tools/convert_asset.py workspaces/softpaws-avax-flow.json \
    --asset ETH --threshold-scale 10 --add-market DERIBIT:ETH-PERPETUAL \
    -o workspaces/softpaws-eth-flow.json

python3 tools/convert_asset.py workspaces/softpaws-avax-flow.json \
    --asset SOL --threshold-scale 4 \
    -o workspaces/softpaws-sol-flow.json
```

Flags: `--beta` and `--ratio-mult` override the per-asset defaults; `--add-market EXCHANGE:pair` appends a symbol to every perp-side pane (used to add Deribit's inverse ETH perp, which the 1:1 mapping does not produce); `--source-asset` if auto-detect from the id fails.

Threshold scale is relative liquidity. From AVAX: ETH ≈ 10×, SOL ≈ 4×, BTC ≈ 30×. Tune by ear afterwards. Adaptive indicators — size buckets, absorption, cascade, every z-score — are scale-free and need nothing.

After converting, validate with the aggr-workspace skill's `validate_workspace.py`, then import.

## Things that will bite you

- **Identifiers starting with `var`** (`variance`, `varBB`) are mangled by aggr's preprocessor and kill the pane with `execution failed` and no location. Same caution for names starting with `bar`, `time`, `sum`, `sma`, `cum`, `avg`, `ema`.
- **A title word that equals a variable name** renders the label as `vars[0].state …`. Rename the variable.
- **`hiddenMarkets` does not affect `source()`**. It only removes a market from the plain `bar`/`vbuy`/`vsell` aggregate. The size-bucket indicators use `source(..., type=spot)` and will include hidden markets.
- **A market missing from the selector** (red) is missing from the server. Remove it; it does nothing but flicker.
- **After a blank pane**, export the workspace and read `states.<pane>.indicatorsErrors` — aggr writes the indicator id and the JS error there.
- **aggr is a tape tool.** No order-book depth, no open interest. Those live elsewhere (Velo, Coinalyze, exchange APIs). Everything on these screens is derived from executed trades.
