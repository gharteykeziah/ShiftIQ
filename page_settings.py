"""page_settings.py — Settings page (simulation, projection, about)."""
import logging
import tkinter as tk

import theme
import database as db
import config
from theme import F_BODY, F_SMALL, F_H2
from widgets import ScrollFrame, page_title, card, kv_row, action_btn

logger = logging.getLogger(__name__)


class SettingsPage(tk.Frame):
    """Persistent app settings saved to SQLite."""

    _DEFAULTS = {
        "monte_carlo_runs": 500,
        "projection_weeks": 52,
    }

    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self._app = app

        sf    = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=28)

        page_title(inner, "Settings", "Customize how the app behaves.")

        # ── Simulation ────────────────────────────────────────────────────
        tk.Label(inner, text="Simulation", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))

        c1     = card(inner, pady=10)
        mc_runs = int(db.load_setting("monte_carlo_runs", self._DEFAULTS["monte_carlo_runs"]))
        tk.Label(c1, text="Monte Carlo runs",
                 font=("Inter", 11, "bold"), fg=theme.TEXT, bg=theme.BG).pack(
            anchor="w", padx=16, pady=(6, 2))
        tk.Label(c1,
                 text="How many futures to simulate when you click 'Run 500 Futures'. "
                      "Higher = more accurate, slower. Recommended: 500.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                 wraplength=620, justify="left").pack(anchor="w", padx=16, pady=(0, 6))
        mc_var   = tk.StringVar(value=str(mc_runs))
        mc_entry = tk.Entry(c1, textvariable=mc_var, font=F_BODY, width=10,
                            bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT,
                            highlightbackground=theme.BORDER, highlightthickness=1, relief="flat")
        mc_entry.pack(anchor="w", padx=16, pady=(0, 10))

        # ── Projection ────────────────────────────────────────────────────
        tk.Label(inner, text="Projection", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(16, 8))

        c2       = card(inner, pady=10)
        proj_wks = int(db.load_setting("projection_weeks", self._DEFAULTS["projection_weeks"]))
        tk.Label(c2, text="Default projection horizon (weeks)",
                 font=("Inter", 11, "bold"), fg=theme.TEXT, bg=theme.BG).pack(
            anchor="w", padx=16, pady=(6, 2))
        tk.Label(c2,
                 text="The number of weeks shown by default on the balance projection chart. "
                      "Recommended: 52 (one year).",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                 wraplength=620, justify="left").pack(anchor="w", padx=16, pady=(0, 6))
        proj_var   = tk.StringVar(value=str(proj_wks))
        proj_entry = tk.Entry(c2, textvariable=proj_var, font=F_BODY, width=10,
                              bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT,
                              highlightbackground=theme.BORDER, highlightthickness=1, relief="flat")
        proj_entry.pack(anchor="w", padx=16, pady=(0, 10))

        # ── Save ─────────────────────────────────────────────────────────
        result_lbl = tk.Label(inner, text="", font=F_SMALL, fg=theme.ACCENT, bg=theme.BG)
        result_lbl.pack(anchor="w", pady=(4, 0))

        def save_settings():
            errors = []
            try:
                runs = int(mc_var.get())
                if runs < 50 or runs > 10_000:
                    errors.append("Monte Carlo runs must be between 50 and 10,000.")
                else:
                    db.save_setting("monte_carlo_runs", runs)
            except ValueError:
                errors.append("Monte Carlo runs must be a whole number.")
            try:
                wks = int(proj_var.get())
                if wks < 1 or wks > 520:
                    errors.append("Projection weeks must be between 1 and 520.")
                else:
                    db.save_setting("projection_weeks", wks)
            except ValueError:
                errors.append("Projection weeks must be a whole number.")

            if errors:
                result_lbl.config(text="\n".join(errors), fg=theme.DANGER)
            else:
                result_lbl.config(text="Settings saved.", fg=theme.ACCENT)
                logger.info("Settings saved: mc_runs=%s  proj_weeks=%s",
                            mc_var.get(), proj_var.get())

        action_btn(inner, "Save Settings", save_settings)

        # Reset to defaults
        tk.Button(
            inner, text="Reset to defaults",
            font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
            activebackground=theme.BG, activeforeground=theme.TEXT,
            relief="flat", cursor="hand2",
            command=lambda: [
                mc_var.set(str(self._DEFAULTS["monte_carlo_runs"])),
                proj_var.set(str(self._DEFAULTS["projection_weeks"])),
                result_lbl.config(
                    text="Defaults restored — click Save to apply.", fg=theme.MUTED),
            ]
        ).pack(anchor="w", pady=(4, 0))

        # ── About ─────────────────────────────────────────────────────────
        tk.Label(inner, text="About", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(24, 8))
        about_c = card(inner, pady=10)
        kv_row(about_c, "App",        "ShiftIQ")
        kv_row(about_c, "Version",    config.APP_VERSION)
        kv_row(about_c, "Built with", "Python · tkinter · SQLite · matplotlib")
        kv_row(about_c, "License",    "MIT")
