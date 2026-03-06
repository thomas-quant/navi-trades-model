"""
report.py — compute stats and generate dark-theme HTML report with Plotly charts.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import List

import numpy as np
import pandas as pd

from backtest.engine import Trade


# ──────────────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────────────

def compute_stats(trades: List[Trade], df_1m: pd.DataFrame) -> dict:
    if not trades:
        return {}

    # Filter out skipped trades (no_tp_found) for most metrics
    active = [t for t in trades if t.exit_reason != 'no_tp_found']
    total = len(active)
    if total == 0:
        return {}

    r_multiples = np.array([t.r_multiple for t in active])
    wins = [t for t in active if t.r_multiple > 0]
    losses = [t for t in active if t.r_multiple <= 0]

    win_rate = len(wins) / total * 100

    # Equity curve (1% risk, compounding)
    equity = [100.0]
    for t in sorted(active, key=lambda x: x.entry_time):
        equity.append(equity[-1] * (1 + t.r_multiple * 0.01))

    total_return = (equity[-1] / equity[0] - 1) * 100

    # Drawdown
    eq_arr = np.array(equity)
    running_max = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - running_max) / running_max * 100
    max_dd = float(dd.min())

    # Sharpe (annualised, by calendar day)
    daily: dict = defaultdict(float)
    for t in active:
        day = t.date
        daily[day] += t.r_multiple * 0.01
    daily_r = np.array(list(daily.values()))
    if len(daily_r) > 1 and daily_r.std() > 0:
        sharpe = float(daily_r.mean() / daily_r.std() * np.sqrt(252))
    else:
        sharpe = float('nan')

    expectancy = float(r_multiples.mean())
    avg_rr_wins = float(np.mean([t.r_multiple for t in wins])) if wins else float('nan')
    med_rr_wins = float(np.median([t.r_multiple for t in wins])) if wins else float('nan')

    sum_wins = sum(t.r_multiple for t in wins)
    sum_losses = abs(sum(t.r_multiple for t in losses))
    profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else float('inf')

    # B&H
    first_trade_time = sorted(active, key=lambda x: x.entry_time)[0].entry_time
    bh_start_idx = df_1m.index.searchsorted(first_trade_time, side='left')
    bh_start_price = float(df_1m['Close'].iloc[bh_start_idx])
    bh_end_price = float(df_1m['Close'].iloc[-1])
    bh_return = (bh_end_price / bh_start_price - 1) * 100

    # Session breakdown
    session_stats = {}
    for sess in ['london', 'ny_am', 'ny_pm']:
        st = [t for t in active if t.session == sess]
        if st:
            sw = [t for t in st if t.r_multiple > 0]
            session_stats[sess] = {
                'trades': len(st),
                'win_rate': len(sw) / len(st) * 100,
                'total_r': sum(t.r_multiple for t in st),
            }

    # Method breakdown
    method_stats = {}
    for meth in ['csd', 'ifvg']:
        mt = [t for t in active if t.entry_method == meth]
        if mt:
            mw = [t for t in mt if t.r_multiple > 0]
            method_stats[meth] = {
                'trades': len(mt),
                'win_rate': len(mw) / len(mt) * 100,
                'avg_r': np.mean([t.r_multiple for t in mt]),
            }

    # Monthly breakdown
    monthly_stats = {}
    for t in active:
        key = t.entry_time.strftime('%Y-%m')
        if key not in monthly_stats:
            monthly_stats[key] = []
        monthly_stats[key].append(t)

    monthly_rows = []
    for month in sorted(monthly_stats.keys()):
        mt = monthly_stats[month]
        mw = [t for t in mt if t.r_multiple > 0]
        rs = [t.r_multiple for t in mt]
        monthly_rows.append({
            'month': month,
            'trades': len(mt),
            'total_r': sum(rs),
            'win_pct': len(mw) / len(mt) * 100,
            'avg_r': np.mean(rs),
            'best': max(rs),
            'worst': min(rs),
        })

    # Date range
    all_times = sorted([t.entry_time for t in active])
    date_range = f'{all_times[0].strftime("%Y-%m-%d")} to {all_times[-1].strftime("%Y-%m-%d")}'

    return {
        'total_trades': total,
        'total_all': len(trades),
        'skipped': len(trades) - total,
        'win_rate': win_rate,
        'total_return': total_return,
        'sharpe': sharpe,
        'expectancy': expectancy,
        'avg_rr_wins': avg_rr_wins,
        'med_rr_wins': med_rr_wins,
        'max_drawdown': max_dd,
        'profit_factor': profit_factor,
        'bh_return': bh_return,
        'equity': equity,
        'drawdown': dd.tolist(),
        'r_multiples': r_multiples.tolist(),
        'session_stats': session_stats,
        'method_stats': method_stats,
        'monthly_rows': monthly_rows,
        'date_range': date_range,
        'active_trades': sorted(active, key=lambda x: x.entry_time),
    }


# ──────────────────────────────────────────────────────────────────────────────
# HTML generation
# ──────────────────────────────────────────────────────────────────────────────

_PLOTLY_LAYOUT = dict(
    paper_bgcolor='#161b22',
    plot_bgcolor='#0d1117',
    font=dict(color='#c9d1d9', family='-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif'),
    xaxis=dict(gridcolor='#21262d', zerolinecolor='#21262d'),
    yaxis=dict(gridcolor='#21262d', zerolinecolor='#21262d'),
    margin=dict(l=40, r=20, t=30, b=40),
)


def _json(obj) -> str:
    return json.dumps(obj)


def _fmt(val, decimals=2, pct=False, signed=True) -> str:
    if val != val:  # nan
        return 'N/A'
    if pct:
        s = f'{val:+.{decimals}f}%' if signed else f'{val:.{decimals}f}%'
    else:
        s = f'{val:+.{decimals}f}' if signed else f'{val:.{decimals}f}'
    return s


def _color_class(val) -> str:
    if val > 0:
        return 'positive'
    if val < 0:
        return 'negative'
    return 'neutral'


def build_html(stats: dict, trades: List[Trade]) -> str:
    if not stats:
        return '<html><body>No trades found.</body></html>'

    active = stats['active_trades']
    equity = stats['equity']
    dd = stats['drawdown']
    r_mult = stats['r_multiples']

    # Equity curve times
    times = [active[0].entry_time] + [t.exit_time for t in active]
    times_str = [t.strftime('%Y-%m-%d %H:%M') for t in times]

    bh_return = stats['bh_return']
    # B&H curve: linear interpolation normalised to 0% at first trade
    bh_curve = [bh_return * i / (len(equity) - 1) for i in range(len(equity))]

    equity_pct = [(e / equity[0] - 1) * 100 for e in equity]

    # ── Charts data ──────────────────────────────────────────────────────────

    equity_chart = {
        'data': [
            {
                'x': times_str,
                'y': [round(v, 4) for v in equity_pct],
                'type': 'scatter',
                'mode': 'lines',
                'name': 'Strategy',
                'line': {'color': '#3fb950', 'width': 2},
            },
            {
                'x': times_str,
                'y': [round(v, 4) for v in bh_curve],
                'type': 'scatter',
                'mode': 'lines',
                'name': 'Buy & Hold NQ',
                'line': {'color': '#7d8590', 'width': 1.5, 'dash': 'dash'},
            },
        ],
        'layout': {
            **_PLOTLY_LAYOUT,
            'yaxis': {'ticksuffix': '%', 'gridcolor': '#21262d', 'zerolinecolor': '#21262d'},
            'legend': {'bgcolor': 'rgba(0,0,0,0)', 'borderwidth': 0},
        },
    }

    dd_chart = {
        'data': [
            {
                'x': times_str,
                'y': [round(v, 4) for v in dd],
                'type': 'scatter',
                'mode': 'lines',
                'fill': 'tozeroy',
                'name': 'Drawdown',
                'line': {'color': '#f85149', 'width': 1},
                'fillcolor': 'rgba(248,81,73,0.15)',
            }
        ],
        'layout': {
            **_PLOTLY_LAYOUT,
            'yaxis': {'ticksuffix': '%', 'gridcolor': '#21262d', 'zerolinecolor': '#21262d'},
        },
    }

    pos_r = [v for v in r_mult if v > 0]
    neg_r = [v for v in r_mult if v <= 0]
    rdist_chart = {
        'data': [
            {
                'x': pos_r,
                'type': 'histogram',
                'name': 'Wins',
                'marker': {'color': '#3fb950'},
                'opacity': 0.85,
            },
            {
                'x': neg_r,
                'type': 'histogram',
                'name': 'Losses',
                'marker': {'color': '#f85149'},
                'opacity': 0.85,
            },
        ],
        'layout': {
            **_PLOTLY_LAYOUT,
            'barmode': 'overlay',
            'xaxis': {'title': 'R-Multiple', 'gridcolor': '#21262d'},
            'yaxis': {'title': 'Count', 'gridcolor': '#21262d'},
            'legend': {'bgcolor': 'rgba(0,0,0,0)'},
        },
    }

    # Session bar chart
    ss = stats.get('session_stats', {})
    sess_labels = [s.replace('_', ' ').title() for s in ss.keys()]
    sess_wr = [ss[s]['win_rate'] for s in ss]
    sess_r = [ss[s]['total_r'] for s in ss]
    sess_colors_wr = ['#3fb950' if v >= 50 else '#f85149' for v in sess_wr]
    sess_colors_r = ['#3fb950' if v >= 0 else '#f85149' for v in sess_r]

    session_chart = {
        'data': [
            {
                'x': sess_labels,
                'y': sess_wr,
                'type': 'bar',
                'name': 'Win Rate %',
                'marker': {'color': sess_colors_wr},
            }
        ],
        'layout': {
            **_PLOTLY_LAYOUT,
            'yaxis': {'ticksuffix': '%', 'gridcolor': '#21262d'},
            'showlegend': False,
        },
    }

    session_r_chart = {
        'data': [
            {
                'x': sess_labels,
                'y': sess_r,
                'type': 'bar',
                'name': 'Total R',
                'marker': {'color': sess_colors_r},
            }
        ],
        'layout': {
            **_PLOTLY_LAYOUT,
            'yaxis': {'title': 'Total R', 'gridcolor': '#21262d'},
            'showlegend': False,
        },
    }

    # Method bar chart
    ms = stats.get('method_stats', {})
    meth_labels = [m.upper() for m in ms.keys()]
    meth_wr = [ms[m]['win_rate'] for m in ms]
    meth_r = [ms[m]['avg_r'] for m in ms]
    meth_colors_wr = ['#3fb950' if v >= 50 else '#f85149' for v in meth_wr]
    meth_colors_r = ['#3fb950' if v >= 0 else '#f85149' for v in meth_r]

    method_wr_chart = {
        'data': [
            {
                'x': meth_labels,
                'y': meth_wr,
                'type': 'bar',
                'marker': {'color': meth_colors_wr},
            }
        ],
        'layout': {
            **_PLOTLY_LAYOUT,
            'yaxis': {'ticksuffix': '%', 'gridcolor': '#21262d'},
            'showlegend': False,
        },
    }

    method_r_chart = {
        'data': [
            {
                'x': meth_labels,
                'y': meth_r,
                'type': 'bar',
                'marker': {'color': meth_colors_r},
            }
        ],
        'layout': {
            **_PLOTLY_LAYOUT,
            'yaxis': {'title': 'Avg R', 'gridcolor': '#21262d'},
            'showlegend': False,
        },
    }

    # ── Stat cards ───────────────────────────────────────────────────────────
    def stat_card(label, value, cls='', detail=''):
        return f'''
    <div class="stat-card">
        <div class="label">{label}</div>
        <div class="value {cls}">{value}</div>
        {f'<div class="detail">{detail}</div>' if detail else ''}
    </div>'''

    pf = stats['profit_factor']
    pf_str = f'{pf:.2f}' if pf != float('inf') else '∞'

    cards = ''.join([
        stat_card('Total Trades', stats['total_trades'],
                  detail=f'{stats["skipped"]} skipped (no TP)'),
        stat_card('Win Rate', f'{stats["win_rate"]:.1f}%',
                  cls=_color_class(stats["win_rate"] - 50)),
        stat_card('Total Return', f'{stats["total_return"]:+.2f}%',
                  cls=_color_class(stats["total_return"])),
        stat_card('Sharpe', f'{stats["sharpe"]:.2f}' if stats["sharpe"] == stats["sharpe"] else 'N/A',
                  cls=_color_class(stats["sharpe"] if stats["sharpe"] == stats["sharpe"] else 0)),
        stat_card('Expectancy', f'{stats["expectancy"]:+.3f}R',
                  cls=_color_class(stats["expectancy"])),
        stat_card('Avg RR (Wins)', f'{stats["avg_rr_wins"]:.2f}R' if stats["avg_rr_wins"] == stats["avg_rr_wins"] else 'N/A',
                  cls='positive'),
        stat_card('Median RR (Wins)', f'{stats["med_rr_wins"]:.2f}R' if stats["med_rr_wins"] == stats["med_rr_wins"] else 'N/A'),
        stat_card('Max Drawdown', f'{stats["max_drawdown"]:.2f}%',
                  cls='negative'),
        stat_card('Profit Factor', pf_str,
                  cls=_color_class(pf - 1 if pf != float('inf') else 1)),
        stat_card('B&H Return', f'{stats["bh_return"]:+.2f}%',
                  cls=_color_class(stats["bh_return"]),
                  detail='NQ from first trade date'),
    ])

    # ── Monthly table ────────────────────────────────────────────────────────
    monthly_rows_html = ''
    for row in stats['monthly_rows']:
        tr_cls = 'green' if row['total_r'] >= 0 else 'red'
        monthly_rows_html += f'''<tr>
            <td class="highlight">{row['month']}</td>
            <td>{row['trades']}</td>
            <td class="{tr_cls} highlight">{row['total_r']:+.2f}</td>
            <td>{row['win_pct']:.1f}%</td>
            <td>{row['avg_r']:+.3f}</td>
            <td class="green">{row['best']:+.2f}</td>
            <td class="red">{row['worst']:+.2f}</td>
        </tr>'''

    # ── Session breakdown table ───────────────────────────────────────────────
    session_table_html = ''
    for sess, sd in stats['session_stats'].items():
        wr_cls = 'green' if sd['win_rate'] >= 50 else 'red'
        tr_cls = 'green' if sd['total_r'] >= 0 else 'red'
        session_table_html += f'''<tr>
            <td class="highlight">{sess.replace('_', ' ').title()}</td>
            <td>{sd['trades']}</td>
            <td class="{wr_cls}">{sd['win_rate']:.1f}%</td>
            <td class="{tr_cls}">{sd['total_r']:+.2f}</td>
        </tr>'''

    # ── Method breakdown table ────────────────────────────────────────────────
    method_table_html = ''
    for meth, md in stats['method_stats'].items():
        wr_cls = 'green' if md['win_rate'] >= 50 else 'red'
        r_cls = 'green' if md['avg_r'] >= 0 else 'red'
        method_table_html += f'''<tr>
            <td class="highlight">{meth.upper()}</td>
            <td>{md['trades']}</td>
            <td class="{wr_cls}">{md['win_rate']:.1f}%</td>
            <td class="{r_cls}">{md['avg_r']:+.3f}</td>
        </tr>'''

    # ── Trade log ────────────────────────────────────────────────────────────
    log_rows = ''
    for t in sorted(active, key=lambda x: x.entry_time):
        dir_cls = 'long' if t.direction == 'long' else 'short'
        r_cls = 'green' if t.r_multiple > 0 else 'red'
        tp_str = f'{t.tp_price:.2f}' if t.tp_price == t.tp_price else '&mdash;'
        log_rows += f'''<tr>
            <td>{t.entry_time.strftime('%Y-%m-%d')}</td>
            <td>{t.entry_time.strftime('%H:%M')}</td>
            <td><span class="tag {dir_cls}">{t.direction.upper()}</span></td>
            <td>{t.session.replace('_', ' ').title()}</td>
            <td>{t.entry_method.upper()}</td>
            <td>{t.entry_price:.2f}</td>
            <td>{t.stop_price:.2f}</td>
            <td>{tp_str}</td>
            <td>{t.exit_price:.2f}</td>
            <td class="{r_cls}">{t.r_multiple:+.2f}R</td>
        </tr>'''

    # ── Full HTML ─────────────────────────────────────────────────────────────
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ICC/CCT Strategy &mdash; Backtest Report</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
        background: #0a0e17;
        color: #c9d1d9;
        padding: 24px;
        line-height: 1.6;
    }}
    .header {{
        text-align: center;
        padding: 32px 0;
        border-bottom: 1px solid #21262d;
        margin-bottom: 32px;
    }}
    .header h1 {{
        font-size: 28px;
        color: #e6edf3;
        margin-bottom: 8px;
    }}
    .header .subtitle {{
        color: #7d8590;
        font-size: 14px;
    }}
    .stats-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin-bottom: 32px;
    }}
    .stat-card {{
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }}
    .stat-card .label {{
        font-size: 12px;
        color: #7d8590;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }}
    .stat-card .value {{
        font-size: 24px;
        font-weight: 700;
        color: #e6edf3;
    }}
    .stat-card .value.positive {{ color: #3fb950; }}
    .stat-card .value.negative {{ color: #f85149; }}
    .stat-card .value.neutral {{ color: #d29922; }}
    .stat-card .detail {{
        font-size: 11px;
        color: #7d8590;
        margin-top: 4px;
    }}
    .section {{
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 24px;
        margin-bottom: 24px;
    }}
    .section h2 {{
        font-size: 18px;
        color: #e6edf3;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid #21262d;
    }}
    .section h3 {{
        font-size: 14px;
        color: #c9d1d9;
        margin-bottom: 12px;
        margin-top: 20px;
    }}
    .chart-container {{
        width: 100%;
        height: 350px;
        margin-bottom: 16px;
    }}
    .chart-container.tall {{ height: 400px; }}
    .chart-container.short {{ height: 250px; }}
    .two-col {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 24px;
    }}
    @media (max-width: 800px) {{
        .two-col {{ grid-template-columns: 1fr; }}
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }}
    th, td {{
        padding: 10px 14px;
        text-align: left;
        border-bottom: 1px solid #21262d;
    }}
    th {{
        color: #7d8590;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
    }}
    td {{ color: #c9d1d9; }}
    tr:last-child td {{ border-bottom: none; }}
    .highlight {{ color: #e6edf3; font-weight: 600; }}
    .green {{ color: #3fb950; }}
    .red {{ color: #f85149; }}
    .yellow {{ color: #d29922; }}
    .tag {{
        display: inline-block;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    .tag.long {{ background: rgba(63, 185, 80, 0.15); color: #3fb950; }}
    .tag.short {{ background: rgba(248, 81, 73, 0.15); color: #f85149; }}
    .trade-log-wrap {{
        max-height: 500px;
        overflow-y: auto;
        border: 1px solid #21262d;
        border-radius: 6px;
    }}
    .trade-log-wrap table {{ margin-bottom: 0; }}
    .trade-log-wrap thead th {{
        position: sticky;
        top: 0;
        background: #161b22;
        z-index: 1;
    }}
</style>
</head>
<body>

<div class="header">
    <h1>ICC/CCT Strategy &mdash; Backtest Report</h1>
    <div class="subtitle">NQ Futures &mdash; 1-minute bars &mdash; {stats['date_range']}</div>
</div>

<div class="stats-grid">
{cards}
</div>

<!-- Equity Curve -->
<div class="section">
    <h2>Equity Curve vs Buy &amp; Hold</h2>
    <div class="chart-container tall" id="equity-chart"></div>
</div>

<!-- Drawdown -->
<div class="section">
    <h2>Drawdown</h2>
    <div class="chart-container" id="dd-chart"></div>
</div>

<!-- R-Multiple Distribution -->
<div class="section">
    <h2>R-Multiple Distribution</h2>
    <div class="chart-container" id="rdist-chart"></div>
</div>

<!-- Session & Method Breakdown -->
<div class="section">
    <h2>Session Breakdown</h2>
    <div class="two-col">
        <div>
            <h3>Win Rate by Session</h3>
            <div class="chart-container short" id="sess-wr-chart"></div>
        </div>
        <div>
            <h3>Total R by Session</h3>
            <div class="chart-container short" id="sess-r-chart"></div>
        </div>
    </div>
    <table>
        <thead><tr><th>Session</th><th>Trades</th><th>Win Rate</th><th>Total R</th></tr></thead>
        <tbody>{session_table_html}</tbody>
    </table>
</div>

<div class="section">
    <h2>Entry Method Breakdown</h2>
    <div class="two-col">
        <div>
            <h3>Win Rate by Method</h3>
            <div class="chart-container short" id="meth-wr-chart"></div>
        </div>
        <div>
            <h3>Avg R by Method</h3>
            <div class="chart-container short" id="meth-r-chart"></div>
        </div>
    </div>
    <table>
        <thead><tr><th>Method</th><th>Trades</th><th>Win Rate</th><th>Avg R</th></tr></thead>
        <tbody>{method_table_html}</tbody>
    </table>
</div>

<!-- Monthly Breakdown -->
<div class="section">
    <h2>Monthly Breakdown</h2>
    <table>
        <thead>
            <tr><th>Month</th><th>Trades</th><th>Total R</th><th>Win%</th><th>Avg R</th><th>Best</th><th>Worst</th></tr>
        </thead>
        <tbody>{monthly_rows_html}</tbody>
    </table>
</div>

<!-- Trade Log -->
<div class="section">
    <h2>Trade Log</h2>
    <div class="trade-log-wrap">
        <table>
            <thead>
                <tr>
                    <th>Date</th><th>Time</th><th>Dir</th><th>Session</th>
                    <th>Method</th><th>Entry</th><th>Stop</th><th>TP</th>
                    <th>Exit</th><th>R</th>
                </tr>
            </thead>
            <tbody>{log_rows}</tbody>
        </table>
    </div>
</div>

<script>
var cfg = {{responsive: true}};
Plotly.newPlot('equity-chart', {_json(equity_chart['data'])}, {_json(equity_chart['layout'])}, cfg);
Plotly.newPlot('dd-chart', {_json(dd_chart['data'])}, {_json(dd_chart['layout'])}, cfg);
Plotly.newPlot('rdist-chart', {_json(rdist_chart['data'])}, {_json(rdist_chart['layout'])}, cfg);
Plotly.newPlot('sess-wr-chart', {_json(session_chart['data'])}, {_json(session_chart['layout'])}, cfg);
Plotly.newPlot('sess-r-chart', {_json(session_r_chart['data'])}, {_json(session_r_chart['layout'])}, cfg);
Plotly.newPlot('meth-wr-chart', {_json(method_wr_chart['data'])}, {_json(method_wr_chart['layout'])}, cfg);
Plotly.newPlot('meth-r-chart', {_json(method_r_chart['data'])}, {_json(method_r_chart['layout'])}, cfg);
</script>
</body>
</html>'''

    return html
