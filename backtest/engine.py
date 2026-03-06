from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from .entry import EntrySignal, scan_entry_hour
from .setup import Setup


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    stop_price: float
    tp_price: float
    direction: str          # 'long' | 'short'
    exit_reason: str        # 'tp' | 'sl' | 'no_tp_found'
    r_multiple: float
    session: str
    entry_method: str       # 'csd' | 'ifvg'
    attempt: int
    poi_level: float
    displacement_time: pd.Timestamp
    date: pd.Timestamp


def _find_tp(
    df_1m: pd.DataFrame,
    before_idx: int,
    entry_price: float,
    direction: str,
    risk: float,
    lookback: int = 2000,
    min_rr: float = 1.5,
) -> Optional[float]:
    """
    Find the most recent *confirmed* 1M structural pivot before entry_idx
    that meets the min R:R requirement.

    A confirmed pivot high is a 3-bar local high whose nearest swing-high
    neighbours on BOTH sides are strictly lower than it (i.e. it is the
    dominant high between two lower peaks).  Mirror logic for lows.

    This ensures we target meaningful structural levels rather than any
    random 1-bar wick that pokes above its immediate neighbours.
    """
    start = max(0, before_idx - lookback)
    highs = df_1m['High'].values
    lows  = df_1m['Low'].values
    min_dist = min_rr * risk

    if direction == 'long':
        # --- Pass 1: collect all 3-bar pivot high indices ---
        pivot_idx = [
            i for i in range(start + 1, before_idx - 1)
            if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]
        ]
        if len(pivot_idx) < 3:
            # Not enough pivots to confirm structure; fall back to simple pivots
            for i in range(before_idx - 2, start + 1, -1):
                if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                    candidate = highs[i]
                    if candidate > entry_price and (candidate - entry_price) >= min_dist:
                        return float(candidate)
            return None

        # --- Pass 2: confirmed pivots — lower pivot on each side ---
        confirmed = []
        for k in range(1, len(pivot_idx) - 1):
            i     = pivot_idx[k]
            left  = pivot_idx[k - 1]   # nearest pivot to the left
            right = pivot_idx[k + 1]   # nearest pivot to the right
            if highs[i] > highs[left] and highs[i] > highs[right]:
                confirmed.append(i)

        # Most recent confirmed pivot first
        for i in reversed(confirmed):
            candidate = highs[i]
            if candidate > entry_price and (candidate - entry_price) >= min_dist:
                return float(candidate)

    else:  # short — mirror for lows
        pivot_idx = [
            i for i in range(start + 1, before_idx - 1)
            if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]
        ]
        if len(pivot_idx) < 3:
            for i in range(before_idx - 2, start + 1, -1):
                if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                    candidate = lows[i]
                    if candidate < entry_price and (entry_price - candidate) >= min_dist:
                        return float(candidate)
            return None

        confirmed = []
        for k in range(1, len(pivot_idx) - 1):
            i     = pivot_idx[k]
            left  = pivot_idx[k - 1]
            right = pivot_idx[k + 1]
            if lows[i] < lows[left] and lows[i] < lows[right]:
                confirmed.append(i)

        for i in reversed(confirmed):
            candidate = lows[i]
            if candidate < entry_price and (entry_price - candidate) >= min_dist:
                return float(candidate)

    return None



def _simulate(
    df_1m: pd.DataFrame,
    after_idx: int,
    entry_price: float,
    stop_price: float,
    tp_price: float,
    direction: str,
) -> Tuple[float, Optional[pd.Timestamp], str]:
    """
    Scan forward from after_idx until TP or SL is hit.
    SL is checked before TP within the same bar (conservative).
    Returns (exit_price, exit_time, exit_reason).
    """
    highs = df_1m['High'].values
    lows = df_1m['Low'].values
    idx_arr = df_1m.index

    for i in range(after_idx, len(df_1m)):
        if direction == 'long':
            if lows[i] <= stop_price:
                return stop_price, idx_arr[i], 'sl'
            if highs[i] >= tp_price:
                return tp_price, idx_arr[i], 'tp'
        else:
            if highs[i] >= stop_price:
                return stop_price, idx_arr[i], 'sl'
            if lows[i] <= tp_price:
                return tp_price, idx_arr[i], 'tp'

    return entry_price, None, 'no_exit'


