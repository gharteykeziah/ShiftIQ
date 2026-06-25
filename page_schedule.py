"""
page_schedule.py — Time & Income Planner page.

Tabs:
    1. Week View    — all events laid out per day
    2. Add Event    — form with conflict detection
    3. My Events    — list / edit / delete
    4. Free Time    — free-block analysis + opportunity cost
    5. Income       — work hours & income summary
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import theme
import database as db
from theme import F_BODY, F_SMALL, F_H2
from utils import canon_name, normalize_job_name


def _canon(name: str) -> str:
    """Delegates to utils.canon_name() — single source of truth."""
    return canon_name(name)


def _normalize_job_name(raw: str, existing_names: list[str]) -> str:
    """Delegates to utils.normalize_job_name() — single source of truth."""
    return normalize_job_name(raw, existing_names)
from widgets import (ScrollFrame, TabBar, page_title, card,
                     kv_row, action_btn, status_lbl, section_divider)
from schedule_event import (ScheduleEvent, DAYS, CATEGORIES,
                             CATEGORY_COLORS, fmt_time, fmt_duration)
from time_engine import (get_free_blocks, largest_free_block,
                          weekly_availability, detect_conflicts,
                          weekly_income_summary, opportunity_cost)
import week_engine


# ── Color helpers ─────────────────────────────────────────────────────────────
def _cat_color(category: str) -> str:
    """Return the hex color for a category, adjusted for dark mode."""
    base = CATEGORY_COLORS.get(category, "#6B7280")
    if theme.is_dark():
        # Lighten slightly for dark backgrounds
        h = base.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r * 1.3))
        g = min(255, int(g * 1.3))
        b = min(255, int(b * 1.3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return base


# ── Time picker widget ────────────────────────────────────────────────────────
class _TimePicker(tk.Frame):
    """
    A compact time picker: [Hour ▾] : [Minute ▾] [AM/PM ▾]
    Returns time as "HH:MM" (24-hour) via get_value().
    """

    _HOURS   = [str(h) for h in range(1, 13)]
    _MINUTES = ["00", "15", "30", "45"]
    _AMPM    = ["AM", "PM"]

    def __init__(self, parent, initial_time: str = "09:00"):
        super().__init__(parent, bg=theme.BG)
        h24, m = map(int, initial_time.split(":"))
        ampm_val = "AM" if h24 < 12 else "PM"
        h12_val  = str(h24 % 12 or 12)
        # Snap minute to nearest quarter
        m_snap = str(min(self._MINUTES, key=lambda x: abs(int(x) - m)))

        self._hour = ttk.Combobox(self, values=self._HOURS, width=3, state="readonly")
        self._hour.set(h12_val)
        self._hour.pack(side="left")

        tk.Label(self, text=":", font=F_BODY, fg=theme.TEXT, bg=theme.BG).pack(side="left")

        self._min = ttk.Combobox(self, values=self._MINUTES, width=3, state="readonly")
        self._min.set(m_snap)
        self._min.pack(side="left")

        self._ampm = ttk.Combobox(self, values=self._AMPM, width=3, state="readonly")
        self._ampm.set(ampm_val)
        self._ampm.pack(side="left", padx=(4, 0))

    def get_value(self) -> str:
        """Return the selected time as "HH:MM" (24-hour)."""
        h  = int(self._hour.get())
        m  = int(self._min.get())
        ap = self._ampm.get()
        if ap == "PM" and h != 12:
            h += 12
        elif ap == "AM" and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"


# ── Main page ─────────────────────────────────────────────────────────────────
def _recategorize_existing_events() -> None:
    """
    One-time cleanup: fix events that were imported as 'Work' before the
    category-detection logic existed.  An event is reclassified away from Work
    only if it has no hourly rate AND its name matches a non-work keyword.
    Events with a rate are always left as Work.
    """
    def _infer(name: str, rate: float) -> str:
        if rate > 0:
            return "Work"
        t = name.lower()
        if any(w in t for w in ["class", "lecture", "lab", "seminar", "course"]):
            return "Class"
        if any(w in t for w in ["study", "homework", "hw", "review", "tutoring",
                                  "session", "calculus", "algebra", "biology",
                                  "chemistry", "physics", "english", "history", "writing"]):
            return "Study"
        if any(w in t for w in ["meeting", "club", "group", "committee", "board", "org"]):
            return "Meeting"
        if any(w in t for w in ["gym", "workout", "church", "appointment", "doctor",
                                  "dentist", "hair", "lunch", "dinner", "break", "personal"]):
            return "Personal"
        return "Work"   # unknown with no rate → keep as Work (user can edit)

    for ev in db.get_events():
        if ev.category == "Work":
            correct = _infer(ev.title, ev.hourly_rate or 0.0)
            if correct != "Work":
                db.update_event(ev.id, category=correct)


class SchedulePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=theme.BG)
        self._app = app
        _recategorize_existing_events()   # fix legacy mis-labeled events
        # Which week the Week View is currently showing (Monday date)
        self._view_week: "week_engine.datetime.date" = week_engine.get_week_start()

        header = tk.Frame(self, bg=theme.BG, padx=36, pady=16)
        header.pack(fill="x")
        page_title(header, "Schedule",
                   "Manage your time, find free blocks, and see your earning potential.")

        tb = TabBar(self, [
            ("week",     "Week View"),
            ("add",      "Add Event"),
            ("events",   "My Events"),
            ("freetime", "Free Time"),
            ("import",   "Import"),
        ])
        tb.pack(fill="x", padx=36)
        self._body = tk.Frame(self, bg=theme.BG)
        self._body.pack(fill="both", expand=True)
        tb.bind_select(self._render)
        tb.activate("week")

        # Sync all existing Work events to ShiftIQ Data on every page load
        self.after(100, self._sync_all_work_to_state)

    def _render(self, key):
        for w in self._body.winfo_children():
            w.destroy()
        {
            "week":     self._week_view,
            "add":      self._add_event,
            "events":   self._my_events,
            "freetime": self._free_time,
            "import":   self._import_schedule,
        }[key]()

    # ─────────────────────────────────────────────────────────────────────
    # TAB 1: Week View
    # ─────────────────────────────────────────────────────────────────────
    def _week_view(self):
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        # ── Week navigation bar ───────────────────────────────────────────
        week_start = self._view_week
        week_end   = week_start + __import__("datetime").timedelta(days=6)
        is_current = week_engine.is_current_week(week_start)

        nav = tk.Frame(inner, bg=theme.BG)
        nav.pack(fill="x", pady=(0, 12))

        tk.Button(nav, text="← Prev",
                  font=F_SMALL, fg=theme.ACCENT, bg=theme.BG,
                  relief="flat", cursor="hand2",
                  command=self._go_prev_week).pack(side="left")

        label_text = week_engine.week_label(week_start, week_end)
        if is_current:
            label_text += "  (This Week)"
        tk.Label(nav, text=label_text,
                 font=("Inter", 12, "bold"), fg=theme.TEXT,
                 bg=theme.BG).pack(side="left", padx=16)

        tk.Button(nav, text="Next →",
                  font=F_SMALL, fg=theme.ACCENT, bg=theme.BG,
                  relief="flat", cursor="hand2",
                  command=self._go_next_week).pack(side="left")

        if not is_current:
            tk.Button(nav, text="Today",
                      font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                      relief="flat", cursor="hand2",
                      command=self._go_current_week).pack(side="left", padx=(12, 0))

        # ── Fetch events for this week ────────────────────────────────────
        # Prefer date-stamped events; fall back to all events for current week
        dated_events = db.get_events_for_week(week_start)
        if dated_events:
            week_events = dated_events
        elif is_current:
            # Legacy events (no shift_date) — show all for current week
            week_events = db.get_events()
        else:
            week_events = []

        if not week_events:
            tk.Label(inner,
                     text="No events for this week.\nUse the Import tab to paste a schedule, "
                          "or Add Event to create one.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG,
                     justify="center").pack(anchor="w", pady=20)
            return

        # Quick summary row
        stats = weekly_availability(week_events)
        summary = card(inner, pady=4)
        summary_row = tk.Frame(summary, bg=theme.SIDEBAR)
        summary_row.pack(fill="x", padx=16, pady=10)
        for label, val in [
            ("Scheduled",    f"{stats['scheduled_hours']}h"),
            ("Free",         f"{stats['free_hours']}h"),
            ("Availability", f"{stats['availability_pct']}%"),
        ]:
            col = tk.Frame(summary_row, bg=theme.SIDEBAR, padx=18)
            col.pack(side="left")
            tk.Label(col, text=val, font=("Inter", 18, "bold"),
                     fg=theme.ACCENT, bg=theme.SIDEBAR).pack()
            tk.Label(col, text=label, font=F_SMALL,
                     fg=theme.MUTED, bg=theme.SIDEBAR).pack()

        section_divider(inner)

        # Group events by day name (derived from shift_date when available)
        by_day: dict[str, list[ScheduleEvent]] = {d: [] for d in DAYS}
        for ev in week_events:
            day_name = ev.day
            if ev.shift_date:
                d = week_engine.parse_iso(ev.shift_date)
                if d:
                    day_name = week_engine.date_to_day(d)
            if day_name in by_day:
                by_day[day_name].append(ev)

        for day in DAYS:
            evs = sorted(by_day[day], key=lambda e: e.start_time)

            # Day header — show actual date if available
            day_date = week_engine.day_to_date(day, week_start)
            date_suffix = f"  {day_date.strftime('%b %d')}" if day_date else ""
            day_hdr = tk.Frame(inner, bg=theme.BG)
            day_hdr.pack(fill="x", pady=(10, 2))
            tk.Label(day_hdr, text=f"{day}{date_suffix}",
                     font=("Inter", 13, "bold"),
                     fg=theme.TEXT, bg=theme.BG).pack(side="left")
            if evs:
                total_h = sum(self._shift_hours(e) for e in evs)
                tk.Label(day_hdr,
                         text=f"  {fmt_duration(total_h)} scheduled",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(side="left")

            if not evs:
                tk.Label(inner, text="    Free all day",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
                continue

            for ev in evs:
                color = _cat_color(ev.category)
                row = tk.Frame(inner, bg=theme.SIDEBAR,
                               highlightbackground=theme.BORDER, highlightthickness=1)
                row.pack(fill="x", pady=2)

                tk.Frame(row, bg=color, width=5).pack(side="left", fill="y")
                info = tk.Frame(row, bg=theme.SIDEBAR)
                info.pack(side="left", fill="x", padx=12, pady=8)

                top = tk.Frame(info, bg=theme.SIDEBAR)
                top.pack(fill="x")
                tk.Label(top, text=ev.title, font=("Inter", 11, "bold"),
                         fg=theme.TEXT, bg=theme.SIDEBAR).pack(side="left")
                tk.Label(top, text=f" {ev.category} ",
                         font=("Inter", 9, "bold"),
                         fg="white", bg=color, padx=4).pack(side="left", padx=(8, 0))

                hrs = self._shift_hours(ev)
                time_str = (f"{fmt_time(ev.start_time)} – {fmt_time(ev.end_time)}"
                            f"  ({fmt_duration(hrs)})"
                            + ("  +1 day" if ev.end_time < ev.start_time else ""))
                tk.Label(info, text=time_str,
                         font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR).pack(anchor="w")
                if ev.notes and ev.notes not in ("", "Imported"):
                    tk.Label(info, text=ev.notes,
                             font=("Inter", 9, "italic"), fg=theme.MUTED,
                             bg=theme.SIDEBAR, wraplength=560).pack(anchor="w")

    def _go_prev_week(self):
        self._view_week, _ = week_engine.get_previous_week(self._view_week)
        self._render("week")

    def _go_next_week(self):
        self._view_week, _ = week_engine.get_next_week(self._view_week)
        self._render("week")

    def _go_current_week(self):
        self._view_week = week_engine.get_week_start()
        self._render("week")

    # ─────────────────────────────────────────────────────────────────────
    # TAB 2: Add Event
    # ─────────────────────────────────────────────────────────────────────
    def _add_event(self, prefill: ScheduleEvent | None = None):
        """
        prefill: if given, populate the form for editing an existing event.
        """
        editing = prefill is not None
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        heading = "Edit Event" if editing else "Add a New Event"
        tk.Label(inner, text=heading, font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text="Enter a work shift, class, study block, or any personal commitment.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 14))

        # ── Title ────────────────────────────────────────────────────────
        tk.Label(inner, text="Event Title", font=("Inter", 10, "bold"),
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 3))
        title_e = tk.Entry(inner, font=F_BODY, width=36, relief="flat",
                           highlightbackground=theme.ACCENT, highlightthickness=1,
                           bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT)
        title_e.pack(anchor="w", ipady=7)
        if prefill:
            title_e.insert(0, prefill.title)

        # ── Category ─────────────────────────────────────────────────────
        tk.Label(inner, text="Category", font=("Inter", 10, "bold"),
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(12, 3))
        cat_var = tk.StringVar(value=prefill.category if prefill else "Work")
        cat_row = tk.Frame(inner, bg=theme.BG)
        cat_row.pack(anchor="w")
        for cat in CATEGORIES:
            color = _cat_color(cat)
            rb = tk.Radiobutton(
                cat_row, text=cat, variable=cat_var, value=cat,
                font=F_BODY, fg=color, bg=theme.BG,
                activebackground=theme.BG, selectcolor=theme.ACCENT_L,
            )
            rb.pack(side="left", padx=6)

        # ── Day ──────────────────────────────────────────────────────────
        tk.Label(inner, text="Day", font=("Inter", 10, "bold"),
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(12, 3))
        day_var = tk.StringVar(value=prefill.day if prefill else "Monday")
        day_cb  = ttk.Combobox(inner, textvariable=day_var,
                                values=DAYS, state="readonly", width=14,
                                font=F_BODY)
        day_cb.pack(anchor="w")

        # ── Times ────────────────────────────────────────────────────────
        times_row = tk.Frame(inner, bg=theme.BG)
        times_row.pack(anchor="w", pady=(12, 0))

        tk.Label(times_row, text="Start Time", font=("Inter", 10, "bold"),
                 fg=theme.TEXT, bg=theme.BG).grid(row=0, column=0, sticky="w", padx=(0, 30))
        tk.Label(times_row, text="End Time", font=("Inter", 10, "bold"),
                 fg=theme.TEXT, bg=theme.BG).grid(row=0, column=1, sticky="w")

        start_picker = _TimePicker(times_row,
                                    prefill.start_time if prefill else "09:00")
        start_picker.grid(row=1, column=0, sticky="w", padx=(0, 30))

        end_picker = _TimePicker(times_row,
                                  prefill.end_time if prefill else "10:00")
        end_picker.grid(row=1, column=1, sticky="w")

        # ── Hourly rate (Work only) ───────────────────────────────────────
        rate_frame = tk.Frame(inner, bg=theme.BG)
        rate_frame.pack(anchor="w", fill="x")

        rate_lbl = tk.Label(rate_frame, text="Hourly Rate ($)  (for Work events)",
                            font=("Inter", 10, "bold"), fg=theme.TEXT, bg=theme.BG)
        rate_e   = tk.Entry(rate_frame, font=F_BODY, width=10, relief="flat",
                             highlightbackground=theme.ACCENT, highlightthickness=1,
                             bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT)
        if prefill and prefill.hourly_rate > 0:
            rate_e.insert(0, str(prefill.hourly_rate))

        def _refresh_rate_vis(*_):
            if cat_var.get() == "Work":
                rate_lbl.pack(anchor="w", pady=(12, 3))
                rate_e.pack(anchor="w", ipady=7)
            else:
                rate_lbl.pack_forget()
                rate_e.pack_forget()

        cat_var.trace_add("write", _refresh_rate_vis)
        _refresh_rate_vis()

        # ── Notes ─────────────────────────────────────────────────────────
        tk.Label(inner, text="Notes  (optional)", font=("Inter", 10, "bold"),
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(12, 3))
        notes_e = tk.Entry(inner, font=F_BODY, width=46, relief="flat",
                            highlightbackground=theme.BORDER, highlightthickness=1,
                            bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT)
        notes_e.pack(anchor="w", ipady=6)
        if prefill and prefill.notes:
            notes_e.insert(0, prefill.notes)

        # ── Status area ───────────────────────────────────────────────────
        status = tk.Frame(inner, bg=theme.BG)
        status.pack(anchor="w", pady=(8, 0))

        # ── Submit ────────────────────────────────────────────────────────
        def submit():
            for w in status.winfo_children():
                w.destroy()
            try:
                rate_val = 0.0
                if cat_var.get() == "Work" and rate_e.get().strip():
                    rate_val = float(rate_e.get().strip())

                ev = ScheduleEvent(
                    title       = title_e.get().strip(),
                    category    = cat_var.get(),
                    day         = day_var.get(),
                    start_time  = start_picker.get_value(),
                    end_time    = end_picker.get_value(),
                    hourly_rate = rate_val,
                    notes       = notes_e.get().strip(),
                    id          = prefill.id if prefill else 0,
                )
                ok, msg = ev.validate()
                if not ok:
                    status_lbl(status, msg, False)
                    return

                # Conflict check
                existing_evs = db.get_events(ev.day)
                conflicts = detect_conflicts(ev, existing_evs)
                if conflicts:
                    names = ", ".join(c.title for c in conflicts)
                    status_lbl(status,
                               f"Conflict with: {names}  "
                               f"(overlapping time on {ev.day})", False)
                    def force_save():
                        _maybe_prompt_rate(ev)
                    tk.Button(status, text="Save anyway",
                              font=F_SMALL, fg=theme.DANGER, bg=theme.BG,
                              relief="flat", cursor="hand2",
                              command=force_save).pack(anchor="w", pady=(4, 0))
                    return

                _maybe_prompt_rate(ev)

            except ValueError:
                status_lbl(status, "Hourly rate must be a number (e.g. 12.50).", False)

        def _maybe_prompt_rate(ev: ScheduleEvent):
            """
            If this is a Work event with no rate and the job is brand new,
            ask for a rate before saving.  If 'No Rate' → save to Schedule
            only (not added to Data).  If rate given → save + add to Data.
            """
            if ev.category != "Work" or ev.hourly_rate > 0:
                _do_save(ev)
                return

            # Check if a rate is already known for this job
            known = self._get_known_rate(ev.title)
            if known:
                ev.hourly_rate = known
                _do_save(ev)
                return

            # Brand-new job with no rate — ask
            for w in status.winfo_children():
                w.destroy()

            tk.Label(status,
                     text=f"'{ev.title}' is a new job. What's the hourly rate?",
                     font=F_SMALL, fg=theme.TEXT, bg=theme.BG).pack(anchor="w")

            prompt_row = tk.Frame(status, bg=theme.BG)
            prompt_row.pack(anchor="w", pady=(4, 0))

            rate_prompt = tk.Entry(prompt_row, font=F_BODY, width=10,
                                   relief="flat",
                                   highlightbackground=theme.ACCENT,
                                   highlightthickness=1,
                                   bg=theme.SIDEBAR, fg=theme.TEXT,
                                   insertbackground=theme.TEXT)
            rate_prompt.pack(side="left", ipady=5, padx=(0, 6))
            rate_prompt.focus_set()

            def _confirm_rate():
                try:
                    r = float(rate_prompt.get().strip())
                    if r <= 0:
                        raise ValueError
                    ev.hourly_rate = r
                    _do_save(ev)
                except ValueError:
                    for w in prompt_row.winfo_children():
                        pass  # keep prompt visible, just flash entry
                    rate_prompt.config(highlightbackground=theme.DANGER)

            def _no_rate():
                # Save to Schedule only — no Data job created
                _do_save(ev)

            tk.Button(prompt_row, text="Set Rate",
                      font=F_SMALL, fg="white", bg=theme.ACCENT,
                      relief="flat", cursor="hand2",
                      command=_confirm_rate).pack(side="left", padx=(0, 4))
            tk.Button(prompt_row, text="No Rate",
                      font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                      relief="flat", cursor="hand2",
                      command=_no_rate).pack(side="left")

            rate_prompt.bind("<Return>", lambda _: _confirm_rate())

        def _do_save(ev: ScheduleEvent):
            for w in status.winfo_children():
                w.destroy()
            if editing and ev.id:
                db.update_event(ev.id,
                                title=ev.title, category=ev.category,
                                day=ev.day, start_time=ev.start_time,
                                end_time=ev.end_time, hourly_rate=ev.hourly_rate,
                                notes=ev.notes)
                status_lbl(status, f"'{ev.title}' updated.", True)
            else:
                db.add_event(ev)
                status_lbl(status, f"'{ev.title}' added to {ev.day}.", True)
                title_e.delete(0, "end")
                notes_e.delete(0, "end")
                rate_e.delete(0, "end")

            # ── Sync to Data only if a rate is known ──────────────────────
            if ev.category == "Work" and ev.hourly_rate > 0:
                db.update_events_rate(ev.title, ev.hourly_rate)
                self._sync_work_to_state(ev.title, ev.hourly_rate)

        lbl = "Save Changes" if editing else "Add to Schedule"
        action_btn(inner, lbl, submit)

    # ─────────────────────────────────────────────────────────────────────
    # TAB 3: My Events
    # ─────────────────────────────────────────────────────────────────────
    def _my_events(self):
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="All Scheduled Events", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))

        # Filters
        filter_row = tk.Frame(inner, bg=theme.BG)
        filter_row.pack(anchor="w", fill="x", pady=(0, 8))

        search_var = tk.StringVar()
        day_filter_var = tk.StringVar(value="All Days")
        cat_filter_var = tk.StringVar(value="All Categories")

        tk.Label(filter_row, text="Search:", font=F_SMALL,
                 fg=theme.MUTED, bg=theme.BG).pack(side="left")
        tk.Entry(filter_row, textvariable=search_var, font=F_BODY, width=20,
                 bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT,
                 highlightbackground=theme.BORDER, highlightthickness=1,
                 relief="flat").pack(side="left", padx=(4, 16))

        tk.Label(filter_row, text="Day:", font=F_SMALL,
                 fg=theme.MUTED, bg=theme.BG).pack(side="left")
        ttk.Combobox(filter_row, textvariable=day_filter_var,
                     values=["All Days"] + DAYS,
                     state="readonly", width=12,
                     font=F_SMALL).pack(side="left", padx=(4, 16))

        tk.Label(filter_row, text="Category:", font=F_SMALL,
                 fg=theme.MUTED, bg=theme.BG).pack(side="left")
        ttk.Combobox(filter_row, textvariable=cat_filter_var,
                     values=["All Categories"] + CATEGORIES,
                     state="readonly", width=14,
                     font=F_SMALL).pack(side="left", padx=4)

        list_frame = tk.Frame(inner, bg=theme.BG)
        list_frame.pack(fill="x")

        def refresh(*_):
            for w in list_frame.winfo_children():
                w.destroy()
            all_events = db.get_events()
            q   = search_var.get().strip().lower()
            df  = day_filter_var.get()
            cf  = cat_filter_var.get()
            matches = [
                e for e in all_events
                if (not q or q in e.title.lower() or q in e.notes.lower())
                and (df == "All Days" or e.day == df)
                and (cf == "All Categories" or e.category == cf)
            ]
            if not matches:
                tk.Label(list_frame, text="No events match your filters.",
                         font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
                return

            # Sort by day order then start time
            day_order = {d: i for i, d in enumerate(DAYS)}
            matches.sort(key=lambda e: (day_order.get(e.day, 99), e.start_time))

            for ev in matches:
                color = _cat_color(ev.category)
                row = tk.Frame(list_frame, bg=theme.SIDEBAR,
                               highlightbackground=theme.BORDER, highlightthickness=1)
                row.pack(fill="x", pady=2)
                tk.Frame(row, bg=color, width=5).pack(side="left", fill="y")

                info = tk.Frame(row, bg=theme.SIDEBAR)
                info.pack(side="left", fill="x", expand=True, padx=12, pady=8)

                top = tk.Frame(info, bg=theme.SIDEBAR)
                top.pack(fill="x")
                tk.Label(top, text=ev.title, font=("Inter", 11, "bold"),
                         fg=theme.TEXT, bg=theme.SIDEBAR).pack(side="left")
                tk.Label(top, text=f" {ev.category} ",
                         font=("Inter", 9, "bold"), fg="white", bg=color,
                         padx=3).pack(side="left", padx=(6, 0))
                tk.Label(top, text=f"  {ev.day}",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR).pack(side="left")

                # Time display — overnight-aware
                hrs = self._shift_hours(ev)
                from schedule_event import fmt_time, fmt_duration
                time_str = (f"{fmt_time(ev.start_time)} – {fmt_time(ev.end_time)}"
                            f"  ({fmt_duration(hrs)})"
                            + ("  +1 day" if ev.end_time < ev.start_time else ""))
                tk.Label(info, text=time_str,
                         font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR).pack(anchor="w")

                # Rate + shift earnings — shown for ALL Work events
                btns = tk.Frame(row, bg=theme.SIDEBAR)
                btns.pack(side="right", padx=8)

                def _edit(e=ev):
                    for w in self._body.winfo_children():
                        w.destroy()
                    self._add_event(prefill=e)

                def _delete(e=ev):
                    db.delete_event_by_id(e.id)
                    refresh()

                tk.Button(btns, text="Edit", font=F_SMALL,
                          fg=theme.BLUE, bg=theme.SIDEBAR,
                          relief="flat", cursor="hand2",
                          command=_edit).pack(pady=(0, 4))
                tk.Button(btns, text="Delete", font=F_SMALL,
                          fg=theme.DANGER, bg=theme.SIDEBAR,
                          relief="flat", cursor="hand2",
                          command=_delete).pack()

        search_var.trace_add("write", refresh)
        day_filter_var.trace_add("write", refresh)
        cat_filter_var.trace_add("write", refresh)
        refresh()

    # ─────────────────────────────────────────────────────────────────────
    # TAB 4: Free Time
    # ─────────────────────────────────────────────────────────────────────
    def _free_time(self):
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Free Time Finder", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text="Automatically finds your open time blocks based on your scheduled events.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 14))

        # ── Weekly overview ───────────────────────────────────────────────
        all_events = db.get_events()
        stats      = weekly_availability(all_events)

        overview = card(inner, pady=8, accent=True)
        ov_row   = tk.Frame(overview, bg=theme.SIDEBAR)
        ov_row.pack(fill="x", padx=16, pady=10)
        for label, val, col in [
            ("Scheduled Hours",  f"{stats['scheduled_hours']}h", theme.TEXT),
            ("Free Hours",        f"{stats['free_hours']}h",      theme.ACCENT),
            ("Availability",      f"{stats['availability_pct']}%",
             theme.ACCENT if stats["availability_pct"] >= 50 else "#e67e22"),
        ]:
            col_f = tk.Frame(ov_row, bg=theme.SIDEBAR, padx=20)
            col_f.pack(side="left")
            tk.Label(col_f, text=val, font=("Inter", 20, "bold"),
                     fg=col, bg=theme.SIDEBAR).pack()
            tk.Label(col_f, text=label, font=F_SMALL,
                     fg=theme.MUTED, bg=theme.SIDEBAR).pack()

        section_divider(inner)

        # ── Per-day free time ─────────────────────────────────────────────
        tk.Label(inner, text="Free Blocks by Day", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))

        # Day range controls
        ctrl_row = tk.Frame(inner, bg=theme.BG)
        ctrl_row.pack(anchor="w", pady=(0, 12))
        tk.Label(ctrl_row, text="Day window:", font=F_SMALL,
                 fg=theme.MUTED, bg=theme.BG).pack(side="left")
        start_var = ttk.Combobox(ctrl_row, values=[f"{h:02d}:00" for h in range(6, 13)],
                                  state="readonly", width=6, font=F_SMALL)
        start_var.set("08:00")
        start_var.pack(side="left", padx=(4, 2))
        tk.Label(ctrl_row, text="–", fg=theme.TEXT, bg=theme.BG).pack(side="left")
        end_var = ttk.Combobox(ctrl_row, values=[f"{h:02d}:00" for h in range(18, 24)],
                                state="readonly", width=6, font=F_SMALL)
        end_var.set("22:00")
        end_var.pack(side="left", padx=(2, 16))

        # Earning potential toggle — off by default
        show_potential_var = tk.BooleanVar(value=False)

        def _toggle_potential():
            if show_potential_var.get():
                potential_btn.config(
                    text="* Earning Potential  ON",
                    fg=theme.ACCENT,
                    bg=theme.ACCENT_L,
                )
            else:
                potential_btn.config(
                    text="* Earning Potential  OFF",
                    fg=theme.MUTED,
                    bg=theme.BG,
                )
            refresh_free()

        potential_btn = tk.Button(
            ctrl_row,
            text="* Earning Potential  OFF",
            font=F_SMALL,
            fg=theme.MUTED,
            bg=theme.BG,
            activebackground=theme.ACCENT_L,
            activeforeground=theme.ACCENT,
            relief="flat", bd=0,
            cursor="hand2",
            command=lambda: [
                show_potential_var.set(not show_potential_var.get()),
                _toggle_potential(),
            ],
        )
        potential_btn.pack(side="left")

        free_frame = tk.Frame(inner, bg=theme.BG)
        free_frame.pack(fill="x")

        # Opportunity cost: collect work job rates from ShiftIQ jobs
        def _work_rates() -> list[tuple[str, float]]:
            from model import FREQUENCIES
            rates = []
            for job in self._app.state.jobs:
                # Convert to hourly: Weekly / 40 approx, or use as-is if per-hour
                wk = job.weekly_income()
                hr = wk / 40  # rough estimate
                rates.append((job.name, round(hr, 2)))
            return rates

        def refresh_free(*_):
            for w in free_frame.winfo_children():
                w.destroy()
            day_start = start_var.get() if start_var.get() else "08:00"
            day_end   = end_var.get()   if end_var.get()   else "22:00"
            work_rates = _work_rates()

            for day in DAYS:
                day_events = [e for e in all_events if e.day == day]
                free_blocks = get_free_blocks(day_events, day_start, day_end)
                biggest     = largest_free_block(day_events, day_start, day_end)

                day_hdr = tk.Frame(free_frame, bg=theme.BG)
                day_hdr.pack(fill="x", pady=(10, 2))
                tk.Label(day_hdr, text=day, font=("Inter", 12, "bold"),
                         fg=theme.TEXT, bg=theme.BG).pack(side="left")

                if not free_blocks:
                    tk.Label(day_hdr,
                             text="  Fully scheduled",
                             font=F_SMALL, fg=theme.DANGER, bg=theme.BG).pack(side="left")
                    continue

                total_free = sum(b["duration_hours"] for b in free_blocks)
                tk.Label(day_hdr,
                         text=f"  {fmt_duration(total_free)} free",
                         font=F_SMALL, fg=theme.ACCENT, bg=theme.BG).pack(side="left")

                c = tk.Frame(free_frame, bg=theme.SIDEBAR,
                              highlightbackground=theme.BORDER, highlightthickness=1)
                c.pack(fill="x", pady=2)

                for block in free_blocks:
                    br = tk.Frame(c, bg=theme.SIDEBAR)
                    br.pack(fill="x", padx=14, pady=4)
                    is_biggest = (biggest and
                                  block["start"] == biggest["start"] and
                                  block["end"]   == biggest["end"])
                    col = theme.ACCENT if is_biggest else theme.TEXT
                    badge = "  ★ Largest" if is_biggest else ""
                    tk.Label(br,
                             text=f"{fmt_time(block['start'])} – {fmt_time(block['end'])}"
                                  f"  ({fmt_duration(block['duration_hours'])}){badge}",
                             font=("Inter", 10, "bold" if is_biggest else "normal"),
                             fg=col, bg=theme.SIDEBAR).pack(side="left")

                # Opportunity cost — only when toggle is ON
                if show_potential_var.get() and biggest and work_rates:
                    opp = opportunity_cost(biggest, work_rates)
                    if opp:
                        opp_row = tk.Frame(c, bg=theme.ACCENT_L)
                        opp_row.pack(fill="x", padx=0, pady=(4, 0))
                        tk.Label(opp_row,
                                 text="  * Earning potential in largest block:",
                                 font=F_SMALL, fg=theme.ACCENT, bg=theme.ACCENT_L,
                                 padx=14, pady=4).pack(anchor="w")
                        for o in opp[:3]:
                            tk.Label(opp_row,
                                     text=f"     {o['job']}:  ${o['potential_income']:.2f}",
                                     font=F_SMALL, fg=theme.ACCENT, bg=theme.ACCENT_L,
                                     padx=14).pack(anchor="w")

        start_var.bind("<<ComboboxSelected>>", refresh_free)
        end_var.bind("<<ComboboxSelected>>",   refresh_free)
        refresh_free()

    # ─────────────────────────────────────────────────────────────────────
    # TAB 5: Income
    # ─────────────────────────────────────────────────────────────────────
    def _income(self):
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Income from Schedule", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text="Based on your scheduled work events and their hourly rates.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 14))

        all_events = db.get_events()
        summary    = weekly_income_summary(all_events)

        # ── Hero totals ───────────────────────────────────────────────────
        hero = tk.Frame(inner, bg=theme.ACCENT, pady=20, padx=24)
        hero.pack(fill="x", pady=(0, 16))
        tk.Label(hero, text="Estimated Weekly Income",
                 font=("Inter", 10), fg="#b2d8c8", bg=theme.ACCENT).pack(anchor="w")
        tk.Label(hero, text=f"${summary['total_income']:,.2f}",
                 font=("Inter", 26, "bold"), fg="white", bg=theme.ACCENT).pack(anchor="w")
        tk.Label(hero,
                 text=f"{summary['total_work_hours']} work hours scheduled this week",
                 font=("Inter", 10), fg="#b2d8c8", bg=theme.ACCENT).pack(anchor="w", pady=(2, 0))

        if not summary["by_job"]:
            tk.Label(inner,
                     text="Add Work events with an hourly rate to see your income breakdown.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=12)
        else:
            # ── Per-job breakdown ─────────────────────────────────────────
            tk.Label(inner, text="By Job", font=F_H2,
                     fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(4, 6))
            c = card(inner)
            hdr = tk.Frame(c, bg=theme.ACCENT)
            hdr.pack(fill="x")
            for txt, w in [("Job / Shift", 24), ("Hours", 10),
                            ("Rate", 10), ("Income", 14)]:
                tk.Label(hdr, text=txt, font=("Inter", 10, "bold"), fg="white",
                         bg=theme.ACCENT, width=w, anchor="w").pack(side="left", padx=8, pady=5)

            for job_name, vals in summary["by_job"].items():
                row = tk.Frame(c, bg=theme.SIDEBAR,
                               highlightbackground=theme.BORDER, highlightthickness=1)
                row.pack(fill="x", pady=1)
                color = _cat_color("Work")
                tk.Label(row, text=job_name, font=("Inter", 10, "bold"),
                         fg=color, bg=theme.SIDEBAR,
                         width=24, anchor="w").pack(side="left", padx=8, pady=8)
                tk.Label(row, text=f"{vals['hours']}h",
                         font=F_SMALL, fg=theme.TEXT, bg=theme.SIDEBAR, width=10).pack(side="left")
                tk.Label(row, text=f"${vals['rate']:.2f}/hr",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR, width=10).pack(side="left")
                tk.Label(row, text=f"${vals['income']:.2f}",
                         font=("Inter", 10, "bold"), fg=color,
                         bg=theme.SIDEBAR, width=14).pack(side="left")

            # Total row
            total_row = tk.Frame(c, bg=theme.ACCENT_L)
            total_row.pack(fill="x", pady=(2, 0))
            tk.Label(total_row, text="Total", font=("Inter", 11, "bold"),
                     fg=theme.ACCENT, bg=theme.ACCENT_L,
                     width=24, anchor="w").pack(side="left", padx=8, pady=8)
            tk.Label(total_row, text=f"{summary['total_work_hours']}h",
                     font=("Inter", 11, "bold"), fg=theme.ACCENT,
                     bg=theme.ACCENT_L, width=10).pack(side="left")
            tk.Label(total_row, text="",
                     bg=theme.ACCENT_L, width=10).pack(side="left")
            tk.Label(total_row, text=f"${summary['total_income']:.2f}",
                     font=("Inter", 11, "bold"), fg=theme.ACCENT,
                     bg=theme.ACCENT_L, width=14).pack(side="left")

        # ── Cross-reference with ShiftIQ jobs ─────────────────────────────────
        fre_income = self._app.state.total_income_per_week()
        if fre_income > 0:
            section_divider(inner)
            tk.Label(inner, text="ShiftIQ vs Scheduled", font=F_H2,
                     fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 6))
            tk.Label(inner,
                     text="Comparing your entered job income (ShiftIQ) against what your "
                          "schedule actually shows this week.",
                     font=F_SMALL, fg=theme.MUTED, bg=theme.BG,
                     wraplength=640, justify="left").pack(anchor="w", pady=(0, 8))
            cc = card(inner)
            kv_row(cc, "ShiftIQ Jobs (weekly estimate)",
                   f"${fre_income:,.2f}", theme.TEXT)
            kv_row(cc, "Scheduled Work Income",
                   f"${summary['total_income']:,.2f}", theme.ACCENT)
            diff = summary["total_income"] - fre_income
            diff_color = theme.ACCENT if diff >= 0 else theme.DANGER
            kv_row(cc, "Difference",
                   f"${diff:+,.2f}", diff_color)
            if diff < 0:
                tk.Label(cc,
                         text="  Your scheduled hours earn less than your ShiftIQ estimate. "
                              "You may need more shifts or a higher rate.",
                         font=F_SMALL, fg=theme.DANGER, bg=theme.SIDEBAR,
                         wraplength=600, padx=16, pady=(0, 8)).pack(anchor="w")
            else:
                tk.Label(cc,
                         text="  Your scheduled hours match or exceed your ShiftIQ income estimate.",
                         font=F_SMALL, fg=theme.ACCENT, bg=theme.SIDEBAR,
                         wraplength=600, padx=16, pady=(0, 8)).pack(anchor="w")

    # ─────────────────────────────────────────────────────────────────────
    # HELPER: Fuzzy job-name lookup
    # ─────────────────────────────────────────────────────────────────────
    def _get_known_rate(self, job_name: str) -> float | None:
        """
        Look up the hourly rate for job_name.  Uses canonical name comparison
        so 'admission', 'Admissions', and 'admissions' all share the same rate.
        Checks: events table, then fre_jobs (schedule_core).
        """
        canon = _canon(job_name)

        # Source 1: events table
        for ev in db.get_events():
            if ev.category == "Work" and ev.hourly_rate > 0 and _canon(ev.title) == canon:
                return ev.hourly_rate

        # Source 2: fre_jobs (schedule_core)
        try:
            from schedule_core import Scheduler
            for job in Scheduler().get_jobs():
                if job.hourly_rate > 0 and _canon(job.name) == canon:
                    return job.hourly_rate
        except Exception:
            pass

        return None

    @staticmethod
    def _fuzzy_match_job(name: str, jobs: list) -> object | None:
        """
        Return the best-matching Job from `jobs` for `name`, or None.

        Uses difflib similarity on lowercased names.  A match is accepted
        when the ratio is ≥ 0.82 — close enough to catch plurals and small
        typos ("admission" / "admissions", "cashier" / "cashiers") while
        staying far enough from completely different names.
        """
        from difflib import SequenceMatcher
        key = name.strip().lower()
        best_job   = None
        best_ratio = 0.0
        for j in jobs:
            ratio = SequenceMatcher(None, key, j.name.strip().lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_job   = j
        return best_job if best_ratio >= 0.82 else None

    # ─────────────────────────────────────────────────────────────────────
    # HELPER: Sync ALL Work events → ShiftIQ Data on page load
    # ─────────────────────────────────────────────────────────────────────
    def _sync_all_work_to_state(self) -> None:
        """
        On Schedule page load, group ALL Work events by canonical name, then
        sync one entry per unique job to ShiftIQ Data.  Deduplicates state.jobs
        by canonical name first.
        """
        try:
            # ── Deduplicate state.jobs by canonical name ───────────────────
            seen_canon: set[str] = set()
            deduped = []
            for j in self._app.state.jobs:
                c = _canon(j.name)
                if c not in seen_canon:
                    seen_canon.add(c)
                    deduped.append(j)
            self._app.state.jobs[:] = deduped

            # ── Collect unique canonical job names from events ─────────────
            canon_names: dict[str, str] = {}   # canon_key → display name
            for ev in db.get_events():
                if ev.category == "Work" and ev.title.strip():
                    c = _canon(ev.title)
                    if c not in canon_names:
                        canon_names[c] = c   # canonical IS the display name

            for name in canon_names.values():
                self._sync_work_to_state(name, 0.0)

        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # HELPER: Sync a Work event into ShiftIQ Data (jobs) if it doesn't exist
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _shift_hours(ev) -> float:
        """Duration-aware hours for a ScheduleEvent, including overnight shifts."""
        from schedule_event import to_minutes
        s = to_minutes(ev.start_time)
        e = to_minutes(ev.end_time)
        if s == e:
            return 0.0
        if e < s:          # overnight — e.g. 22:00 → 06:00
            e += 24 * 60
        return (e - s) / 60.0

    def _sync_work_to_state(self, job_name: str, hourly_rate: float,
                             _unused: float = 0.0) -> None:
        """
        Sync a Work job into ShiftIQ Data (income / analytics / forecasting).

        Reads ALL Work events for this job from the events table, sums the
        hours (overnight-aware), multiplies by rate, then creates or updates
        the ShiftIQ Job entry.  Bypasses the >0 validation when rate is unknown
        so the job still appears in Data with a $0 placeholder.
        """
        try:
            from model import Job as FREJob

            canon = _canon(job_name)

            # ── Total hours across ALL canonical-matching Work events ──────
            all_work = [
                e for e in db.get_events()
                if e.category == "Work" and _canon(e.title) == canon
            ]
            total_hours = sum(self._shift_hours(e) for e in all_work)

            # Pick up rate from event records if not supplied
            if hourly_rate <= 0:
                rates = [e.hourly_rate for e in all_work if e.hourly_rate > 0]
                hourly_rate = rates[0] if rates else 0.0

            weekly_amount = round(hourly_rate * total_hours, 2)

            # ── Create or update in ShiftIQ state (canonical lookup) ──────────
            existing = next(
                (j for j in self._app.state.jobs if _canon(j.name) == canon),
                None
            )

            if existing is None:
                # Only create a Data job if we have a real weekly amount
                if weekly_amount > 0:
                    new_job = FREJob(canon, weekly_amount, "Weekly")
                    self._app.state.add_job(new_job)
                # If rate is unknown, don't create a $0 placeholder — wait
                # until the user sets a rate
            else:
                if weekly_amount > 0:
                    existing.amount = weekly_amount
                    existing.name   = canon
                    db.update_job_amount(canon, weekly_amount)

        except Exception:
            pass  # never crash the Schedule page over a sync error

    # ─────────────────────────────────────────────────────────────────────
    # TAB 6: Import Schedule
    # ─────────────────────────────────────────────────────────────────────
    def _import_schedule(self):
        try:
            from date_parser import parse_schedule as _parse_dates
        except ImportError:
            tk.Label(self._body,
                     text="date_parser.py not found. Make sure it's in the same folder.",
                     font=F_BODY, fg=theme.DANGER, bg=theme.BG).pack(pady=40)
            return

        # Plain frame — no canvas/ScrollFrame so fill="x" always works reliably.
        outer = tk.Frame(self._body, bg=theme.BG)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=theme.BG)
        inner.pack(fill="x", padx=36, pady=20)

        # ── Header ────────────────────────────────────────────────────────
        tk.Label(inner, text="Import Schedule", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text="Paste your full weekly schedule as text. One job per line.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 2))

        # ── Week selector ─────────────────────────────────────────────────
        import_week_start = [week_engine.get_week_start()]   # mutable cell

        week_nav = tk.Frame(inner, bg=theme.BG)
        week_nav.pack(anchor="w", pady=(4, 8))

        week_lbl_var = tk.StringVar()

        def _refresh_week_label():
            ws = import_week_start[0]
            we = ws + __import__("datetime").timedelta(days=6)
            suffix = "  (This Week)" if week_engine.is_current_week(ws) else ""
            week_lbl_var.set(f"Importing for:  {week_engine.week_label(ws, we)}{suffix}")

        _refresh_week_label()

        tk.Button(week_nav, text="←",
                  font=F_SMALL, fg=theme.ACCENT, bg=theme.BG,
                  relief="flat", cursor="hand2",
                  command=lambda: (
                      import_week_start.__setitem__(0,
                          week_engine.get_previous_week(import_week_start[0])[0]),
                      _refresh_week_label()
                  )).pack(side="left")

        tk.Label(week_nav, textvariable=week_lbl_var,
                 font=("Inter", 10, "bold"), fg=theme.ACCENT,
                 bg=theme.BG).pack(side="left", padx=8)

        tk.Button(week_nav, text="→",
                  font=F_SMALL, fg=theme.ACCENT, bg=theme.BG,
                  relief="flat", cursor="hand2",
                  command=lambda: (
                      import_week_start.__setitem__(0,
                          week_engine.get_next_week(import_week_start[0])[0]),
                      _refresh_week_label()
                  )).pack(side="left")

        # ── Format hint (collapsible) ─────────────────────────────────────
        hint_box = tk.Frame(inner, bg=theme.ACCENT_L,
                            highlightbackground=theme.BORDER, highlightthickness=1)
        hint_box.pack(fill="x", pady=(0, 16))

        _hint_open = [False]   # collapsed by default

        hint_header_row = tk.Frame(hint_box, bg=theme.ACCENT_L, cursor="hand2")
        hint_header_row.pack(fill="x")

        toggle_lbl = tk.Label(hint_header_row, text="▶  Supported formats (auto-detected)  — click to expand",
                              font=("Inter", 10, "bold"), fg=theme.ACCENT,
                              bg=theme.ACCENT_L, padx=14, pady=8, anchor="w")
        toggle_lbl.pack(fill="x")

        # Build the detail section (hidden initially)
        hint_detail = tk.Frame(hint_box, bg=theme.ACCENT_L)

        format_sections = [
            ("Weekly (default — uses the week selected above):",
             ["Admissions: Mon 9-12 Wed 14-17 Fri 10-13",
              "Cashier: Tue 17-21 Thu 9-13",
              "cashier wed 12-9   or   wed cashier 12-9"]),
            ("Daily (all shifts on one date):",
             ["Date: 2026-06-18",
              "Admissions: 9-12",
              "Library: 14-17"]),
            ("Monthly (explicit date per shift):",
             ["Month: 2026-06",
              "Admissions: 2026-06-01 9-12  2026-06-03 2-5",
              "Library: 2026-06-07 1-4  2026-06-14 1-4"]),
        ]
        for section_title, section_lines in format_sections:
            tk.Label(hint_detail, text=f"  {section_title}",
                     font=("Inter", 9, "bold"), fg=theme.TEXT,
                     bg=theme.ACCENT_L, padx=14, pady=4).pack(anchor="w")
            for ln in section_lines:
                tk.Label(hint_detail, text=f"      {ln}",
                         font=("Courier", 9), fg=theme.TEXT,
                         bg=theme.ACCENT_L, padx=14, pady=1).pack(anchor="w")
        tk.Label(hint_detail,
                 text="  Night shifts: 22-6   |   Times: 9-12 or 9:30-12:00",
                 font=F_SMALL, fg=theme.MUTED,
                 bg=theme.ACCENT_L, padx=14, pady=6).pack(anchor="w")

        def _toggle_hint(_event=None):
            if _hint_open[0]:
                hint_detail.pack_forget()
                toggle_lbl.config(text="▶  Supported formats (auto-detected)  — click to expand")
            else:
                hint_detail.pack(fill="x")
                toggle_lbl.config(text="▼  Supported formats (auto-detected)  — click to collapse")
            _hint_open[0] = not _hint_open[0]

        hint_header_row.bind("<Button-1>", _toggle_hint)
        toggle_lbl.bind("<Button-1>", _toggle_hint)

        # ── Text area ─────────────────────────────────────────────────────
        paste_row = tk.Frame(inner, bg=theme.BG)
        paste_row.pack(fill="x", pady=(0, 4))
        tk.Label(paste_row, text="Paste your schedule here:",
                 font=("Inter", 11, "bold"), fg=theme.TEXT,
                 bg=theme.BG).pack(side="left")
        tk.Label(paste_row, text="  or  ", font=F_SMALL,
                 fg=theme.MUTED, bg=theme.BG).pack(side="left")
        tk.Button(paste_row, text="Browse file...",
                  font=F_SMALL, fg=theme.ACCENT, bg=theme.BG,
                  activeforeground=theme.ACCENT, activebackground=theme.BG,
                  relief="flat", cursor="hand2",
                  command=lambda: _load_file()).pack(side="left")

        text_frame = tk.Frame(inner, bg=theme.BORDER, padx=1, pady=1)
        text_frame.pack(fill="x", pady=(0, 12))
        txt = tk.Text(text_frame,
                      height=10,
                      font=("Courier", 11),
                      fg=theme.TEXT,
                      bg=theme.SIDEBAR,
                      insertbackground=theme.TEXT,
                      relief="flat",
                      wrap="word",
                      padx=12, pady=10)
        txt.pack(fill="x")

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = tk.Frame(inner, bg=theme.BG)
        btn_row.pack(fill="x", pady=(0, 16))

        result_frame = tk.Frame(inner, bg=theme.BG)
        result_frame.pack(fill="x")

        def _load_file():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="Open schedule file (txt or csv)",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("CSV files",  "*.csv"),
                    ("All files",  "*.*"),
                ],
            )
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                txt.delete("1.0", "end")
                txt.insert("1.0", content)
            except OSError as exc:
                for w in result_frame.winfo_children():
                    w.destroy()
                tk.Label(result_frame,
                         text=f"⚠  Could not open file: {exc}",
                         font=F_BODY, fg=theme.DANGER, bg=theme.BG).pack(anchor="w")

        def _do_import():
            raw = txt.get("1.0", "end").strip()
            for w in result_frame.winfo_children():
                w.destroy()

            if not raw:
                tk.Label(result_frame,
                         text="⚠  Nothing to import — paste your schedule above.",
                         font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
                return

            # ── Parse with date_parser (daily / weekly / monthly) ───────────
            from date_parser import parse_schedule as _parse_dates
            from schedule_event import ScheduleEvent as _SE

            parsed = _parse_dates(raw, week_start=import_week_start[0])

            # Show parse errors immediately if nothing could be read
            if parsed.errors:
                err_box = tk.Frame(result_frame, bg=theme.BG,
                                   highlightbackground=theme.DANGER,
                                   highlightthickness=1)
                err_box.pack(fill="x", pady=(0, 8))
                tk.Label(err_box,
                         text=f"✗  {len(parsed.errors)} error(s)",
                         font=("Inter", 11, "bold"), fg=theme.DANGER,
                         bg=theme.BG, padx=14, pady=6).pack(anchor="w")
                for e in parsed.errors:
                    tk.Label(err_box, text=f"   {e}",
                             font=("Courier", 10), fg=theme.DANGER,
                             bg=theme.BG, padx=14, pady=2,
                             wraplength=580, justify="left").pack(anchor="w")
                tk.Label(err_box, text="", bg=theme.BG, pady=2).pack()

            if parsed.warnings:
                w_box = tk.Frame(result_frame, bg=theme.BG,
                                 highlightbackground=theme.BORDER,
                                 highlightthickness=1)
                w_box.pack(fill="x", pady=(0, 8))
                tk.Label(w_box, text=f"⚠  {len(parsed.warnings)} warning(s)",
                         font=("Inter", 11, "bold"), fg=theme.MUTED,
                         bg=theme.BG, padx=14, pady=6).pack(anchor="w")
                for w in parsed.warnings:
                    tk.Label(w_box, text=f"   {w}",
                             font=("Courier", 10), fg=theme.MUTED,
                             bg=theme.BG, padx=14, pady=1,
                             wraplength=580, justify="left").pack(anchor="w")

            if not parsed.shifts:
                return

            # ── Build list of existing canonical job names for normalization ─
            existing_work_events = db.get_events()
            existing_job_names: list[str] = []
            seen_keys: set[str] = set()
            for ev0 in existing_work_events:
                if ev0.category == "Work" and ev0.title.strip():
                    key = _canon(ev0.title)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        existing_job_names.append(ev0.title.strip())

            # ── Write directly to events table (skip fre_jobs/fre_shifts) ───
            saved_shifts = []
            skipped = []
            for ps in parsed.shifts:
                # Normalize job name against existing canonical names
                canonical_name = _normalize_job_name(ps.job_name, existing_job_names)
                # Add this canonical name for subsequent shifts in the same import
                if canonical_name not in existing_job_names:
                    existing_job_names.append(canonical_name)

                # date_parser already resolved the concrete ISO date
                shift_date_str = ps.date   # "YYYY-MM-DD" or ""

                # Rate priority: inline rate in text > rate already in DB
                inline_rate = getattr(ps, "rate", 0.0) or 0.0
                db_rate     = self._get_known_rate(canonical_name) or 0.0
                known_rate  = inline_rate if inline_rate > 0 else db_rate

                # If an inline rate was given, save it to the DB immediately
                # so future imports / manual adds pick it up automatically.
                if inline_rate > 0:
                    db.update_events_rate(canonical_name, inline_rate)

                # Infer category:
                #   - inline rate OR existing DB rate → Work (it's a job)
                #   - otherwise keyword-detect the event type
                def _infer_cat(name: str, rate: float) -> str:
                    if rate > 0:
                        return "Work"
                    t = name.lower()
                    if any(w in t for w in ["class", "lecture", "lab", "seminar", "course", "101", "201", "301"]):
                        return "Class"
                    if any(w in t for w in ["study", "homework", "hw", "review", "tutoring", "session", "calculus", "algebra", "biology", "chemistry", "physics", "english", "history", "writing"]):
                        return "Study"
                    if any(w in t for w in ["meeting", "club", "group", "committee", "board", "org", "organization"]):
                        return "Meeting"
                    if any(w in t for w in ["gym", "workout", "personal", "church", "appointment", "doctor", "dentist", "hair", "lunch", "dinner", "break"]):
                        return "Personal"
                    return "Personal"

                inferred_category = _infer_cat(canonical_name, known_rate)
                ev = _SE(
                    title=canonical_name,
                    category=inferred_category,
                    day=ps.day,
                    start_time=ps.start_time,
                    end_time=ps.end_time,
                    hourly_rate=known_rate,
                    notes="",
                    shift_date=shift_date_str,
                )
                # Skip exact duplicates (same job + date + times)
                if shift_date_str:
                    date_evs = db.get_events_for_date(shift_date_str)
                    is_dup = any(
                        _canon(e.title) == _canon(canonical_name)
                        and e.start_time == ps.start_time
                        and e.end_time == ps.end_time
                        for e in date_evs
                    )
                else:
                    existing_day = db.get_events(ps.day)
                    is_dup = any(
                        _canon(e.title) == _canon(canonical_name)
                        and e.start_time == ps.start_time
                        and e.end_time == ps.end_time
                        for e in existing_day
                    )
                if is_dup:
                    # Fix category on the existing record if it was mis-labeled
                    existing_evs = (
                        db.get_events_for_date(shift_date_str)
                        if shift_date_str
                        else db.get_events(ps.day)
                    )
                    for existing_ev in existing_evs:
                        if (
                            _canon(existing_ev.title) == _canon(canonical_name)
                            and existing_ev.start_time == ps.start_time
                            and existing_ev.end_time == ps.end_time
                            and existing_ev.category != inferred_category
                        ):
                            db.update_event(existing_ev.id, category=inferred_category)
                    skipped.append(ps)
                    continue
                db.add_event(ev)
                saved_shifts.append({"job_name": canonical_name, "day": ps.day,
                                     "start_time": ps.start_time,
                                     "end_time": ps.end_time,
                                     "shift_date": shift_date_str,
                                     "category": inferred_category})

            # ── Clear the text box on successful import ───────────────────────
            if saved_shifts:
                txt.delete("1.0", "end")

            # ── Show saved summary ────────────────────────────────────────────
            if saved_shifts:
                from schedule_core import _fmt12
                ok_box = tk.Frame(result_frame, bg=theme.ACCENT_L,
                                  highlightbackground=theme.BORDER,
                                  highlightthickness=1)
                ok_box.pack(fill="x", pady=(0, 8))
                tk.Label(ok_box,
                         text=f"✓  {len(saved_shifts)} shift(s) saved",
                         font=("Inter", 11, "bold"), fg=theme.ACCENT,
                         bg=theme.ACCENT_L, padx=14, pady=6).pack(anchor="w")
                for s in saved_shifts:
                    hrs = self._shift_hours(
                        type("_E", (), {"start_time": s["start_time"],
                                        "end_time": s["end_time"]})()
                    )
                    tk.Label(ok_box,
                             text=f"   {s['job_name']}  {s['day']}  "
                                  f"{_fmt12(s['start_time'])} – {_fmt12(s['end_time'])}  ({hrs:.1f}h)",
                             font=("Courier", 10), fg=theme.TEXT,
                             bg=theme.ACCENT_L, padx=14, pady=1).pack(anchor="w")
                tk.Label(ok_box, text="", bg=theme.ACCENT_L, pady=2).pack()

            if skipped:
                tk.Label(result_frame,
                         text=f"—  {len(skipped)} duplicate(s) skipped",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")

            if not saved_shifts and not skipped:
                tk.Label(result_frame,
                         text="No shifts were saved.",
                         font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
                return

            # ── Rate prompt for Work jobs with no rate ────────────────────
            if saved_shifts:
                seen_canon: dict[str, str] = {}
                for s in saved_shifts:
                    key = _canon(s["job_name"])
                    if key not in seen_canon:
                        seen_canon[key] = s  # store full dict to access category

                jobs_needing_rate: list[str] = []
                for key, s_data in seen_canon.items():
                    jname = s_data["job_name"]
                    # Only Work events participate in income / need a rate
                    if s_data.get("category", "Work") != "Work":
                        continue
                    known_rate = self._get_known_rate(jname)
                    if known_rate:
                        db.update_events_rate(jname, known_rate)
                        self._sync_work_to_state(jname, known_rate)
                    else:
                        jobs_needing_rate.append(jname)

                if jobs_needing_rate:
                    rate_box = tk.Frame(result_frame, bg=theme.ACCENT_L,
                                        highlightbackground=theme.BORDER,
                                        highlightthickness=1)
                    rate_box.pack(fill="x", pady=(8, 0))
                    tk.Label(rate_box,
                             text="Set hourly rates for new jobs:",
                             font=("Inter", 11, "bold"), fg=theme.ACCENT,
                             bg=theme.ACCENT_L, padx=14, pady=8).pack(anchor="w")

                    rate_entries: dict[str, tk.Entry] = {}
                    for jname in jobs_needing_rate:
                        row_f = tk.Frame(rate_box, bg=theme.ACCENT_L)
                        row_f.pack(fill="x", padx=14, pady=3)
                        tk.Label(row_f, text=f"{jname}:",
                                 font=("Inter", 10, "bold"), fg=theme.TEXT,
                                 bg=theme.ACCENT_L, width=20, anchor="w").pack(side="left")
                        tk.Label(row_f, text="$", font=F_BODY,
                                 fg=theme.TEXT, bg=theme.ACCENT_L).pack(side="left")
                        e = tk.Entry(row_f, font=F_BODY, width=8, relief="flat",
                                     highlightbackground=theme.BORDER,
                                     highlightthickness=1,
                                     bg=theme.SIDEBAR, fg=theme.TEXT,
                                     insertbackground=theme.TEXT)
                        e.pack(side="left", padx=(2, 4), ipady=4)
                        tk.Label(row_f, text="/hr", font=F_SMALL,
                                 fg=theme.MUTED, bg=theme.ACCENT_L).pack(side="left")
                        rate_entries[jname] = e

                    rate_status = tk.Label(rate_box, text="", font=F_SMALL,
                                           fg=theme.DANGER, bg=theme.ACCENT_L, padx=14)
                    rate_status.pack(anchor="w")

                    def _save_rates():
                        errs = []
                        for jname, entry in rate_entries.items():
                            val = entry.get().strip()
                            if not val:
                                continue
                            try:
                                rate = float(val)
                                if rate <= 0:
                                    raise ValueError
                                db.update_events_rate(jname, rate)
                                self._sync_work_to_state(jname, rate)
                                entry.config(bg="#d4edda")
                            except ValueError:
                                errs.append(f"{jname}: enter a number > 0")
                        if errs:
                            rate_status.config(text="\n".join(errs))
                        else:
                            rate_box.destroy()

                    btn_row2 = tk.Frame(rate_box, bg=theme.ACCENT_L)
                    btn_row2.pack(anchor="w", padx=14, pady=(4, 10))
                    tk.Button(btn_row2, text="Save Rates",
                              font=("Inter", 10, "bold"),
                              fg="white", bg=theme.ACCENT,
                              activeforeground="white",
                              activebackground=theme.ACCENT,
                              relief="flat", padx=16, pady=6,
                              cursor="hand2",
                              command=_save_rates).pack(side="left", padx=(0, 8))
                    tk.Button(btn_row2, text="No Rate",
                              font=("Inter", 10),
                              fg=theme.MUTED, bg=theme.ACCENT_L,
                              relief="flat", padx=10, pady=6,
                              cursor="hand2",
                              command=rate_box.destroy).pack(side="left")

        def _clear_all():
            txt.delete("1.0", "end")
            for w in result_frame.winfo_children():
                w.destroy()

        tk.Button(btn_row,
                  text="Import",
                  font=("Inter", 11, "bold"),
                  fg="white", bg=theme.ACCENT,
                  activeforeground="white", activebackground=theme.ACCENT,
                  relief="flat", padx=20, pady=8,
                  cursor="hand2",
                  command=_do_import).pack(side="left", padx=(0, 8))

        tk.Button(btn_row,
                  text="Clear",
                  font=("Inter", 11),
                  fg=theme.MUTED, bg=theme.SIDEBAR,
                  activeforeground=theme.TEXT, activebackground=theme.SIDEBAR,
                  relief="flat", padx=16, pady=8,
                  cursor="hand2",
                  command=_clear_all).pack(side="left")
