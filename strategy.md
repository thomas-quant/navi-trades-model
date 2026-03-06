# ICC/CCT Strategy — Mechanical Backtest Specification

> Source: "How This ICC + CCT Trading Strategy Made Everything Click for Me" transcript + diagram screenshots
> Original: ICC by Trades by Sai → CCT (Candlestick Continuation Theory) by Crimson Capital

---

## Overview

1-hour / 1-minute scalping strategy using displacement candles + virgin wick POIs to find high-probability continuation entries.

**Instruments tested**: NQ, Gold
**Sessions**: London, New York AM, New York PM
**Reported results (1 day sample)**: 8W/3L, 73% WR, 11R total (NQ: 6.7R, Gold: 4.3R)

---

## Session Windows (EST)

| Session     | Hours (EST)   |
|-------------|---------------|
| London      | 02:00 – 05:00 |
| New York AM | 09:30 – 12:00 |
| New York PM | 13:00 – 16:00 |

Entries are valid from the open of the next 1H candle after a displacement up until that hour closes.

---

## ATR Reference

All ATR values use the **14-period ATR on the 1H chart**, computed at the time of the displacement candle close. This single ATR value is used for all filters within that hour's setup.

---

## Step 1 — 1H: Identify Displacement Candle

Scan each 1H candle close within session hours.

### Displacement Candle Criteria (ALL must pass)

| Filter | Rule |
|--------|------|
| Range  | `(High - Low) >= 1.3 × ATR` |
| Body   | `Body / Range >= 0.70` where `Body = abs(Open - Close)` |
| Wick consumption | Close must be beyond the tip of at least one virgin wick (see Step 2) |

- If bullish (Close > Open) and closes **above** at least one virgin upper wick tip → look for **longs** next hour
- If bearish (Close < Open) and closes **below** at least one virgin lower wick tip → look for **shorts** next hour
- If both conditions apply in the same hour → **skip the hour** (conflicting displacement)
- If no virgin wicks are consumed → not a valid displacement, skip

---

## Step 2 — 1H: Identify Virgin Wicks → POIs

### Virgin Wick Definition

Scan the previous **10 1H bars** looking left from the displacement candle (crosses session boundaries).

**For a bullish displacement** (looking for longs):
- A virgin wick is the **upper wick** of a prior candle whose **wick tip** has not been touched by any subsequent candle's high since it formed
- Formally: `prior_candle.high` has not been exceeded by any candle between it and the displacement candle

**For a bearish displacement** (looking for shorts):
- A virgin wick is the **lower wick** of a prior candle whose **wick tip** has not been touched by any subsequent candle's low since it formed
- Formally: `prior_candle.low` has not been breached by any candle between it and the displacement candle

**"Touched" definition**: any candle's high (bullish case) or low (bearish case) reaching or exceeding the wick tip invalidates it as virgin.

### POI Placement

- Each qualifying virgin wick tip that the displacement candle's **close** surpasses becomes a POI
- POI is a **single horizontal line at the wick tip (extreme)** — `prior_candle.high` for bullish, `prior_candle.low` for bearish
- If multiple POIs exist, each is a separate level
- When multiple POIs are present, the region between the nearest and farthest POI forms the engagement zone

### POI Priority

Use only the **first (nearest) POI** to the displacement close. Additional POIs are ignored.

---

## Step 3 — 1M: Entry Sequence

After the displacement candle's hour closes, switch to 1M. Watch for the engagement sequence.

### Longs — Required Sequence

1. Price trades down into the POI (1M candle low reaches or crosses POI)
2. A 1M candle **closes below** the POI line
3. A subsequent 1M candle **closes back above** the POI line → entry check begins

### Shorts — Required Sequence

1. Price trades up into the POI
2. A 1M candle **closes above** the POI line
3. A subsequent 1M candle **closes back below** the POI line → entry check begins

---

## Step 4 — Entry Methods

Use whichever method triggers first (CSD or iFVG). Only one entry per attempt.

### Method A — CSD (Change in State of Delivery)

A CSD is a consecutive series of same-direction closes (the pivot/turning-point of the engagement move) fully closed through by a single subsequent candle.

