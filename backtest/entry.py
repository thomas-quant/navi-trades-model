from dataclasses import dataclass
from typing import List, Optional

import pandas as pd


@dataclass
class FVG:
    upper: float
    lower: float
    formed_at: pd.Timestamp


@dataclass
class EntrySignal:
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    method: str    # 'csd' | 'ifvg'
    attempt: int


def scan_entry_hour(
    df_1m_hour: pd.DataFrame,
    poi: float,
    direction: str,
    atr: float,
    attempt: int = 1,
) -> List[EntrySignal]:
    """
    State machine scanning 1M bars within one entry hour.
    Returns a list with at most one EntrySignal (first trigger wins).

    Implements strategy.md Step 3 — the full 3-step engagement sequence:
      1. WAITING  → price's low/high TOUCHES the POI (intrabar)
      2. TOUCHED  → a candle CLOSES beyond the POI (engagement confirmed)
      3. ENGAGED  → a subsequent candle CLOSES back above/below POI
                    → transition to ENTRY_HUNT, start tracking CSD/iFVG

    CSD definition:
      Track consecutive same-direction closes during the bounce/pushback.
      Entry triggers when a single candle closes beyond the open of the
      FIRST candle in that run.  Broken run = reset and track the next.
    """
    signals: List[EntrySignal] = []

    # States: WAITING → TOUCHED → ENGAGED → ENTRY_HUNT → TRIGGERED
    state = 'WAITING'

    fvgs_formed: List[FVG] = []
    engagement_bars: list = []   # bars accumulated from first POI touch onward

    # CSD series tracking (only active in ENTRY_HUNT)
    csd_series_open: Optional[float] = None   # open of FIRST candle in current run

    min_fvg = 0.15 * atr

    for i in range(len(df_1m_hour)):
        bar = df_1m_hour.iloc[i]

        # ── WAITING: watch for intrabar POI touch ─────────────────────────────
        if state == 'WAITING':
            touched = (
                (direction == 'long'  and bar.Low  <= poi) or
                (direction == 'short' and bar.High >= poi)
            )
            if touched:
                engagement_bars = [bar]
                # If the same bar ALSO closes through the POI, advance directly
                if direction == 'long' and bar.Close < poi:
                    state = 'ENGAGED'
                elif direction == 'short' and bar.Close > poi:
                    state = 'ENGAGED'
                else:
                    state = 'TOUCHED'

        # ── TOUCHED: wait for a close beyond the POI ──────────────────────────
        elif state == 'TOUCHED':
            engagement_bars.append(bar)
            if direction == 'long' and bar.Close < poi:
                state = 'ENGAGED'
            elif direction == 'short' and bar.Close > poi:
                state = 'ENGAGED'
            # If price moves back without ever closing through, stay TOUCHED
            # (intrabar touches but no close-through keep us in TOUCHED)

        # ── ENGAGED: wait for a close BACK above/below POI ───────────────────
        elif state == 'ENGAGED':
            engagement_bars.append(bar)

            # Accumulate FVGs formed DURING the engagement (the pullback move)
            if len(engagement_bars) >= 3:
                b0 = engagement_bars[-3]
                b1 = engagement_bars[-2]
                b2 = engagement_bars[-1]
                if direction == 'long':
                    gap = b0.Low - b2.High
                    if gap >= min_fvg:
                        fvgs_formed.append(
                            FVG(upper=b0.Low, lower=b2.High, formed_at=b1.name)
                        )
                else:
                    gap = b2.Low - b0.High
                    if gap >= min_fvg:
                        fvgs_formed.append(
                            FVG(upper=b2.Low, lower=b0.High, formed_at=b1.name)
                        )

            # Check for close-back (step 3.3) → transition to ENTRY_HUNT
            if direction == 'long' and bar.Close > poi:
                state = 'ENTRY_HUNT'
                # This bar is the first bounce bar — start a bearish run
                # (it closed bullish above POI, so no bearish run yet)
                csd_series_open = None
            elif direction == 'short' and bar.Close < poi:
                state = 'ENTRY_HUNT'
                csd_series_open = None

            # If price keeps diving below POI (for longs), remain ENGAGED

        # ── ENTRY_HUNT: track CSD runs and iFVG inversions ───────────────────
        elif state == 'ENTRY_HUNT':
            engagement_bars.append(bar)
            triggered = False

            # --- CSD tracking ------------------------------------------------
            if direction == 'long':
                if bar.Close < bar.Open:
                    # Bearish candle — continues or starts a run
                    if csd_series_open is None:
                        csd_series_open = bar.Open
                else:
                    # Bullish candle — potential CSD trigger
                    if csd_series_open is not None and bar.Close > csd_series_open:
                        stop = min(b.Low for b in engagement_bars)
                        signals.append(EntrySignal(
                            entry_time=bar.name,
                            entry_price=bar.Close,
                            stop_price=stop,
                            method='csd',
                            attempt=attempt,
                        ))
                        triggered = True
                    csd_series_open = None  # reset on any non-bearish bar

            else:  # short
                if bar.Close > bar.Open:
                    # Bullish candle — continues or starts a run
                    if csd_series_open is None:
                        csd_series_open = bar.Open
                else:
                    # Bearish candle — potential CSD trigger
                    if csd_series_open is not None and bar.Close < csd_series_open:
                        stop = max(b.High for b in engagement_bars)
                        signals.append(EntrySignal(
                            entry_time=bar.name,
                            entry_price=bar.Close,
                            stop_price=stop,
                            method='csd',
                            attempt=attempt,
                        ))
                        triggered = True
                    csd_series_open = None  # reset on any non-bullish bar

            if triggered:
                state = 'TRIGGERED'
                break

            # --- iFVG: close fully through a formed FVG ----------------------
            for fvg in fvgs_formed:
                if direction == 'long' and bar.Close > fvg.upper:
                    stop = min(b.Low for b in engagement_bars)
                    signals.append(EntrySignal(
                        entry_time=bar.name,
                        entry_price=bar.Close,
                        stop_price=stop,
                        method='ifvg',
                        attempt=attempt,
                    ))
                    state = 'TRIGGERED'
                    triggered = True
                    break
                elif direction == 'short' and bar.Close < fvg.lower:
                    stop = max(b.High for b in engagement_bars)
                    signals.append(EntrySignal(
                        entry_time=bar.name,
                        entry_price=bar.Close,
                        stop_price=stop,
                        method='ifvg',
                        attempt=attempt,
                    ))
                    state = 'TRIGGERED'
                    triggered = True
                    break

            if triggered:
                break

            # If price re-crosses back through POI (into it again), re-engage
            if direction == 'long' and bar.Close < poi:
                state = 'ENGAGED'
                csd_series_open = None
            elif direction == 'short' and bar.Close > poi:
                state = 'ENGAGED'
                csd_series_open = None

    return signals
