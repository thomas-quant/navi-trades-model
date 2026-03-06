#!/usr/bin/env python3
"""
run_backtest.py — CLI entry point for the ICC/CCT strategy backtest.

Usage:
    python run_backtest.py [--data data/nq_1m.parquet] [--output report.html]
                          [--sessions london,ny_am,ny_pm]
"""
import argparse
import time

from backtest.data import load_1m, build_1h
from backtest.indicators import wilder_atr
from backtest.setup import find_setups
from backtest.engine import run
from report import compute_stats, build_html


def main():
    parser = argparse.ArgumentParser(description='ICC/CCT Strategy Backtest')
    parser.add_argument('--data', default='data/nq_1m.parquet')
    parser.add_argument('--output', default='report.html')
    parser.add_argument('--sessions', default='london,ny_am,ny_pm')
    parser.add_argument('--atr-mult', type=float, default=1.3,
                        help='Min displacement range as ATR multiple (default 1.3)')
    parser.add_argument('--body-pct', type=float, default=0.70,
                        help='Min body/range ratio for displacement (default 0.70)')
    parser.add_argument('--poi-lookback', type=int, default=10,
                        help='Number of 1H bars to look back for virgin wicks (default 10)')
    parser.add_argument('--min-rr', type=float, default=1.5,
                        help='Minimum R:R for TP target (default 1.5). '
                             'TP swing must be at least min-rr × stop distance from entry.')
    args = parser.parse_args()

    sessions = [s.strip() for s in args.sessions.split(',')]

    # ── Load data ─────────────────────────────────────────────────────────────
    t0 = time.time()
    print(f'Loading data from {args.data} ...')
    df_1m = load_1m(args.data)
    print(f'  Loaded {len(df_1m):,} 1M bars  ({df_1m.index[0]} → {df_1m.index[-1]})')

    # ── Build 1H frame + ATR ──────────────────────────────────────────────────
    print('Building 1H bars ...')
    df_1h = build_1h(df_1m)
    print(f'  {len(df_1h):,} 1H bars')

    print('Computing ATR(14) on 1H ...')
    atr_series = wilder_atr(df_1h, period=14)

    # ── Find setups ───────────────────────────────────────────────────────────
    print(f'Scanning for setups  (sessions: {sessions}, atr_mult={args.atr_mult}, '
          f'body_pct={args.body_pct}, poi_lookback={args.poi_lookback}) ...')
    setups = find_setups(df_1m, df_1h, atr_series, sessions,
                         atr_mult=args.atr_mult, body_pct=args.body_pct,
                         poi_lookback=args.poi_lookback)
    print(f'  Found {len(setups):,} setups')

    # ── Run engine ────────────────────────────────────────────────────────────
    print(f'Executing trades ...  (min-rr={args.min_rr})')
    trades = run(df_1m, setups, min_rr=args.min_rr)
    active = [t for t in trades if t.exit_reason != 'no_tp_found']
    print(f'  Executed {len(trades):,} trades  ({len(active):,} with valid TP, '
          f'{len(trades) - len(active):,} skipped)')

    elapsed = time.time() - t0
    print(f'  Done in {elapsed:.1f}s')

    if not active:
        print('No tradeable setups found — check strategy parameters.')
        return

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats = compute_stats(trades, df_1m)

    print('\n── Summary ─────────────────────────────────────────────────────')
    print(f'  Trades          : {stats["total_trades"]}')
    print(f'  Win Rate        : {stats["win_rate"]:.1f}%')
    print(f'  Expectancy      : {stats["expectancy"]:+.3f}R')
    print(f'  Avg RR (wins)   : {stats["avg_rr_wins"]:.2f}R')
    print(f'  Total Return    : {stats["total_return"]:+.2f}%')
    print(f'  Max Drawdown    : {stats["max_drawdown"]:.2f}%')
    print(f'  Sharpe          : {stats["sharpe"]:.2f}')
    print(f'  Profit Factor   : {stats["profit_factor"]:.2f}')
    print(f'  B&H Return      : {stats["bh_return"]:+.2f}%')
    print('────────────────────────────────────────────────────────────────')

    # ── Build report ──────────────────────────────────────────────────────────
    print(f'\nGenerating report → {args.output} ...')
    html = build_html(stats, trades)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'  Report saved to {args.output}')


if __name__ == '__main__':
    main()