**Long CSD entry**:
- During engagement, track consecutive **bearish** (down-close) candles; record the open of the first candle in the run as the series top
- Entry trigger = a candle closes **above the series top**
- If the run is broken by a candle that does not close above the series top, reset and track the next bearish run
- Example: 3 consecutive down-close candles → one candle closes above the open of the first → CSD long entry

**Short CSD entry** (mirror):
- Track consecutive **bullish** (up-close) candles; series bottom = open of the first candle
- Entry trigger = a candle closes **below the series bottom**

### Method B — Inverse Fair Value Gap (iFVG)

**FVG definition (3-candle imbalance on 1M)**:
- Bullish FVG: `candle[N-1].high < candle[N+1].low` — gap between N-1 high and N+1 low
- Bearish FVG: `candle[N-1].low > candle[N+1].high` — gap between N-1 low and N+1 high

**Minimum FVG size**: `gap >= 0.15 × ATR` (where ATR is the 1H ATR from Step 1). Smaller FVGs are ignored.

**Inversion (iFVG)**:
- For longs: a **bearish FVG** forms during the drop into the POI; price then closes a 1M candle **fully above** the FVG's upper boundary (candle[N-1].high) → enter on close
- For shorts: a **bullish FVG** forms during the push up into POI; price then closes a 1M candle **fully below** the FVG's lower boundary (candle[N-1].low) → enter on close

"Fully through" = close is strictly beyond the FVG boundary, not just inside it.

---

## Step 5 — Stop Loss

- **Longs**: Stop at the **exact low** of the most recent wick formed during POI engagement (no buffer)
- **Shorts**: Stop at the **exact high** of the most recent wick formed during POI engagement

Stop = the lowest low (longs) or highest high (shorts) of all 1M candles from when price first touched the POI to the entry candle close.

---

## Step 6 — Take Profit

**Target**: Most recent swing high (longs) or swing low (shorts) on the **1M or 5M chart**, identified before the entry candle closes.

- Swing high = a 1M/5M candle whose high is higher than both the prior and subsequent candle's high (simple 3-bar pivot)
- Swing low = a 1M/5M candle whose low is lower than both the prior and subsequent candle's low

### Minimum TP Filter

`(TP_price - Entry_price) >= 1.5 × ATR` for longs (reversed for shorts).

If the nearest qualifying swing does not meet this distance, **skip the trade** (no draw on liquidity).

TP is a **limit order at the exact swing extreme**.

---

## Step 7 — Re-entry Rule

- If stopped out on the first entry attempt, watch for a **second entry** using the same POI and same entry methods (CSD or iFVG)
- The second entry requires a fresh Step 3 sequence to complete (price must re-engage the POI)
- **Maximum 2 attempts per POI per hour**
- After 2 stops, the POI is invalidated for the remainder of that hour

---

## Step 8 — Hour Reset

At the close of each 1H candle within the session:
1. Discard all POI lines from the prior hour
2. Evaluate the newly closed 1H candle against Step 1 criteria
3. If valid displacement → mark POI, begin watching on 1M for next hour
4. If no valid displacement → no trade setup for that hour; continue to next candle

At session end, reset everything regardless of open positions.

---

## Parameter Summary

| Parameter | Value |
|-----------|-------|
| ATR period | 14, on 1H |
| Displacement: min range | 1.3× ATR |
| Displacement: min body % | 70% of candle range |
| POI placement | Wick tip (extreme) |
| Virgin wick lookback | 10 × 1H bars (crosses session boundaries) |
| POI count used | First (nearest) only |
| FVG minimum size | 0.15× ATR |
| iFVG entry | Must fully close through FVG boundary |
| CSD entry | Close beyond open of break candle |
| Stop | Exact wick extreme of engagement |
| TP minimum distance | 1.5× ATR |
| TP placement | Nearest 1M/5M swing extreme |
| Max re-entries | 2 per POI per hour |
| Conflicting displacement | Skip hour |
| Sessions (EST) | London 02-05, NY AM 09:30-12, NY PM 13-16 |
