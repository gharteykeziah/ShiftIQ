"""
shift_planner_ui.py — Standalone tkinter UI for the Shift Engine.

Run this file directly:
    python shift_planner_ui.py

Nothing in the existing ShiftIQ app is changed.
All data is read/written through shift_engine.py.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import shift_engine as se

# ── Colour palette (dark, matches ShiftIQ style) ──────────────────────────────────
BG        = "#0F1117"
SIDEBAR   = "#1A1D27"
CARD      = "#1E2130"
BORDER    = "#2A2D3E"
ACCENT    = "#1B6B3A"
ACCENT2   = "#22C55E"
TEXT      = "#E2E8F0"
MUTED     = "#64748B"
RED       = "#EF4444"
YELLOW    = "#F59E0B"
BLUE      = "#3B82F6"
WHITE     = "#FFFFFF"

F_TITLE   = ("Inter", 18, "bold")
F_HEAD    = ("Inter", 13, "bold")
F_BODY    = ("Inter", 11)
F_SMALL   = ("Inter", 10)
F_MONO    = ("Courier", 10)

DAY_OPTIONS = ["Monday", "Tuesday", "Wednesday", "Thursday",
               "Friday", "Saturday", "Sunday"]
HOUR_OPTIONS = [f"{h:02d}" for h in range(0, 24)]
MIN_OPTIONS  = ["00", "15", "30", "45"]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _card(parent, **kwargs) -> tk.Frame:
    """A styled card frame."""
    kw = dict(bg=CARD, bd=0, highlightbackground=BORDER,
              highlightthickness=1, relief="flat")
    kw.update(kwargs)
    return tk.Frame(parent, **kw)


def _label(parent, text, font=F_BODY, fg=TEXT, bg=None, **kwargs) -> tk.Label:
    return tk.Label(parent, text=text, font=font,
                    fg=fg, bg=bg or parent["bg"], **kwargs)


def _btn(parent, text, command, bg=ACCENT, fg=WHITE,
         font=F_BODY, pad=8) -> tk.Button:
    b = tk.Button(parent, text=text, command=command,
                  bg=bg, fg=fg, font=font,
                  activebackground=ACCENT2, activeforeground=WHITE,
                  relief="flat", bd=0, padx=14, pady=pad, cursor="hand2")
    b.bind("<Enter>", lambda e: b.config(bg=ACCENT2))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


def _entry(parent, width=22, textvariable=None) -> tk.Entry:
    return tk.Entry(parent, font=F_BODY, bg=SIDEBAR,
                    fg=TEXT, insertbackground=TEXT,
                    relief="flat", bd=0, highlightbackground=BORDER,
                    highlightthickness=1, width=width,
                    textvariable=textvariable)


def _dropdown(parent, variable, options, width=12) -> ttk.Combobox:
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Dark.TCombobox",
                    fieldbackground=SIDEBAR, background=SIDEBAR,
                    foreground=TEXT, selectbackground=ACCENT,
                    selectforeground=WHITE, arrowcolor=TEXT,
                    bordercolor=BORDER, relief="flat")
    cb = ttk.Combobox(parent, textvariable=variable, values=options,
                      state="readonly", width=width, style="Dark.TCombobox",
                      font=F_BODY)
    return cb


def _scrollable(parent) -> tuple[tk.Canvas, tk.Frame]:
    """Return (canvas, inner_frame) — pack canvas into parent."""
    canvas = tk.Canvas(parent, bg=parent["bg"], bd=0,
                       highlightthickness=0)
    sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                      bg=SIDEBAR, troughcolor=BG)
    inner = tk.Frame(canvas, bg=parent["bg"])
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)

    def _resize(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(inner_id, width=canvas.winfo_width())
    inner.bind("<Configure>", _resize)
    canvas.bind("<MouseWheel>",
                lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    return canvas, inner


def _divider(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=4)


# ─────────────────────────────────────────────────────────────────────────────
# Tab — Jobs
# ─────────────────────────────────────────────────────────────────────────────

class JobsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build()

    def _build(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(20, 6))
        _label(hdr, "Job Profiles", font=F_TITLE, bg=BG).pack(side="left")
        _btn(hdr, "+ Add Job", self._show_form).pack(side="right")

        _label(self,
               "Create one profile per job. Each profile stores the job name and hourly rate.",
               font=F_SMALL, fg=MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        # ── Add form (hidden by default) ──
        self._form_frame = tk.Frame(self, bg=CARD,
                                    highlightbackground=BORDER,
                                    highlightthickness=1)

        self._name_var = tk.StringVar()
        self._rate_var = tk.StringVar()

        form_inner = tk.Frame(self._form_frame, bg=CARD)
        form_inner.pack(padx=16, pady=14, fill="x")

        _label(form_inner, "Job Name", bg=CARD, fg=MUTED).grid(
            row=0, column=0, sticky="w", padx=(0, 10))
        _entry(form_inner, width=22, textvariable=self._name_var).grid(
            row=0, column=1, padx=(0, 16))

        _label(form_inner, "Hourly Rate ($)", bg=CARD, fg=MUTED).grid(
            row=0, column=2, sticky="w", padx=(0, 10))
        _entry(form_inner, width=10, textvariable=self._rate_var).grid(
            row=0, column=3, padx=(0, 16))

        _btn(form_inner, "Save Job", self._save_job).grid(
            row=0, column=4, padx=(0, 8))
        _btn(form_inner, "Cancel", self._hide_form,
             bg=SIDEBAR, fg=MUTED).grid(row=0, column=5)

        # ── List area ──
        _, self._list_inner = _scrollable(self)
        self._refresh_list()

    def _show_form(self):
        self._name_var.set("")
        self._rate_var.set("")
        self._form_frame.pack(fill="x", padx=24, pady=(0, 12))

    def _hide_form(self):
        self._form_frame.pack_forget()

    def _save_job(self):
        name = self._name_var.get().strip()
        rate_str = self._rate_var.get().strip()
        if not name:
            messagebox.showerror("Missing Info", "Please enter a job name.")
            return
        try:
            rate = float(rate_str)
        except ValueError:
            messagebox.showerror("Invalid Rate",
                                 "Hourly rate must be a number (e.g. 12.50).")
            return
        se.add_job(name, rate)
        self._hide_form()
        self._refresh_list()

    def _delete_job(self, name):
        if messagebox.askyesno("Delete Job",
                               f"Delete '{name}' and all its shifts?"):
            se.delete_job(name)
            self._refresh_list()

    def _refresh_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()

        jobs = se.get_jobs()
        if not jobs:
            _label(self._list_inner,
                   "No jobs yet. Click '+ Add Job' to create one.",
                   fg=MUTED, bg=BG).pack(pady=40)
            return

        for job in jobs:
            row = _card(self._list_inner)
            row.pack(fill="x", padx=24, pady=4)

            inner = tk.Frame(row, bg=CARD)
            inner.pack(fill="x", padx=14, pady=10)

            _label(inner, job["job_name"], font=F_HEAD, bg=CARD).pack(side="left")
            _label(inner, f"${job['hourly_rate']:.2f}/hr",
                   fg=ACCENT2, bg=CARD, font=F_BODY).pack(side="left", padx=16)
            _btn(inner, "Delete",
                 lambda n=job["job_name"]: self._delete_job(n),
                 bg=RED, pad=5).pack(side="right")


# ─────────────────────────────────────────────────────────────────────────────
# Tab — Shifts
# ─────────────────────────────────────────────────────────────────────────────

class ShiftsTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(20, 6))
        _label(hdr, "Weekly Shifts", font=F_TITLE, bg=BG).pack(side="left")

        btn_row = tk.Frame(hdr, bg=BG)
        btn_row.pack(side="right")
        _btn(btn_row, "+ Add Shift", self._show_form).pack(side="left", padx=(0, 8))
        _btn(btn_row, "Clear Week", self._clear_week,
             bg=RED, fg=WHITE).pack(side="left")

        _label(self,
               "Enter each shift for this week. Shifts are linked to a job profile.",
               font=F_SMALL, fg=MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        # ── Add shift form ──
        self._form_frame = tk.Frame(self, bg=CARD,
                                    highlightbackground=BORDER,
                                    highlightthickness=1)
        form_inner = tk.Frame(self._form_frame, bg=CARD)
        form_inner.pack(padx=16, pady=14, fill="x")

        self._job_var   = tk.StringVar()
        self._day_var   = tk.StringVar(value="Monday")
        self._sh_var    = tk.StringVar(value="09")
        self._sm_var    = tk.StringVar(value="00")
        self._eh_var    = tk.StringVar(value="12")
        self._em_var    = tk.StringVar(value="00")

        # Row 0 — job + day
        _label(form_inner, "Job", bg=CARD, fg=MUTED).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        self._job_cb = _dropdown(form_inner, self._job_var, [], width=18)
        self._job_cb.grid(row=0, column=1, padx=(0, 20), pady=(0, 8))

        _label(form_inner, "Day", bg=CARD, fg=MUTED).grid(
            row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 8))
        _dropdown(form_inner, self._day_var, DAY_OPTIONS, width=12).grid(
            row=0, column=3, padx=(0, 20), pady=(0, 8))

        # Row 1 — start/end time
        _label(form_inner, "Start", bg=CARD, fg=MUTED).grid(
            row=1, column=0, sticky="w", padx=(0, 8))
        st = tk.Frame(form_inner, bg=CARD)
        st.grid(row=1, column=1, sticky="w", padx=(0, 20))
        _dropdown(st, self._sh_var, HOUR_OPTIONS, width=4).pack(side="left")
        _label(st, ":", bg=CARD, fg=TEXT).pack(side="left", padx=2)
        _dropdown(st, self._sm_var, MIN_OPTIONS, width=4).pack(side="left")

        _label(form_inner, "End", bg=CARD, fg=MUTED).grid(
            row=1, column=2, sticky="w", padx=(0, 8))
        et = tk.Frame(form_inner, bg=CARD)
        et.grid(row=1, column=3, sticky="w", padx=(0, 20))
        _dropdown(et, self._eh_var, HOUR_OPTIONS, width=4).pack(side="left")
        _label(et, ":", bg=CARD, fg=TEXT).pack(side="left", padx=2)
        _dropdown(et, self._em_var, MIN_OPTIONS, width=4).pack(side="left")

        # Row 2 — buttons
        btn_f = tk.Frame(form_inner, bg=CARD)
        btn_f.grid(row=2, column=0, columnspan=6, sticky="w", pady=(10, 0))
        _btn(btn_f, "Save Shift", self._save_shift).pack(side="left", padx=(0, 8))
        _btn(btn_f, "Cancel", self._hide_form,
             bg=SIDEBAR, fg=MUTED).pack(side="left")

        # ── Shift list ──
        _, self._list_inner = _scrollable(self)
        self._refresh_list()

    def _show_form(self):
        # Refresh job list in dropdown
        jobs = se.get_jobs()
        names = [j["job_name"] for j in jobs]
        self._job_cb["values"] = names
        if names:
            self._job_var.set(names[0])
        self._form_frame.pack(fill="x", padx=24, pady=(0, 12))

    def _hide_form(self):
        self._form_frame.pack_forget()

    def _save_shift(self):
        job_name = self._job_var.get()
        day      = self._day_var.get()
        start    = f"{self._sh_var.get()}:{self._sm_var.get()}"
        end      = f"{self._eh_var.get()}:{self._em_var.get()}"

        if not job_name:
            messagebox.showerror("Missing Info",
                                 "No job selected. Add a job profile first.")
            return
        try:
            se.add_shift(job_name, day, start, end)
        except ValueError as e:
            messagebox.showerror("Invalid Shift", str(e))
            return

        self._hide_form()
        self._refresh_list()

    def _clear_week(self):
        if messagebox.askyesno("Clear Week",
                               "Delete ALL shifts this week?\n"
                               "Job profiles will NOT be deleted."):
            se.clear_week()
            self._refresh_list()

    def _delete_shift(self, shift_id):
        se.delete_shift(shift_id)
        self._refresh_list()

    def _refresh_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()

        schedule = se.get_weekly_schedule()
        has_any  = any(schedule[d] for d in se.DAY_ORDER)

        if not has_any:
            _label(self._list_inner,
                   "No shifts this week. Click '+ Add Shift' to get started.",
                   fg=MUTED, bg=BG).pack(pady=40)
            return

        for day in se.DAY_ORDER:
            shifts = schedule[day]
            if not shifts:
                continue

            # Day header
            day_hdr = tk.Frame(self._list_inner, bg=BG)
            day_hdr.pack(fill="x", padx=24, pady=(10, 4))
            _label(day_hdr, day, font=F_HEAD, bg=BG).pack(side="left")
            _divider(self._list_inner)

            for s in shifts:
                row = _card(self._list_inner)
                row.pack(fill="x", padx=24, pady=3)

                # Left colour bar
                tk.Frame(row, bg=ACCENT, width=4).pack(side="left", fill="y")

                inner = tk.Frame(row, bg=CARD)
                inner.pack(fill="x", padx=12, pady=8, side="left", expand=True)

                _label(inner, s["job_name"], font=("Inter", 11, "bold"),
                       bg=CARD).pack(side="left")
                start12 = se._format_time_12h(s["start_time"])
                end12   = se._format_time_12h(s["end_time"])
                _label(inner, f"{start12} – {end12}",
                       fg=MUTED, bg=CARD, font=F_SMALL).pack(side="left", padx=14)
                _label(inner, se._format_hours(s["hours"]),
                       fg=ACCENT2, bg=CARD, font=F_SMALL).pack(side="left")

                _btn(inner, "✕", lambda sid=s["id"]: self._delete_shift(sid),
                     bg=RED, fg=WHITE, pad=4).pack(side="right")


# ─────────────────────────────────────────────────────────────────────────────
# Tab — Free Time Mode
# ─────────────────────────────────────────────────────────────────────────────

class FreeTimeTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(20, 4))
        _label(hdr, "Free Time Mode", font=F_TITLE, bg=BG).pack(side="left")
        _btn(hdr, "⟳  Refresh", self._run).pack(side="right")

        _label(self,
               "Shows when you are BUSY and when you are FREE. No financial data.",
               font=F_SMALL, fg=MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        _, self._inner = _scrollable(self)
        self._run()

    def _run(self):
        for w in self._inner.winfo_children():
            w.destroy()

        data = se.FreeTimeMode().run()

        total_busy = 0.0
        total_free = 0.0

        for day in se.DAY_ORDER:
            day_data = data[day]
            busy_h   = day_data["total_busy_hours"]
            free_h   = day_data["total_free_hours"]
            total_busy += busy_h
            total_free += free_h

            if not day_data["shifts"] and not day_data["free_blocks"]:
                continue

            # Day header
            day_row = tk.Frame(self._inner, bg=BG)
            day_row.pack(fill="x", padx=24, pady=(12, 4))
            _label(day_row, day, font=F_HEAD, bg=BG).pack(side="left")
            _label(day_row,
                   f"  {se._format_hours(busy_h)} busy  ·  {se._format_hours(free_h)} free",
                   fg=MUTED, bg=BG, font=F_SMALL).pack(side="left", padx=8)

            card = _card(self._inner)
            card.pack(fill="x", padx=24, pady=(0, 6))

            for s in day_data["shifts"]:
                row = tk.Frame(card, bg=CARD)
                row.pack(fill="x", padx=14, pady=4)
                tk.Frame(row, bg=RED, width=6, height=20).pack(
                    side="left", padx=(0, 10))
                _label(row, "BUSY", fg=RED, bg=CARD,
                       font=("Inter", 9, "bold")).pack(side="left", padx=(0, 8))
                start12 = se._format_time_12h(s["start_time"])
                end12   = se._format_time_12h(s["end_time"])
                _label(row, f"{start12} – {end12}",
                       fg=TEXT, bg=CARD, font=F_SMALL).pack(side="left", padx=(0, 8))
                _label(row, f"({se._format_hours(s['hours'])})",
                       fg=MUTED, bg=CARD, font=F_SMALL).pack(side="left", padx=(0, 8))
                _label(row, s["job_name"], fg=MUTED, bg=CARD,
                       font=F_SMALL).pack(side="left")

            for b in day_data["free_blocks"]:
                row = tk.Frame(card, bg=CARD)
                row.pack(fill="x", padx=14, pady=4)
                tk.Frame(row, bg=ACCENT2, width=6, height=20).pack(
                    side="left", padx=(0, 10))
                _label(row, "FREE", fg=ACCENT2, bg=CARD,
                       font=("Inter", 9, "bold")).pack(side="left", padx=(0, 8))
                start12 = se._format_time_12h(b["start"])
                end12   = se._format_time_12h(b["end"])
                _label(row, f"{start12} – {end12}",
                       fg=TEXT, bg=CARD, font=F_SMALL).pack(side="left", padx=(0, 8))
                _label(row, f"({se._format_hours(b['hours'])})",
                       fg=ACCENT2, bg=CARD, font=F_SMALL).pack(side="left")

        # ── Weekly summary ──
        _divider(self._inner)
        summary = _card(self._inner)
        summary.pack(fill="x", padx=24, pady=8)
        s_inner = tk.Frame(summary, bg=CARD)
        s_inner.pack(fill="x", padx=20, pady=14)

        window_h = (se._time_to_minutes(se.DAY_END) -
                    se._time_to_minutes(se.DAY_START)) * 7 / 60
        avail = round(total_free / window_h * 100) if window_h else 0

        _label(s_inner, "Week Total", font=F_HEAD, bg=CARD).pack(anchor="w")
        stat_row = tk.Frame(s_inner, bg=CARD)
        stat_row.pack(anchor="w", pady=4)

        for val, label, col in [
            (se._format_hours(total_busy), "busy",  RED),
            (se._format_hours(total_free), "free",  ACCENT2),
            (f"{avail}%",                  "available", BLUE),
        ]:
            box = tk.Frame(stat_row, bg=BORDER, padx=12, pady=8)
            box.pack(side="left", padx=(0, 10))
            _label(box, val, font=("Inter", 14, "bold"),
                   fg=col, bg=BORDER).pack()
            _label(box, label, fg=MUTED, bg=BORDER,
                   font=F_SMALL).pack()


# ─────────────────────────────────────────────────────────────────────────────
# Tab — Income Mode
# ─────────────────────────────────────────────────────────────────────────────

class IncomeTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(20, 4))
        _label(hdr, "Income Mode", font=F_TITLE, bg=BG).pack(side="left")
        _btn(hdr, "⟳  Refresh", self._run).pack(side="right")

        _label(self,
               "Calculates your total earnings this week from scheduled shifts.",
               font=F_SMALL, fg=MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        _, self._inner = _scrollable(self)
        self._run()

    def _run(self):
        for w in self._inner.winfo_children():
            w.destroy()

        data = se.IncomeMode().run()

        if not data["by_job"]:
            _label(self._inner,
                   "No shifts scheduled. Add shifts to see income.",
                   fg=MUTED, bg=BG).pack(pady=40)
            return

        for job_name, info in sorted(data["by_job"].items()):
            # Job card
            jcard = _card(self._inner)
            jcard.pack(fill="x", padx=24, pady=6)

            # Colour bar
            tk.Frame(jcard, bg=ACCENT, width=4).pack(side="left", fill="y")

            inner = tk.Frame(jcard, bg=CARD)
            inner.pack(fill="both", expand=True, padx=14, pady=12)

            # Header row
            h_row = tk.Frame(inner, bg=CARD)
            h_row.pack(fill="x")
            _label(h_row, job_name, font=F_HEAD, bg=CARD).pack(side="left")
            _label(h_row, f"${info['hourly_rate']:.2f}/hr",
                   fg=MUTED, bg=CARD, font=F_SMALL).pack(side="left", padx=10)
            _label(h_row, f"${info['income']:.2f}",
                   fg=ACCENT2, font=("Inter", 13, "bold"),
                   bg=CARD).pack(side="right")

            _divider(inner)

            # Individual shifts
            for s in info["shifts"]:
                s_row = tk.Frame(inner, bg=CARD)
                s_row.pack(fill="x", pady=2)
                _label(s_row, f"{s['day']:12s}", fg=MUTED,
                       bg=CARD, font=F_SMALL).pack(side="left")
                start12 = se._format_time_12h(s["start_time"])
                end12   = se._format_time_12h(s["end_time"])
                _label(s_row, f"{start12} – {end12}",
                       fg=TEXT, bg=CARD, font=F_SMALL).pack(side="left", padx=10)
                _label(s_row, se._format_hours(s["hours"]),
                       fg=MUTED, bg=CARD, font=F_SMALL).pack(side="left", padx=10)
                earn = round(s["hours"] * info["hourly_rate"], 2)
                _label(s_row, f"${earn:.2f}",
                       fg=ACCENT2, bg=CARD, font=F_SMALL).pack(side="right")

            # Subtotal
            sub_row = tk.Frame(inner, bg=CARD)
            sub_row.pack(fill="x", pady=(6, 0))
            _label(sub_row, f"Subtotal:  {se._format_hours(info['total_hours'])}",
                   fg=MUTED, bg=CARD, font=F_SMALL).pack(side="left")
            _label(sub_row, f"${info['income']:.2f}",
                   fg=ACCENT2, bg=CARD, font=("Inter", 11, "bold")).pack(side="right")

        # ── Grand total ──
        _divider(self._inner)
        total_card = _card(self._inner)
        total_card.pack(fill="x", padx=24, pady=8)
        t_inner = tk.Frame(total_card, bg=CARD)
        t_inner.pack(fill="x", padx=20, pady=14)

        _label(t_inner, "This Week's Total", font=F_HEAD, bg=CARD).pack(anchor="w")
        stat_row = tk.Frame(t_inner, bg=CARD)
        stat_row.pack(anchor="w", pady=6)

        for val, label, col in [
            (se._format_hours(data["total_hours"]),  "total hours",   BLUE),
            (f"${data['total_income']:.2f}",          "total income",  ACCENT2),
            (f"${data['average_hourly']:.2f}/hr",     "avg rate",      YELLOW),
        ]:
            box = tk.Frame(stat_row, bg=BORDER, padx=14, pady=10)
            box.pack(side="left", padx=(0, 12))
            _label(box, val, font=("Inter", 15, "bold"),
                   fg=col, bg=BORDER).pack()
            _label(box, label, fg=MUTED, bg=BORDER,
                   font=F_SMALL).pack()


# ─────────────────────────────────────────────────────────────────────────────
# Tab — Opportunity Mode
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(20, 4))
        _label(hdr, "Opportunity Mode", font=F_TITLE, bg=BG).pack(side="left")
        _btn(hdr, "⟳  Refresh", self._run).pack(side="right")

        _label(self,
               "For each free block: what's the maximum you COULD earn if you picked up extra hours?",
               font=F_SMALL, fg=MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        _, self._inner = _scrollable(self)
        self._run()

    def _run(self):
        for w in self._inner.winfo_children():
            w.destroy()

        jobs = se.get_jobs()
        if not jobs:
            _label(self._inner,
                   "No job profiles found. Add jobs first.",
                   fg=MUTED, bg=BG).pack(pady=40)
            return

        data = se.OpportunityMode().run()
        has_blocks = any(data[d] for d in se.DAY_ORDER)

        if not has_blocks:
            _label(self._inner,
                   "No free blocks this week — your schedule is fully booked!",
                   fg=MUTED, bg=BG).pack(pady=40)
            return

        total_max = 0.0

        for day in se.DAY_ORDER:
            blocks = data[day]
            if not blocks:
                continue

            day_row = tk.Frame(self._inner, bg=BG)
            day_row.pack(fill="x", padx=24, pady=(12, 4))
            _label(day_row, day, font=F_HEAD, bg=BG).pack(side="left")

            for block in blocks:
                total_max += block["best_income"]

                bcard = _card(self._inner)
                bcard.pack(fill="x", padx=24, pady=3)

                # Left bar — colour by opportunity
                bar_col = ACCENT2 if block["best_income"] > 0 else MUTED
                tk.Frame(bcard, bg=bar_col, width=4).pack(side="left", fill="y")

                b_inner = tk.Frame(bcard, bg=CARD)
                b_inner.pack(fill="both", expand=True, padx=12, pady=10)

                # Time header
                t_row = tk.Frame(b_inner, bg=CARD)
                t_row.pack(fill="x")
                start12 = se._format_time_12h(block["start"])
                end12   = se._format_time_12h(block["end"])
                _label(t_row,
                       f"FREE:  {start12} – {end12}  ({se._format_hours(block['hours'])})",
                       font=("Inter", 11, "bold"), fg=TEXT, bg=CARD).pack(side="left")
                if block["best_income"] > 0:
                    _label(t_row, f"Best: ${block['best_income']:.2f}",
                           fg=ACCENT2, bg=CARD,
                           font=("Inter", 11, "bold")).pack(side="right")

                if not block["potential"]:
                    _label(b_inner, "No job rates to calculate potential.",
                           fg=MUTED, bg=CARD, font=F_SMALL).pack(anchor="w", pady=4)
                    continue

                # Per-job potential
                for i, opt in enumerate(block["potential"]):
                    is_best = i == 0
                    opt_row = tk.Frame(b_inner, bg=CARD)
                    opt_row.pack(fill="x", pady=2)

                    if is_best:
                        _label(opt_row, "★", fg=YELLOW, bg=CARD,
                               font=F_SMALL).pack(side="left", padx=(0, 4))
                    else:
                        tk.Frame(opt_row, bg=CARD, width=14).pack(side="left")

                    _label(opt_row, opt["job"],
                           fg=TEXT if is_best else MUTED,
                           bg=CARD, font=F_SMALL).pack(side="left", padx=(0, 10))
                    _label(opt_row, f"${opt['rate']:.2f}/hr",
                           fg=MUTED, bg=CARD, font=F_SMALL).pack(side="left", padx=(0, 14))
                    _label(opt_row, f"→  ${opt['potential_income']:.2f}",
                           fg=ACCENT2 if is_best else MUTED,
                           bg=CARD,
                           font=("Inter", 10, "bold") if is_best else F_SMALL,
                           ).pack(side="right")

        # ── Total ──
        _divider(self._inner)
        tot_card = _card(self._inner)
        tot_card.pack(fill="x", padx=24, pady=8)
        t_inner = tk.Frame(tot_card, bg=CARD)
        t_inner.pack(fill="x", padx=20, pady=14)

        _label(t_inner, "Maximum Possible Earnings from Free Time",
               font=F_HEAD, bg=CARD).pack(anchor="w")
        _label(t_inner,
               "(if every free block were filled at the highest available rate)",
               fg=MUTED, bg=CARD, font=F_SMALL).pack(anchor="w", pady=(2, 8))

        box = tk.Frame(t_inner, bg=ACCENT, padx=20, pady=12)
        box.pack(anchor="w")
        _label(box, f"${total_max:.2f}", font=("Inter", 22, "bold"),
               fg=WHITE, bg=ACCENT).pack()
        _label(box, "max opportunity", fg="#b2f0d0", bg=ACCENT,
               font=F_SMALL).pack()


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────

class ShiftPlannerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Shift Planner — ShiftIQ")
        self.geometry("920x660")
        self.configure(bg=BG)
        self.resizable(True, True)

        se.init_shift_tables()
        self._build()

    def _build(self):
        # ── Top bar ──
        top = tk.Frame(self, bg=ACCENT, pady=14)
        top.pack(fill="x")
        _label(top, "  Shift Planner", font=("Inter", 16, "bold"),
               fg=WHITE, bg=ACCENT).pack(side="left")
        _label(top, "ShiftIQ  ·  Schedule Module",
               fg="#b2f0d0", bg=ACCENT, font=F_SMALL).pack(side="left", padx=14)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Tab bar ──
        tab_bar = tk.Frame(self, bg=SIDEBAR, pady=0)
        tab_bar.pack(fill="x")

        self._tab_btns   = {}
        self._tab_frames = {}
        self._active_tab = tk.StringVar(value="jobs")

        tabs = [
            ("jobs",        "  Jobs  "),
            ("shifts",      "  Shifts  "),
            ("free_time",   "  Free Time  "),
            ("income",      "  Income  "),
            ("opportunity", "  Opportunity  "),
        ]

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True)

        for key, label in tabs:
            btn = tk.Button(
                tab_bar, text=label, font=F_BODY,
                fg=MUTED, bg=SIDEBAR, relief="flat", bd=0,
                padx=4, pady=12, cursor="hand2",
                command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(side="left")
            self._tab_btns[key] = btn

        tk.Frame(tab_bar, bg=BORDER, height=2).pack(fill="x", side="bottom")

        # Build tab frames (lazy — build when first visited)
        self._content = content
        self._built   = set()
        self._switch_tab("jobs")

    def _switch_tab(self, key):
        # Destroy old tab
        for f in self._tab_frames.values():
            f.pack_forget()

        # Highlight active tab button
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.config(fg=ACCENT2, bg=SIDEBAR,
                           font=("Inter", 11, "bold"))
            else:
                btn.config(fg=MUTED, bg=SIDEBAR, font=F_BODY)

        # Build or retrieve the frame
        if key not in self._tab_frames:
            frame_cls = {
                "jobs":        JobsTab,
                "shifts":      ShiftsTab,
                "free_time":   FreeTimeTab,
                "income":      IncomeTab,
                "opportunity": OpportunityTab,
            }[key]
            frame = frame_cls(self._content)
            self._tab_frames[key] = frame

        self._tab_frames[key].pack(fill="both", expand=True)
        self._active_tab.set(key)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = ShiftPlannerApp()
    app.mainloop()
