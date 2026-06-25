"""
charts.py — Matplotlib chart renderers for the ShiftIQ.

Chart backgrounds and colors read from theme at render time so they
automatically match the active light/dark palette.
"""
import tkinter as tk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

import theme


def _embed(fig, parent):
    """Embed a matplotlib figure into a tkinter parent and close the figure."""
    frame = tk.Frame(parent, bg=theme.BG)
    frame.pack(anchor="w", pady=(4, 0))
    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack()
    plt.close(fig)


def render_projection_chart(parent, state) -> None:
    """52-week balance projection line chart embedded in parent."""
    weeks_range = list(range(0, 53))
    balances    = [state.project_balance(w) for w in weeks_range]
    zero_line   = [0] * len(weeks_range)

    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=90)
    fig.patch.set_facecolor(theme.BG)
    ax.set_facecolor(theme.BG)

    ax.plot(weeks_range, balances, color=theme.ACCENT, linewidth=2.5, label="Projected Balance")
    ax.plot(weeks_range, zero_line, color=theme.DANGER, linewidth=1,
            linestyle="--", alpha=0.6, label="Break-even")
    ax.fill_between(weeks_range, balances, 0,
                    where=[b >= 0 for b in balances], alpha=0.15, color=theme.ACCENT)
    ax.fill_between(weeks_range, balances, 0,
                    where=[b < 0  for b in balances], alpha=0.15, color=theme.DANGER)

    ax.set_xlabel("Week", fontsize=9, color=theme.MUTED)
    ax.set_ylabel("Balance ($)", fontsize=9, color=theme.MUTED)
    ax.set_title("52-Week Balance Projection", fontsize=11,
                 color=theme.TEXT, fontweight="bold")
    ax.tick_params(colors=theme.MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(theme.BORDER)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=8, facecolor=theme.SIDEBAR,
               edgecolor=theme.BORDER, labelcolor=theme.TEXT)
    plt.tight_layout()
    _embed(fig, parent)


def render_mc_histogram(parent, ending_balances: list, weeks: int) -> None:
    """Histogram of Monte Carlo ending balances."""
    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=90)
    fig.patch.set_facecolor(theme.BG)
    ax.set_facecolor(theme.BG)

    n, bins, patches = ax.hist(ending_balances, bins=30,
                                edgecolor="white", linewidth=0.5)
    for patch, left_edge in zip(patches, bins[:-1]):
        patch.set_facecolor(theme.ACCENT if left_edge >= 0 else theme.DANGER)

    ax.axvline(x=0, color=theme.DANGER, linestyle="--",
               linewidth=1.2, alpha=0.7, label="$0")
    avg = sum(ending_balances) / len(ending_balances)
    ax.axvline(x=avg, color=theme.ACCENT, linestyle="-",
               linewidth=1.5, alpha=0.8, label=f"Avg ${avg:,.0f}")

    ax.set_xlabel("Ending Balance ($)", fontsize=9, color=theme.MUTED)
    ax.set_ylabel("Number of Futures", fontsize=9, color=theme.MUTED)
    ax.set_title(f"Distribution of {len(ending_balances)} Outcomes over {weeks} Weeks",
                 fontsize=11, color=theme.TEXT, fontweight="bold")
    ax.tick_params(colors=theme.MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(theme.BORDER)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=8, facecolor=theme.SIDEBAR,
               edgecolor=theme.BORDER, labelcolor=theme.TEXT)
    plt.tight_layout()
    _embed(fig, parent)


def render_trends_chart(parent, history: list) -> None:
    """Two-panel balance + income-vs-expenses trend chart."""
    dates    = [h["date"]     for h in history]
    balances = [h["balance"]  for h in history]
    incomes  = [h["income"]   for h in history]
    expenses = [h["expenses"] for h in history]
    x        = list(range(len(dates)))

    fig, axes = plt.subplots(2, 1, figsize=(7, 5), dpi=90, sharex=True)
    fig.patch.set_facecolor(theme.BG)

    ax1 = axes[0]
    ax1.set_facecolor(theme.BG)
    ax1.plot(x, balances, color=theme.ACCENT, linewidth=2,
             marker="o", markersize=4)
    ax1.axhline(y=0, color=theme.DANGER, linestyle="--",
                linewidth=0.8, alpha=0.5)
    ax1.set_ylabel("Balance ($)", fontsize=9, color=theme.MUTED)
    ax1.set_title("Balance Over Time", fontsize=10, color=theme.TEXT)
    ax1.tick_params(colors=theme.MUTED, labelsize=7)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    ax2 = axes[1]
    ax2.set_facecolor(theme.BG)
    ax2.plot(x, incomes,  color=theme.ACCENT, linewidth=1.8, label="Income/wk")
    ax2.plot(x, expenses, color=theme.DANGER,  linewidth=1.8,
             linestyle="--", label="Expenses/wk")
    ax2.set_ylabel("Weekly ($)", fontsize=9, color=theme.MUTED)
    ax2.set_title("Income vs Expenses", fontsize=10, color=theme.TEXT)
    ax2.legend(fontsize=8, facecolor=theme.SIDEBAR,
               edgecolor=theme.BORDER, labelcolor=theme.TEXT)
    ax2.tick_params(colors=theme.MUTED, labelsize=7)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    step = max(1, len(dates) // 5)
    tick_pos = list(range(0, len(dates), step))
    ax2.set_xticks(tick_pos)
    ax2.set_xticklabels([dates[i] for i in tick_pos],
                        rotation=30, ha="right", fontsize=7, color=theme.MUTED)
    plt.tight_layout()
    _embed(fig, parent)


def render_category_pie(parent, breakdown: dict) -> None:
    """Expense pie chart."""
    colors = ["#1B6B3A", "#2D9A5C", "#3DCC7A", "#74C69D",
              "#95D5B2", "#B7E4C7", "#52B788", "#40916C"]

    fig, ax = plt.subplots(figsize=(5.5, 4), dpi=90)
    fig.patch.set_facecolor(theme.BG)
    ax.set_facecolor(theme.BG)

    labels = list(breakdown.keys())
    sizes  = [breakdown[l] for l in labels]
    wedge_colors = [colors[i % len(colors)] for i in range(len(labels))]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=wedge_colors,
        autopct="%1.0f%%", startangle=140, pctdistance=0.75,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    for t in texts:
        t.set_fontsize(9)
        t.set_color(theme.TEXT)
    for at in autotexts:
        at.set_fontsize(8)
        at.set_color("white")
        at.set_fontweight("bold")

    ax.set_title("Expenses by Category", fontsize=11, color=theme.TEXT, pad=10)
    plt.tight_layout()
    _embed(fig, parent)
