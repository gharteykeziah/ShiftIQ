"""
page_more.py — Single list page linking to every secondary feature.

Per FRE_MLP_Product_Strategy.md: the sidebar collapses from 7 nav items to
3 (Home, Schedule, More). Nothing is deleted — Dashboard, Analytics,
Forecasting, Goals, Data Management, and Settings all still exist and
still work exactly as before. They're just one tap away from here instead
of competing with Home and Schedule for space in the main nav.
"""
import tkinter as tk

import theme
from theme import F_BODY, F_SMALL
from widgets import ScrollFrame, page_title, card

_ITEMS = [
    ("dashboard",       "Dashboard",   "Balance, weekly totals, risk and health scores"),
    ("analytics",       "Analytics",   "Savings, health, income, expenses, and trends"),
    ("forecasting",     "Forecasting", "Projections, scenarios, and Monte Carlo simulation"),
    ("goals",           "Goals",       "Track progress toward a savings target"),
    ("data_management", "Data",        "Manage jobs and expenses directly"),
    ("settings",        "Settings",    "App preferences, backup, and export"),
]


class MorePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self._app = app

        sf = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=28)

        page_title(inner, "More", "Everything else ShiftIQ can do.")

        for key, title, desc in _ITEMS:
            self._row(inner, key, title, desc)

    def _row(self, parent: tk.Frame, key: str, title: str, desc: str) -> None:
        row = card(parent, pady=4)
        row.configure(cursor="hand2")

        box = tk.Frame(row, bg=theme.SIDEBAR, padx=16, pady=14, cursor="hand2")
        box.pack(fill="x")

        title_lbl = tk.Label(box, text=title, font=("Inter", 12, "bold"),
                              fg=theme.TEXT, bg=theme.SIDEBAR, cursor="hand2")
        title_lbl.pack(anchor="w")

        desc_lbl = tk.Label(box, text=desc, font=F_BODY, fg=theme.MUTED,
                             bg=theme.SIDEBAR, wraplength=660, justify="left",
                             cursor="hand2")
        desc_lbl.pack(anchor="w", pady=(2, 0))

        def go(_event=None, k=key) -> None:
            self._app.show_page(k)

        for widget in (row, box, title_lbl, desc_lbl):
            widget.bind("<Button-1>", go)
