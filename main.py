"""
main.py — Entry point for ShiftIQ.

Wires up logging, initialises the database, and launches the App window.
All application logic lives in:
    theme.py          — palettes, ThemeManager, apply_theme()
    widgets.py        — shared UI helpers (ScrollFrame, TabBar, card, …)
    charts.py         — matplotlib chart renderers
    app.py            — App (tk.Tk), sidebar, navigation, DI state/engines
    page_dashboard.py — Dashboard
    page_data.py      — Data Management
    page_analytics.py — Analytics
    page_forecast.py  — Forecasting
    page_goals.py     — Goals
    page_settings.py  — Settings
"""
import logging
import tkinter.messagebox   # ensure messagebox is importable before any page needs it

import database as db
from config import LOG_FILE
from app import App


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


if __name__ == "__main__":
    _setup_logging()
    db.init_db()
    db.init_events_table()
    db.dedup_jobs()      # fuzzy-merge duplicate job entries
    db.dedup_expenses()  # fuzzy-merge duplicate expense entries
    application = App()
    application.mainloop()