def _build_trade(
    signal: EntrySignal,
    setup: Setup,
    df_1m: pd.DataFrame,
    min_rr: float = 1.5,
) -> Optional[Trade]:
    """
    Given an EntrySignal, find TP and simulate to exit. Returns Trade or None.
    TP minimum distance = min_rr × risk (pure R:R filter).
    """
    entry_idx = df_1m.index.searchsorted(signal.entry_time, side='right')

    risk = abs(signal.entry_price - signal.stop_price)
    if risk == 0:
        return None

    # --- Find TP: nearest 1M swing pivot at least min_rr × risk away ---
    tp = _find_tp(df_1m, entry_idx, signal.entry_price, setup.direction,
                  risk=risk, min_rr=min_rr)

    if tp is None:
        return Trade(
            entry_time=signal.entry_time,
            exit_time=signal.entry_time,
            entry_price=signal.entry_price,
            exit_price=signal.entry_price,
            stop_price=signal.stop_price,
            tp_price=float('nan'),
            direction=setup.direction,
            exit_reason='no_tp_found',
            r_multiple=0.0,
            session=setup.session,
            entry_method=signal.method,
            attempt=signal.attempt,
            poi_level=setup.poi,
            displacement_time=setup.displacement_time,
            date=setup.ts.normalize(),
        )

    # --- Simulate forward ---
    exit_price, exit_time, exit_reason = _simulate(
        df_1m, entry_idx, signal.entry_price, signal.stop_price, tp, setup.direction
    )

    if exit_time is None:
        return None  # data ended before exit — discard

    if risk == 0:
        return None

    if setup.direction == 'long':
        r = (exit_price - signal.entry_price) / risk
    else:
        r = (signal.entry_price - exit_price) / risk

    return Trade(
        entry_time=signal.entry_time,
        exit_time=exit_time,
        entry_price=signal.entry_price,
        exit_price=exit_price,
        stop_price=signal.stop_price,
        tp_price=tp,
        direction=setup.direction,
        exit_reason=exit_reason,
        r_multiple=r,
        session=setup.session,
        entry_method=signal.method,
        attempt=signal.attempt,
        poi_level=setup.poi,
        displacement_time=setup.displacement_time,
        date=setup.ts.normalize(),
    )


def run(
    df_1m: pd.DataFrame,
    setups: List[Setup],
    min_rr: float = 1.5,
) -> List[Trade]:
    trades: List[Trade] = []

    for setup in setups:
        # Entry window: from next hourly bar open until session close.
        # If the displacement IS the last bar of the session, session_end <= next_hour_start
        # so fall back to a 1-hour window (old behaviour) to avoid an empty slice.
        window_end = (
            setup.session_end
            if setup.session_end > setup.next_hour_start
            else setup.next_hour_end
        )
        entry_hour_bars = df_1m.loc[
            setup.next_hour_start: window_end - pd.Timedelta(minutes=1)
        ]
        if len(entry_hour_bars) == 0:
            continue

        # --- Attempt 1 ---
        signals = scan_entry_hour(
            entry_hour_bars, setup.poi, setup.direction, setup.atr, attempt=1
        )
        if not signals:
            continue

        trade1 = _build_trade(signals[0], setup, df_1m, min_rr=min_rr)
        if trade1 is None:
            continue
        trades.append(trade1)

        # --- Re-entry (attempt 2) only if first attempt stopped out ---
        if trade1.exit_reason == 'sl' and signals[0].attempt == 1:
            remaining = entry_hour_bars.loc[trade1.exit_time + pd.Timedelta(minutes=1):]
            if len(remaining) == 0:
                continue

            signals2 = scan_entry_hour(
                remaining, setup.poi, setup.direction, setup.atr, attempt=2
            )
            if not signals2:
                continue

            trade2 = _build_trade(signals2[0], setup, df_1m, min_rr=min_rr)
            if trade2 is not None:
                trades.append(trade2)

    return trades
