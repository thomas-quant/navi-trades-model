#!/usr/bin/env python3
"""Generate static matplotlib charts for README.md from report.html data."""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter

# ── Data extracted from report.html ──────────────────────────────────────────

times = [
    "2020-09-04","2020-09-04","2020-09-21","2020-10-29","2020-11-03","2020-11-13",
    "2020-11-19","2020-12-07","2020-12-14","2020-12-31","2021-01-05","2021-03-04",
    "2021-03-08","2021-03-09","2021-03-22","2021-04-05","2021-04-06","2021-04-09",
    "2021-04-14","2021-04-23","2021-04-29","2021-05-20","2021-05-25","2021-05-30",
    "2021-06-01","2021-06-03","2021-06-15","2021-09-20","2021-10-05","2021-10-28",
    "2021-11-04","2021-11-10","2021-12-03","2021-12-03","2022-01-12","2022-01-24",
    "2022-01-25","2022-01-25","2022-02-22","2022-02-28","2022-03-28","2022-03-28",
    "2022-04-14","2022-04-18","2022-04-29","2022-04-29","2022-05-02","2022-05-06",
    "2022-05-12","2022-05-19","2022-05-22","2022-06-01","2022-07-01","2022-08-02",
    "2022-08-05","2022-08-11","2022-08-15","2022-08-24","2022-09-20","2022-10-06",
    "2022-10-07","2022-10-11","2022-10-31","2022-11-04","2022-11-04","2022-11-08",
    "2022-11-17","2022-11-23","2022-11-28","2022-12-22","2022-12-30","2023-02-07",
    "2023-02-28","2023-03-13","2023-03-14","2023-03-14","2023-04-17","2023-04-18",
    "2023-04-21","2023-05-04","2023-05-08","2023-05-10","2023-05-15","2023-05-24",
    "2023-05-31","2023-05-31","2023-07-05","2023-07-05","2023-07-17","2023-07-20",
    "2023-08-10","2023-08-10","2023-08-24","2023-09-18","2023-09-20","2023-09-20",
    "2023-09-25","2023-09-27","2023-09-29","2023-10-31","2023-11-08","2023-11-08",
    "2023-11-15","2023-12-15","2024-01-05","2024-01-10","2024-01-11","2024-01-12",
    "2024-01-18","2024-01-26","2024-02-21","2024-04-12","2024-04-24","2024-04-24",
    "2024-05-10","2024-06-25","2024-07-15","2024-07-26","2024-07-29","2024-08-01",
    "2024-08-06","2024-08-20","2024-08-22","2024-08-29","2024-08-30","2024-08-30",
    "2024-10-11","2024-10-17","2024-10-30","2024-10-30","2024-11-13","2024-11-18",
    "2024-12-05","2024-12-09","2024-12-27","2024-12-30","2025-01-16","2025-02-26",
    "2025-02-28","2025-03-13","2025-03-31","2025-04-17","2025-04-22","2025-05-22",
    "2025-06-22","2025-06-27","2025-06-27","2025-07-10","2025-07-15","2025-07-17",
    "2025-07-29","2025-08-05","2025-08-05","2025-08-15","2025-09-15","2025-09-25",
    "2025-10-16","2025-11-07",
]

equity_pct = [0.0,-1.0,2.4504,4.9694,3.9197,2.8805,1.8517,0.8332,-0.1751,-1.1734,-2.1616,-0.6683,-1.6616,3.4858,2.4509,6.8783,5.8095,8.8974,12.2224,11.1002,9.9892,8.8893,10.8665,9.7578,12.5733,15.2,16.9838,15.814,14.6558,20.1514,22.514,21.2889,20.076,18.8752,17.6865,19.4578,18.2632,17.0805,18.9808,21.5372,23.7192,22.482,24.8661,26.8199,25.5517,28.1662,31.511,33.5412,32.2058,30.8837,34.5575,33.2119,31.8798,34.2735,32.9307,31.6014,33.7217,32.3845,31.0606,33.2074,35.8229,34.4647,33.1201,31.7889,35.6931,34.3362,32.9928,35.2301,33.8778,32.539,31.2136,29.9015,28.6024,27.3164,26.0433,24.7828,23.535,22.2996,21.0767,19.8659,18.6672,20.723,19.5158,18.3206,17.1374,15.966,14.8064,13.6583,16.0217,17.9851,16.8053,15.6372,18.792,17.6041,16.428,15.2638,14.1111,12.97,11.8403,10.7219,9.6147,8.5185,7.4333,12.4469,11.3224,10.2092,9.1071,8.016,9.812,14.5447,16.8827,18.8048,17.6167,16.4405,15.2761,14.1234,12.9821,11.8523,10.7338,9.6265,8.5302,7.4449,9.7523,8.6548,7.5682,6.4926,5.4276,4.3734,3.3296,5.3388,7.0282,5.9579,7.9118,10.3606,9.257,8.1644,7.0828,6.012,4.9518,3.9023,2.8633,1.8347,0.8163,-0.1919,2.1203,1.099,0.0881,-0.9128,-1.9037,-2.8847,-1.1871,-2.1752,-0.1705,-1.1688,-2.1571,-3.1355,-1.3971,0.2982]

