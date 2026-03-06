from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .data import get_session_hours, get_session_end_hour


@dataclass
class Setup:
    ts: pd.Timestamp            # displacement bar open time (1H)
    direction: str              # 'long' | 'short'
    poi: float
    atr: float
    session: str
    next_hour_start: pd.Timestamp
    next_hour_end: pd.Timestamp
    session_end: pd.Timestamp   # hard cutoff for entry window (session close)
    displacement_time: pd.Timestamp


def is_displacement(
    bar,
    atr: float,
    atr_mult: float = 1.3,
    body_pct: float = 0.70,
) -> Optional[str]:
    candle_range = bar.High - bar.Low
    if candle_range < atr_mult * atr:
        return None
    body = abs(bar.Close - bar.Open)
    if body / candle_range < body_pct:
        return None
    if bar.Close > bar.Open:
        return 'long'
    elif bar.Close < bar.Open:
        return 'short'
    return None


def find_poi(
    df_1h: pd.DataFrame,
    disp_ts: pd.Timestamp,
    direction: str,
    atr: float,
    lookback: int = 10,
) -> Optional[float]:
    """
    Look back up to `lookback` 1H bars before the displacement.
    A wick tip is virgin if no bar between it and the displacement
    has reached or exceeded that level.  The displacement close must
    have moved past the wick tip.  Returns the nearest qualifying
    wick tip to the displacement close, or None.
    """
    disp_pos = df_1h.index.get_loc(disp_ts)
    disp_bar = df_1h.iloc[disp_pos]

    start = max(0, disp_pos - lookback)
    prior = df_1h.iloc[start:disp_pos]  # bars strictly before displacement

    if len(prior) == 0:
        return None

    candidates = []

    if direction == 'long':
        highs = prior['High'].values
        n = len(highs)
        for j in range(n):
            wick_tip = highs[j]
            # Virgin: no bar after j (within the lookback) has High >= wick_tip
            if j + 1 < n and highs[j + 1:].max() >= wick_tip:
                continue
            # POI: displacement close must be above the wick tip
            if disp_bar.Close > wick_tip:
                candidates.append(wick_tip)
        candidates.sort(reverse=True)  # nearest to disp close = highest first

    else:  # short
        lows = prior['Low'].values
        n = len(lows)
        for j in range(n):
            wick_tip = lows[j]
            if j + 1 < n and lows[j + 1:].min() <= wick_tip:
                continue
            if disp_bar.Close < wick_tip:
                candidates.append(wick_tip)
        candidates.sort()  # nearest to disp close = lowest first

    return candidates[0] if candidates else None


def find_setups(
    df_1m: pd.DataFrame,
    df_1h: pd.DataFrame,
    atr_series: pd.Series,
    sessions: list,
    atr_mult: float = 1.3,
    body_pct: float = 0.70,
    poi_lookback: int = 10,
) -> list:
    setups = []
    one_hour = pd.Timedelta(hours=1)

    dates = df_1m.index.normalize().unique()
    atr_index_set = set(atr_series.dropna().index)
    df_1h_index_set = set(df_1h.index)

    for date in dates:
        for session in sessions:
            hours = get_session_hours(session)
            session_ts = [date + pd.Timedelta(hours=h) for h in hours]
            valid_ts = [t for t in session_ts if t in df_1h_index_set]
            if not valid_ts:
                continue

            for ts in valid_ts:
                if ts not in atr_index_set:
                    continue
                atr = atr_series[ts]
                if np.isnan(atr) or atr <= 0:
                    continue

                bar = df_1h.loc[ts]
                direction = is_displacement(bar, atr, atr_mult=atr_mult, body_pct=body_pct)
                if direction is None:
                    continue

                # strategy.md Step 1: skip conflicting displacement
                # (a candle that passes as BOTH long and short is ambiguous)
                # is_displacement already returns only one direction based on
                # Close > Open / Close < Open, so a single bar cannot be truly
                # both. However, we guard against doji-like cases here.
                opposite = 'short' if direction == 'long' else 'long'
                if is_displacement(bar, atr, atr_mult=atr_mult, body_pct=body_pct) == opposite:
                    continue  # conflicting — skip hour

                poi = find_poi(df_1h, ts, direction, atr, lookback=poi_lookback)
                if poi is None:
                    continue

                setups.append(
                    Setup(
                        ts=ts,
                        direction=direction,
                        poi=poi,
                        atr=atr,
                        session=session,
                        next_hour_start=ts + one_hour,
                        next_hour_end=ts + 2 * one_hour,
                        session_end=date + pd.Timedelta(hours=get_session_end_hour(session)),
                        displacement_time=ts,
                    )
                )

    return setups
