"""Quick funnel diagnostic — run once, then delete."""
import pandas as pd
from backtest.data import load_1m, build_1h
from backtest.indicators import wilder_atr
from backtest.setup import find_setups

df_1m = load_1m('data/nq_1m.parquet')
df_1h = build_1h(df_1m)
atr_series = wilder_atr(df_1h, period=14)
setups = find_setups(df_1m, df_1h, atr_series, ['london', 'ny_am', 'ny_pm'])
print(f'Total setups: {len(setups)}')

no_hour_bars = 0
no_engagement = 0   # price never closes through POI
no_trigger = 0      # engaged but CSD/iFVG never fired
triggered = 0

WAIT = 'WAITING'
ENG = 'ENGAGED'

for setup in setups:
    entry_hour = df_1m.loc[
        setup.next_hour_start: setup.next_hour_end - pd.Timedelta(minutes=1)
    ]
    if len(entry_hour) == 0:
        no_hour_bars += 1
        continue

    # Did price ever close through POI?
    closes = entry_hour['Close']
    if setup.direction == 'long':
        engaged_ever = (closes < setup.poi).any()
    else:
        engaged_ever = (closes > setup.poi).any()

    if not engaged_ever:
        no_engagement += 1
        continue

    # --- simplified state machine just to check trigger ---
    state = WAIT
    break_candle = None
    eng_bars = []
    fired = False
    min_fvg = 0.15 * setup.atr

    for i in range(len(entry_hour)):
        bar = entry_hour.iloc[i]
        if state == WAIT:
            if setup.direction == 'long' and bar.Close < setup.poi:
                break_candle = bar; state = ENG; eng_bars = [bar]
            elif setup.direction == 'short' and bar.Close > setup.poi:
                break_candle = bar; state = ENG; eng_bars = [bar]
        elif state == ENG:
            eng_bars.append(bar)
            # CSD
            if setup.direction == 'long' and bar.Close > setup.poi and bar.Close > break_candle.Open:
                fired = True; break
            elif setup.direction == 'short' and bar.Close < setup.poi and bar.Close < break_candle.Open:
                fired = True; break
            # iFVG
            if len(eng_bars) >= 3:
                b0, b2 = eng_bars[-3], eng_bars[-1]
                if setup.direction == 'long' and b0.Low > b2.High:
                    gap = b0.Low - b2.High
                    if gap >= min_fvg and bar.Close > b0.Low:
                        fired = True; break
                elif setup.direction == 'short' and b0.High < b2.Low:
                    gap = b2.Low - b0.High
                    if gap >= min_fvg and bar.Close < b0.High:
                        fired = True; break

    if fired:
        triggered += 1
    else:
        no_trigger += 1

print(f'  No 1M bars in entry hour : {no_hour_bars}')
print(f'  Price never crossed POI  : {no_engagement}')
print(f'  Engaged but no trigger   : {no_trigger}')
print(f'  Triggered entry          : {triggered}')
print()
# Direction split
long_s = [s for s in setups if s.direction == 'long']
short_s = [s for s in setups if s.direction == 'short']
print(f'  Long setups: {len(long_s)}  |  Short setups: {len(short_s)}')
# Session split
for sess in ['london', 'ny_am', 'ny_pm']:
    ss = [s for s in setups if s.session == sess]
    print(f'  {sess}: {len(ss)} setups')

# Sample a few "no engagement" setups to see how far price was from POI
import numpy as np
sample = []
for setup in setups:
    entry_hour = df_1m.loc[setup.next_hour_start: setup.next_hour_end - pd.Timedelta(minutes=1)]
    if len(entry_hour) == 0:
        continue
    closes = entry_hour['Close']
    if setup.direction == 'long':
        if not (closes < setup.poi).any():
            min_close = closes.min()
            gap = min_close - setup.poi   # positive = price stayed above POI
            sample.append(gap / setup.atr)
    else:
        if not (closes > setup.poi).any():
            max_close = closes.max()
            gap = setup.poi - max_close
            sample.append(gap / setup.atr)

if sample:
    arr = np.array(sample)
    print(f'\nNo-engagement gap (ATR units): mean={arr.mean():.2f}  median={np.median(arr):.2f}  p25={np.percentile(arr,25):.2f}')
    print(f'  (positive = price stayed above/below POI by this many ATRs)')
    neg = (arr < 0).sum()
    print(f'  {neg}/{len(arr)} cases where price DID cross POI intrabar but never CLOSED through it')