bh_pct = [0.0,0.68,1.36,2.0401,2.7201,3.4001,4.0801,4.7602,5.4402,6.1202,6.8002,7.4803,8.1603,8.8403,9.5203,10.2003,10.8804,11.5604,12.2404,12.9204,13.6005,14.2805,14.9605,15.6405,16.3206,17.0006,17.6806,18.3606,19.0406,19.7207,20.4007,21.0807,21.7607,22.4408,23.1208,23.8008,24.4808,25.1609,25.8409,26.5209,27.2009,27.8809,28.561,29.241,29.921,30.601,31.2811,31.9611,32.6411,33.3211,34.0012,34.6812,35.3612,36.0412,36.7212,37.4013,38.0813,38.7613,39.4413,40.1214,40.8014,41.4814,42.1614,42.8414,43.5215,44.2015,44.8815,45.5615,46.2416,46.9216,47.6016,48.2816,48.9617,49.6417,50.3217,51.0017,51.6817,52.3618,53.0418,53.7218,54.4018,55.0819,55.7619,56.4419,57.1219,57.802,58.482,59.162,59.842,60.522,61.2021,61.8821,62.5621,63.2421,63.9222,64.6022,65.2822,65.9622,66.6423,67.3223,68.0023,68.6823,69.3623,70.0424,70.7224,71.4024,72.0824,72.7625,73.4425,74.1225,74.8025,75.4826,76.1626,76.8426,77.5226,78.2026,78.8827,79.5627,80.2427,80.9227,81.6028,82.2828,82.9628,83.6428,84.3229,85.0029,85.6829,86.3629,87.0429,87.723,88.403,89.083,89.763,90.4431,91.1231,91.8031,92.4831,93.1632,93.8432,94.5232,95.2032,95.8832,96.5633,97.2433,97.9233,98.6033,99.2834,99.9634,100.6434,101.3234,102.0035,102.6835,103.3635,104.0435,104.7235,105.4036,106.0836,106.7636]

drawdown = [0.0,-1.0,0.0,0.0,-1.0,-1.99,-2.9701,-3.9404,-4.901,-5.852,-6.7935,-5.3708,-6.3171,-1.4134,-2.3993,0.0,-1.0,0.0,0.0,-1.0,-1.99,-2.9701,-1.2082,-2.1962,0.0,0.0,0.0,-1.0,-1.99,0.0,0.0,-1.0,-1.99,-2.9701,-3.9404,-2.4946,-3.4697,-4.435,-2.8839,-0.7973,0.0,-1.0,0.0,0.0,-1.0,0.0,0.0,0.0,-1.0,-1.99,0.0,-1.0,-1.99,-0.2111,-1.209,-2.1969,-0.6212,-1.615,-2.5988,-1.0033,0.0,-1.0,-1.99,-2.9701,-0.0956,-1.0946,-2.0837,-0.4365,-1.4321,-2.4178,-3.3936,-4.3597,-5.3161,-6.2629,-7.2003,-8.1283,-9.047,-9.9566,-10.857,-11.7484,-12.6309,-11.1174,-12.0062,-12.8861,-13.7573,-14.6197,-15.4735,-16.3188,-14.5787,-13.1331,-14.0018,-14.8618,-12.5391,-13.4137,-14.2795,-15.1368,-15.9854,-16.8255,-17.6573,-18.4807,-19.2959,-20.1029,-20.9019,-17.2107,-18.0386,-18.8582,-19.6696,-20.4729,-19.1506,-15.6661,-13.9448,-12.5297,-13.4044,-14.2703,-15.1276,-15.9764,-16.8166,-17.6484,-18.4719,-19.2872,-20.0943,-20.8934,-19.1946,-20.0026,-20.8026,-21.5946,-22.3786,-23.1548,-23.9233,-22.444,-21.2002,-21.9882,-20.5496,-18.7467,-19.5592,-20.3636,-21.16,-21.9484,-22.7289,-23.5016,-24.2666,-25.024,-25.7737,-26.516,-24.8137,-25.5656,-26.3099,-27.0468,-27.7763,-28.4986,-27.2487,-27.9762,-26.5002,-27.2352,-27.9629,-28.6832,-27.4033,-26.1551]

