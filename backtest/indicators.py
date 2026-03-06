import numpy as np
import pandas as pd


def wilder_atr(df_1h: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df_1h['High'].values
    low = df_1h['Low'].values
    close = df_1h['Close'].values
    n = len(close)

    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    atr = np.full(n, np.nan)
    if n >= period:
        atr[period - 1] = tr[:period].mean()
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return pd.Series(atr, index=df_1h.index)


def swing_highs(df_1m: pd.DataFrame, n: int = 1) -> pd.Series:
    high = df_1m['High']
    mask = (high > high.shift(n)) & (high > high.shift(-n))
    result = pd.Series(np.nan, index=df_1m.index, dtype=float)
    result[mask] = high[mask]
    return result


def swing_lows(df_1m: pd.DataFrame, n: int = 1) -> pd.Series:
    low = df_1m['Low']
    mask = (low < low.shift(n)) & (low < low.shift(-n))
    result = pd.Series(np.nan, index=df_1m.index, dtype=float)
    result[mask] = low[mask]
    return result
