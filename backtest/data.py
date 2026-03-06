import pandas as pd


def load_1m(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = df.set_index('DateTime_ET').sort_index()
    drop_cols = [c for c in ['DateTime_UTC', 'session', 'window'] if c in df.columns]
    df = df.drop(columns=drop_cols)
    return df


def build_1h(df_1m: pd.DataFrame) -> pd.DataFrame:
    agg = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum',
    }
    df_1h = df_1m.resample('1h', label='left', closed='left').agg(agg)
    df_1h = df_1h.dropna(subset=['Open', 'High', 'Low', 'Close'])
    return df_1h


def get_session_hours(session: str) -> list:
    """
    Returns a list of 1H bar open-times (as hour offsets from midnight ET)
    that fall within each session window.

    strategy.md Session Windows (EST):
      London      02:00 – 05:00  → 1H bars at 02, 03, 04
      New York AM 09:30 – 12:00  → 1H bars at 10, 11  (09:00 bar is pre-RTH)
      New York PM 13:00 – 16:00  → 1H bars at 13, 14, 15

    Note: NY AM opens at 09:30 so the 09:00–10:00 1H bar is a mixed
    pre-market / in-session bar and is excluded to avoid bias.
    """
    if session == 'london':
        return [2, 3, 4]
    elif session == 'ny_am':
        return [10, 11]   # 09:00 bar excluded — pre-RTH open
    elif session == 'ny_pm':
        return [13, 14, 15]
    else:
        raise ValueError(f'Unknown session: {session}')


def get_session_end_hour(session: str) -> int:
    """
    Returns the closing hour (ET) of each session.
    Used as the hard cutoff for the entry window.
    """
    if session == 'london':
        return 5     # 05:00 ET
    elif session == 'ny_am':
        return 12    # 12:00 ET
    elif session == 'ny_pm':
        return 16    # 16:00 ET
    else:
        raise ValueError(f'Unknown session: {session}')