wins_r = [3.485,2.459,1.526,5.234,4.321,2.918,3.053,1.816,2.565,2.333,1.548,4.793,1.966,1.505,1.623,2.149,1.795,1.946,1.565,2.082,2.610,1.544,2.807,1.815,1.611,1.638,1.963,2.963,1.682,1.732,2.079,1.692,2.728,4.667,1.663,4.310,2.041,1.644,2.148,1.944,1.604,1.844,2.269,2.317,1.748,2.049,1.795,1.719]
losses_r = [-1.0] * 108

sess_labels = ["London", "NY AM", "NY PM"]
sess_wr = [33.33, 25.0, 33.33]
sess_r = [11.28, -12.80, 3.84]

meth_labels = ["CSD", "iFVG"]
meth_wr = [28.97, 50.0]
meth_r = [-0.019, 0.419]

# ── Style ─────────────────────────────────────────────────────────────────────

BG       = '#0d1117'
PANEL    = '#161b22'
BORDER   = '#21262d'
FG       = '#c9d1d9'
FG_DIM   = '#7d8590'
GREEN    = '#3fb950'
RED      = '#f85149'
GREY     = '#7d8590'

def apply_dark(ax, ylabel=None, xlabel=None):
    ax.set_facecolor(PANEL)
    ax.figure.patch.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)
    ax.tick_params(colors=FG_DIM, labelsize=9)
    ax.xaxis.label.set_color(FG_DIM)
    ax.yaxis.label.set_color(FG_DIM)
    ax.grid(color=BORDER, linewidth=0.5, linestyle='-')
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel, color=FG_DIM, fontsize=9)
    if xlabel:
        ax.set_xlabel(xlabel, color=FG_DIM, fontsize=9)

os.makedirs('images', exist_ok=True)

idx = list(range(len(equity_pct)))

# ── 1. Equity Curve ───────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG)
ax.plot(idx, equity_pct, color=GREEN, linewidth=1.8, label='Strategy', zorder=3)
ax.plot(idx, bh_pct, color=GREY, linewidth=1.3, linestyle='--', label='Buy & Hold NQ', zorder=2)
ax.axhline(0, color=BORDER, linewidth=0.8, zorder=1)
ax.fill_between(idx, equity_pct, 0, where=[v > 0 for v in equity_pct],
                alpha=0.08, color=GREEN)
ax.fill_between(idx, equity_pct, 0, where=[v <= 0 for v in equity_pct],
                alpha=0.08, color=RED)
apply_dark(ax, ylabel='Return (%)')
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:+.0f}%'))
ax.set_xticks([])
legend = ax.legend(facecolor=PANEL, edgecolor=BORDER, labelcolor=FG, fontsize=9)
# year labels
year_positions = {}
for i, t in enumerate(times):
    y = t[:4]
    if y not in year_positions:
        year_positions[y] = i
for year, pos in year_positions.items():
    ax.axvline(pos, color=BORDER, linewidth=0.5, linestyle=':')
    ax.text(pos + 1, ax.get_ylim()[0] + 1, year, color=FG_DIM, fontsize=7, va='bottom')
plt.tight_layout(pad=0.5)
plt.savefig('images/equity_curve.png', dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print('saved images/equity_curve.png')

# ── 2. Drawdown ───────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 3), facecolor=BG)
ax.fill_between(idx, drawdown, 0, color=RED, alpha=0.25)
ax.plot(idx, drawdown, color=RED, linewidth=1.2)
ax.axhline(0, color=BORDER, linewidth=0.8)
apply_dark(ax, ylabel='Drawdown (%)')
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0f}%'))
ax.set_xticks([])
for year, pos in year_positions.items():
    ax.axvline(pos, color=BORDER, linewidth=0.5, linestyle=':')
    ax.text(pos + 1, ax.get_ylim()[0] * 0.97, year, color=FG_DIM, fontsize=7, va='bottom')
