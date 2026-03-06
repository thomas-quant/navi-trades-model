"""Quick check: how many setups have overlapping session_end windows?"""
from backtest.data import load_1m, build_1h
from backtest.indicators import wilder_atr
from backtest.setup import find_setups

df_1m = load_1m('data/nq_1m.parquet')
df_1h = build_1h(df_1m)
atr_series = wilder_atr(df_1h, period=14)
setups = find_setups(df_1m, df_1h, atr_series, ['london', 'ny_am', 'ny_pm'])

triggered = 0
no_bars = 0
no_touch = 0
no_trigger = 0

from backtest.entry import scan_entry_hour
import pandas as pd

for setup in setups:
    bars = df_1m.loc[setup.next_hour_start: setup.session_end - pd.Timedelta(minutes=1)]
    if len(bars) == 0:
        no_bars += 1
        continue
    if setup.direction == 'long':
        touched = (bars['Low'] <= setup.poi).any()
    else:
        touched = (bars['High'] >= setup.poi).any()
    if not touched:
        no_touch += 1
        continue
    sigs = scan_entry_hour(bars, setup.poi, setup.direction, setup.atr, attempt=1)
    if sigs:
        triggered += 1
    else:
        no_trigger += 1

print(f"With session-wide window:")
print(f"  No bars        : {no_bars}")
print(f"  No POI touch   : {no_touch} ({100*no_touch/len(setups):.1f}%)")
print(f"  Touch, no trig : {no_trigger}")
print(f"  Triggered      : {triggered} ({100*triggered/len(setups):.1f}%)")