plt.tight_layout(pad=0.5)
plt.savefig('images/drawdown.png', dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print('saved images/drawdown.png')

# ── 3. R-Multiple Distribution ────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(8, 3.5), facecolor=BG)
bins_w = np.arange(1, 6, 0.3)
bins_l = np.arange(-1.5, 0, 0.3)
ax.hist(wins_r, bins=bins_w, color=GREEN, alpha=0.85, label=f'Wins ({len(wins_r)})', zorder=3)
ax.hist(losses_r, bins=bins_l, color=RED, alpha=0.85, label=f'Losses ({len(losses_r)})', zorder=3)
ax.axvline(0, color=BORDER, linewidth=1)
apply_dark(ax, ylabel='Count', xlabel='R-Multiple')
legend = ax.legend(facecolor=PANEL, edgecolor=BORDER, labelcolor=FG, fontsize=9)
plt.tight_layout(pad=0.5)
plt.savefig('images/r_distribution.png', dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print('saved images/r_distribution.png')

# ── 4. Session & Method Breakdown (2×2 grid) ──────────────────────────────────

fig = plt.figure(figsize=(10, 5), facecolor=BG)
gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.35)

# Session
gs_sess = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[0], hspace=0.45)
ax_swr = fig.add_subplot(gs_sess[0])
ax_sr  = fig.add_subplot(gs_sess[1])

colors_swr = [GREEN if v >= 50 else RED for v in sess_wr]
colors_sr  = [GREEN if v >= 0 else RED for v in sess_r]

bars = ax_swr.bar(sess_labels, sess_wr, color=colors_swr, width=0.5, zorder=3)
ax_swr.axhline(50, color=FG_DIM, linewidth=0.8, linestyle='--', zorder=2)
apply_dark(ax_swr, ylabel='Win Rate (%)')
ax_swr.set_title('Session: Win Rate', color=FG, fontsize=10, pad=6)
ax_swr.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0f}%'))
for bar, val in zip(bars, sess_wr):
    ax_swr.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{val:.1f}%', ha='center', va='bottom', color=FG, fontsize=8)

bars2 = ax_sr.bar(sess_labels, sess_r, color=colors_sr, width=0.5, zorder=3)
ax_sr.axhline(0, color=BORDER, linewidth=0.8)
apply_dark(ax_sr, ylabel='Total R')
ax_sr.set_title('Session: Total R', color=FG, fontsize=10, pad=6)
for bar, val in zip(bars2, sess_r):
    offset = 0.3 if val >= 0 else -1.2
    ax_sr.text(bar.get_x() + bar.get_width()/2, bar.get_height() + offset,
                f'{val:+.1f}R', ha='center', va='bottom', color=FG, fontsize=8)

# Method
gs_meth = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[1], hspace=0.45)
ax_mwr = fig.add_subplot(gs_meth[0])
ax_mr  = fig.add_subplot(gs_meth[1])

colors_mwr = [GREEN if v >= 50 else RED for v in meth_wr]
colors_mr  = [GREEN if v >= 0 else RED for v in meth_r]

bars3 = ax_mwr.bar(meth_labels, meth_wr, color=colors_mwr, width=0.4, zorder=3)
ax_mwr.axhline(50, color=FG_DIM, linewidth=0.8, linestyle='--', zorder=2)
apply_dark(ax_mwr, ylabel='Win Rate (%)')
ax_mwr.set_title('Method: Win Rate', color=FG, fontsize=10, pad=6)
ax_mwr.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0f}%'))
for bar, val in zip(bars3, meth_wr):
    ax_mwr.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{val:.1f}%', ha='center', va='bottom', color=FG, fontsize=8)

bars4 = ax_mr.bar(meth_labels, meth_r, color=colors_mr, width=0.4, zorder=3)
ax_mr.axhline(0, color=BORDER, linewidth=0.8)
apply_dark(ax_mr, ylabel='Avg R')
ax_mr.set_title('Method: Avg R', color=FG, fontsize=10, pad=6)
for bar, val in zip(bars4, meth_r):
    offset = 0.01 if val >= 0 else -0.05
    ax_mr.text(bar.get_x() + bar.get_width()/2, bar.get_height() + offset,
                f'{val:+.3f}R', ha='center', va='bottom', color=FG, fontsize=8)

fig.patch.set_facecolor(BG)
plt.savefig('images/breakdown.png', dpi=150, bbox_inches='tight', facecolor=BG)
plt.close()
print('saved images/breakdown.png')

print('All charts generated.')
