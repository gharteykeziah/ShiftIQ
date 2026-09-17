"""page_data.py — Data Management page (jobs, expenses, balance, import, log)."""
import tkinter as tk
import csv
from tkinter import filedialog

import backend.ui.theme as theme
import backend.core.activity_log as activity_log
from backend.ui.theme import F_BODY, F_SMALL, F_H2
from backend.core.widgets import (ScrollFrame, TabBar, page_title, card, kv_row,
                     labeled_entry, action_btn, status_lbl)
from backend.core.model import Job, Expense, FREQUENCIES


class DataManagementPage(tk.Frame):
    """Data management page: add/delete jobs and expenses, set balance, import CSV, view log."""
    def __init__(self, parent, app):
        """Set up tab bar and body frame; activate the Jobs tab."""
        super().__init__(parent, bg=theme.BG)
        self._app = app

        header = tk.Frame(self, bg=theme.BG, padx=36, pady=16)
        header.pack(fill="x")
        page_title(header, "Data Management", "Manage your jobs, expenses, and balance.")

        self._tab_bar = TabBar(self, [
            ("my_jobs",        "My Jobs"),
            ("my_expenses",    "My Expenses"),
            ("jobs",           "Add Job"),
            ("expenses",       "Add Expense"),
            ("delete_job",     "Delete Job"),
            ("delete_expense", "Delete Expense"),
            ("balance",        "Balance"),
            ("import_csv",     "Import CSV"),
            ("log",            "Activity Log"),
        ])
        self._tab_bar.pack(fill="x", padx=36)
        self._body = tk.Frame(self, bg=theme.BG)
        self._body.pack(fill="both", expand=True)
        self._tab_bar.bind_select(self._render_tab)
        self._tab_bar.activate("my_jobs")

    def _render_tab(self, key):
        """Destroy and rebuild the body frame for the selected tab key."""
        for w in self._body.winfo_children():
            w.destroy()
        {
            "my_jobs":        self._my_jobs,
            "my_expenses":    self._my_expenses,
            "jobs":           self._add_job,
            "expenses":       self._add_expense,
            "delete_job":     self._delete_job,
            "delete_expense": self._delete_expense,
            "balance":        self._set_balance,
            "import_csv":     self._import_csv,
            "log":            self._activity_log,
        }[key]()

    # ── My Jobs ──────────────────────────────────────────────────────────
    def _my_jobs(self):
        """Render the My Jobs tab — list of income sources with delete controls."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="My Jobs & Income Sources", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))

        if not state.jobs:
            tk.Label(inner, text="No income sources added yet. Go to Add Job to add one.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
            return

        search_var = tk.StringVar()
        search_row = tk.Frame(inner, bg=theme.BG)
        search_row.pack(anchor="w", fill="x", pady=(0, 8))
        tk.Label(search_row, text="Search:", font=F_SMALL,
                 fg=theme.MUTED, bg=theme.BG).pack(side="left")
        tk.Entry(search_row, textvariable=search_var, font=F_BODY, width=28,
                 bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT,
                 highlightbackground=theme.BORDER, highlightthickness=1,
                 relief="flat").pack(side="left", padx=8)

        table_frame = tk.Frame(inner, bg=theme.BG)
        table_frame.pack(fill="x")

        def refresh_jobs(*_):
            for w in table_frame.winfo_children():
                w.destroy()
            q = search_var.get().strip().lower()
            matches = [j for j in state.jobs if q in j.name.lower()] if q else state.jobs
            if not matches:
                tk.Label(table_frame, text="No jobs match your search.",
                         font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
                return
            c = card(table_frame)
            hdr = tk.Frame(c, bg=theme.ACCENT)
            hdr.pack(fill="x")
            for txt, w in [("Name", 22), ("Amount", 16), ("Weekly Equiv.", 16)]:
                tk.Label(hdr, text=txt, font=("Inter", 10, "bold"), fg="white",
                         bg=theme.ACCENT, width=w, anchor="w").pack(side="left", padx=8, pady=5)
            for job in matches:
                row = tk.Frame(c, bg=theme.SIDEBAR,
                               highlightbackground=theme.BORDER, highlightthickness=1)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=job.name, font=("Inter", 10, "bold"),
                         fg=theme.TEXT, bg=theme.SIDEBAR,
                         width=22, anchor="w").pack(side="left", padx=8, pady=8)
                tk.Label(row, text=f"${job.amount:.2f}/{job.frequency}",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR, width=16).pack(side="left")
                tk.Label(row, text=f"${job.weekly_income():.2f}/wk",
                         font=("Inter", 10, "bold"), fg=theme.ACCENT,
                         bg=theme.SIDEBAR, width=16).pack(side="left")
            total = tk.Frame(c, bg=theme.ACCENT_L)
            total.pack(fill="x", pady=(2, 0))
            tk.Label(total, text="Total Weekly Income", font=("Inter", 11, "bold"),
                     fg=theme.ACCENT, bg=theme.ACCENT_L, width=22,
                     anchor="w").pack(side="left", padx=8, pady=8)
            tk.Label(total, text=f"${state.total_income_per_week():.2f}/wk",
                     font=("Inter", 11, "bold"),
                     fg=theme.ACCENT, bg=theme.ACCENT_L).pack(side="right", padx=8)

        search_var.trace_add("write", refresh_jobs)
        refresh_jobs()

    # ── My Expenses ──────────────────────────────────────────────────────
    def _my_expenses(self):
        """Render the My Expenses tab — list of expenses with delete controls."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="My Expenses", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))

        if not state.expenses:
            tk.Label(inner, text="No expenses added yet. Go to Add Expense to add one.",
                     font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
            return

        exp_search_var = tk.StringVar()
        exp_search_row = tk.Frame(inner, bg=theme.BG)
        exp_search_row.pack(anchor="w", fill="x", pady=(0, 8))
        tk.Label(exp_search_row, text="Search:", font=F_SMALL,
                 fg=theme.MUTED, bg=theme.BG).pack(side="left")
        tk.Entry(exp_search_row, textvariable=exp_search_var, font=F_BODY, width=28,
                 bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT,
                 highlightbackground=theme.BORDER, highlightthickness=1,
                 relief="flat").pack(side="left", padx=8)

        exp_table = tk.Frame(inner, bg=theme.BG)
        exp_table.pack(fill="x")

        def refresh_expenses(*_):
            for w in exp_table.winfo_children():
                w.destroy()
            q = exp_search_var.get().strip().lower()
            matches = ([e for e in state.expenses
                        if q in e.name.lower() or q in e.category.lower()]
                       if q else state.expenses)
            if not matches:
                tk.Label(exp_table, text="No expenses match your search.",
                         font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")
                return
            c = card(exp_table)
            hdr = tk.Frame(c, bg=theme.ACCENT)
            hdr.pack(fill="x")
            for txt, w in [("Name", 20), ("Amount", 16), ("Category", 14), ("Weekly Equiv.", 14)]:
                tk.Label(hdr, text=txt, font=("Inter", 10, "bold"), fg="white",
                         bg=theme.ACCENT, width=w, anchor="w").pack(side="left", padx=8, pady=5)
            for exp in matches:
                row = tk.Frame(c, bg=theme.SIDEBAR,
                               highlightbackground=theme.BORDER, highlightthickness=1)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=exp.name, font=("Inter", 10, "bold"),
                         fg=theme.TEXT, bg=theme.SIDEBAR,
                         width=20, anchor="w").pack(side="left", padx=8, pady=8)
                tk.Label(row, text=f"${exp.amount:.2f}/{exp.frequency}",
                         font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR, width=16).pack(side="left")
                tk.Label(row, text=exp.category,
                         font=F_SMALL, fg=theme.MUTED, bg=theme.SIDEBAR, width=14).pack(side="left")
                tk.Label(row, text=f"${exp.weekly_amount():.2f}/wk",
                         font=("Inter", 10, "bold"), fg=theme.DANGER,
                         bg=theme.SIDEBAR, width=14).pack(side="left")
            # Danger-tinted total footer
            danger_bg = theme.ACCENT_L  # use accent-tinted background even for expenses total
            total = tk.Frame(c, bg=danger_bg)
            total.pack(fill="x", pady=(2, 0))
            tk.Label(total, text="Total Weekly Expenses", font=("Inter", 11, "bold"),
                     fg=theme.DANGER, bg=danger_bg, width=22,
                     anchor="w").pack(side="left", padx=8, pady=8)
            tk.Label(total, text=f"${state.total_expense_per_week():.2f}/wk",
                     font=("Inter", 11, "bold"),
                     fg=theme.DANGER, bg=danger_bg).pack(side="right", padx=8)

        exp_search_var.trace_add("write", refresh_expenses)
        refresh_expenses()

    # ── Add Job ──────────────────────────────────────────────────────────
    def _add_job(self):
        """Render the Add Income tab — form to create a new income source."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Add a New Income Source", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner, text="Enter what you earn and how often you earn it.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 10))

        name_e   = labeled_entry(inner, "Job / Income Name  (e.g. Starbucks, Freelance, Allowance)")
        amount_e = labeled_entry(inner, "Amount Earned ($)", width=16)

        tk.Label(inner, text="How often do you earn this?", font=F_BODY,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(10, 4))
        freq_var = tk.StringVar(value="Weekly")
        freq_row = tk.Frame(inner, bg=theme.BG)
        freq_row.pack(anchor="w")
        for f in FREQUENCIES:
            tk.Radiobutton(freq_row, text=f, variable=freq_var, value=f,
                           font=F_BODY, fg=theme.TEXT, bg=theme.BG,
                           activebackground=theme.BG,
                           selectcolor=theme.ACCENT_L).pack(side="left", padx=6)

        status = tk.Frame(inner, bg=theme.BG)
        status.pack(anchor="w")

        def submit():
            for w in status.winfo_children():
                w.destroy()
            try:
                name = name_e.get().strip()
                if not name:
                    raise ValueError("Income name cannot be empty.")
                amount = _pf(amount_e, "Amount")
                if amount <= 0:
                    raise ValueError("Amount must be greater than zero.")
                freq   = freq_var.get()
                weekly = amount * {"Daily": 7, "Weekly": 1,
                                   "Biweekly": 0.5, "Monthly": 12/52}[freq]
                ok, msg = state.add_job(Job(name, amount, freq))
                if ok:
                    status_lbl(status,
                               f"{name} added — ${amount:.2f}/{freq}"
                               f"  (≈ ${weekly:.2f}/week)", True)
                    name_e.delete(0, "end")
                    amount_e.delete(0, "end")
                else:
                    status_lbl(status, msg, False)
            except ValueError as e:
                status_lbl(status, str(e), False)

        action_btn(inner, "Add Income Source", submit)

    # ── Add Expense ──────────────────────────────────────────────────────
    def _add_expense(self):
        """Render the Add Expense tab — form to create a new expense."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Add a New Expense", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner, text="Enter what you spend and how often you spend it.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 10))

        name_e     = labeled_entry(inner, "Expense Name  (e.g. Rent, Groceries, Coffee)")
        amount_e   = labeled_entry(inner, "Amount ($)", width=16)
        category_e = labeled_entry(inner, "Category  (e.g. Housing, Food, Transport)")
        date_e     = labeled_entry(inner, "Date (YYYY-MM-DD)")

        tk.Label(inner, text="How often do you pay this?", font=F_BODY,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(10, 4))
        freq_var = tk.StringVar(value="Monthly")
        freq_row = tk.Frame(inner, bg=theme.BG)
        freq_row.pack(anchor="w")
        for f in FREQUENCIES:
            tk.Radiobutton(freq_row, text=f, variable=freq_var, value=f,
                           font=F_BODY, fg=theme.TEXT, bg=theme.BG,
                           activebackground=theme.BG,
                           selectcolor=theme.ACCENT_L).pack(side="left", padx=6)

        status = tk.Frame(inner, bg=theme.BG)
        status.pack(anchor="w")

        def submit():
            for w in status.winfo_children():
                w.destroy()
            try:
                name     = name_e.get().strip()
                category = category_e.get().strip()
                date     = date_e.get().strip()
                if not name:     raise ValueError("Expense name cannot be empty.")
                if not category: raise ValueError("Category cannot be empty.")
                if not date:     raise ValueError("Date cannot be empty.")
                amount = _pf(amount_e, "Amount")
                if amount <= 0:  raise ValueError("Amount must be greater than zero.")
                freq   = freq_var.get()
                weekly = amount * {"Daily": 7, "Weekly": 1,
                                   "Biweekly": 0.5, "Monthly": 12/52}[freq]
                ok, msg = state.add_expense(Expense(name, amount, category, date, freq))
                if ok:
                    status_lbl(status,
                               f"{name} added — ${amount:.2f}/{freq}"
                               f"  (≈ ${weekly:.2f}/week)", True)
                    for e in [name_e, amount_e, category_e, date_e]:
                        e.delete(0, "end")
                else:
                    status_lbl(status, msg, False)
            except ValueError as e:
                status_lbl(status, str(e), False)

        action_btn(inner, "Add Expense", submit)

    # ── Delete Job ───────────────────────────────────────────────────────
    def _delete_job(self):
        """Remove the job with the given name from state and database."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Delete a Job", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        name_e = labeled_entry(inner, "Job Name to Delete")
        status = tk.Frame(inner, bg=theme.BG)
        status.pack(anchor="w")

        list_frame = tk.Frame(inner, bg=theme.BG)
        list_frame.pack(fill="x")

        def refresh_list():
            for w in list_frame.winfo_children():
                w.destroy()
            if state.jobs:
                tk.Label(list_frame, text="Current Jobs", font=F_H2,
                         fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(16, 6))
                c = _card_here(list_frame)
                for job in state.jobs:
                    tk.Label(c,
                             text=f"  {job.name}  —  ${job.amount:.2f}/{job.frequency}"
                                  f"  (≈ ${job.weekly_income():.2f}/wk)",
                             font=F_BODY, fg=theme.TEXT, bg=theme.SIDEBAR,
                             pady=6).pack(anchor="w", padx=8)
            else:
                tk.Label(list_frame, text="No jobs on file.",
                         font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=10)

        def submit():
            for w in status.winfo_children():
                w.destroy()
            name = name_e.get().strip()
            if not name:
                status_lbl(status, "Enter a job name.", False)
                return
            ok, msg = state.delete_job(name)
            status_lbl(status, msg, ok)
            if ok:
                name_e.delete(0, "end")
                refresh_list()

        action_btn(inner, "Delete Job", submit, color=theme.DANGER)
        refresh_list()

    # ── Delete Expense ────────────────────────────────────────────────────
    def _delete_expense(self):
        """Remove the expense with the given name from state and database."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Delete an Expense", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        name_e = labeled_entry(inner, "Expense Name to Delete")
        status = tk.Frame(inner, bg=theme.BG)
        status.pack(anchor="w")

        list_frame = tk.Frame(inner, bg=theme.BG)
        list_frame.pack(fill="x")

        def refresh_list():
            for w in list_frame.winfo_children():
                w.destroy()
            if state.expenses:
                tk.Label(list_frame, text="Current Expenses", font=F_H2,
                         fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(16, 6))
                c = _card_here(list_frame)
                for exp in state.expenses:
                    tk.Label(c,
                             text=f"  {exp.name}  —  ${exp.amount:.2f}/{exp.frequency}"
                                  f"  ({exp.category})  ≈ ${exp.weekly_amount():.2f}/wk",
                             font=F_BODY, fg=theme.TEXT, bg=theme.SIDEBAR,
                             pady=6).pack(anchor="w", padx=8)
            else:
                tk.Label(list_frame, text="No expenses on file.",
                         font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=10)

        def submit():
            for w in status.winfo_children():
                w.destroy()
            name = name_e.get().strip()
            if not name:
                status_lbl(status, "Enter an expense name.", False)
                return
            ok, msg = state.delete_expense(name)
            status_lbl(status, msg, ok)
            if ok:
                name_e.delete(0, "end")
                refresh_list()

        action_btn(inner, "Delete Expense", submit, color=theme.DANGER)
        refresh_list()

    # ── Set Balance ───────────────────────────────────────────────────────
    def _set_balance(self):
        """Render the Set Balance tab — input field to update current balance."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Set Your Current Balance", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 4))
        tk.Label(inner, text=f"Balance on file:  ${state.current_balance():,.2f}",
                 font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(0, 10))

        bal_e  = labeled_entry(inner, "New Balance ($)", width=18)
        status = tk.Frame(inner, bg=theme.BG)
        status.pack(anchor="w")

        def save():
            for w in status.winfo_children():
                w.destroy()
            try:
                val = _pf(bal_e, "Balance")
                ok, msg = state.set_balance(val)
                status_lbl(status, msg, ok)
                if ok:
                    bal_e.delete(0, "end")
            except ValueError as e:
                status_lbl(status, str(e), False)

        action_btn(inner, "Save Balance", save)

    # ── Import CSV ────────────────────────────────────────────────────────
    def _import_csv(self):
        """Render the Import CSV tab — file picker for bulk data import."""
        state = self._app.state
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        tk.Label(inner, text="Import CSV", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(anchor="w", pady=(0, 8))
        tk.Label(inner,
                 text="Import jobs or expenses from a CSV file.\n\n"
                      "Jobs CSV columns:  name, amount, frequency\n"
                      "Expenses CSV columns:  name, amount, category, date, frequency\n\n"
                      "frequency must be one of: Daily, Weekly, Biweekly, Monthly\n"
                      "A header row is required. Rows that fail validation are skipped.",
                 font=F_SMALL, fg=theme.MUTED, bg=theme.BG, justify="left",
                 ).pack(anchor="w", pady=(0, 14))

        result = tk.Frame(inner, bg=theme.BG)
        result.pack(anchor="w", fill="x")

        def pick_and_import(import_type):
            path = filedialog.askopenfilename(
                title=f"Select {import_type.title()} CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not path:
                return
            for w in result.winfo_children():
                w.destroy()
            imported, skipped, errors = 0, 0, []
            try:
                with open(path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader, 2):
                        try:
                            if import_type == "jobs":
                                j = Job(
                                    name=row["name"].strip(),
                                    amount=float(row["amount"]),
                                    frequency=row.get("frequency", "Weekly").strip()
                                )
                                ok, msg = state.add_job(j)
                            else:
                                e = Expense(
                                    name=row["name"].strip(),
                                    amount=float(row["amount"]),
                                    category=row.get("category", "Other").strip(),
                                    date=row.get("date", "").strip(),
                                    frequency=row.get("frequency", "Monthly").strip()
                                )
                                ok, msg = state.add_expense(e)
                            if ok:
                                imported += 1
                            else:
                                skipped += 1
                                errors.append(f"Row {i}: {msg}")
                        except (KeyError, ValueError) as ex:
                            skipped += 1
                            errors.append(f"Row {i}: {ex}")
            except Exception as ex:
                status_lbl(result, f"Could not read file: {ex}", False)
                return

            c = _card_here(result, pady=8)
            kv_row(c, "Imported", str(imported), theme.ACCENT)
            kv_row(c, "Skipped",  str(skipped),  theme.DANGER if skipped else theme.TEXT)
            if errors:
                tk.Label(c, text="\n".join(errors[:10]),
                         font=("Courier New", 9), fg=theme.DANGER, bg=theme.BG,
                         justify="left", wraplength=600).pack(anchor="w", padx=14, pady=(4, 8))
            activity_log.log(f"CSV Import ({import_type}): {imported} imported, {skipped} skipped")

        row_btns = tk.Frame(inner, bg=theme.BG)
        row_btns.pack(anchor="w", pady=(0, 10))
        for lbl, itype in [("Import Jobs CSV", "jobs"), ("Import Expenses CSV", "expenses")]:
            tk.Button(
                row_btns, text=lbl, command=lambda t=itype: pick_and_import(t),
                bg=theme.ACCENT, fg="white", font=("Inter", 11, "bold"),
                relief="flat", padx=18, pady=8,
                activebackground=theme.ACCENT, activeforeground="white", cursor="hand2"
            ).pack(side="left", padx=(0, 12), pady=(12, 4))

    # ── Activity Log ──────────────────────────────────────────────────────
    def _activity_log(self):
        """Render the Activity Log tab — recent changes with timestamps."""
        sf    = ScrollFrame(self._body)
        sf.pack(fill="both", expand=True)
        inner = sf.inner
        inner.configure(padx=36, pady=20)

        hdr = tk.Frame(inner, bg=theme.BG)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="Activity Log", font=F_H2,
                 fg=theme.TEXT, bg=theme.BG).pack(side="left")
        tk.Button(hdr, text="Clear Log", font=F_SMALL, fg=theme.DANGER, bg=theme.BG,
                  relief="flat", cursor="hand2",
                  command=lambda: [activity_log.clear(),
                                   self._render_tab("log")]).pack(side="right")

        log_search_var = tk.StringVar()
        log_search_row = tk.Frame(inner, bg=theme.BG)
        log_search_row.pack(anchor="w", fill="x", pady=(0, 8))
        tk.Label(log_search_row, text="Filter:", font=F_SMALL,
                 fg=theme.MUTED, bg=theme.BG).pack(side="left")
        tk.Entry(log_search_row, textvariable=log_search_var, font=F_BODY, width=32,
                 bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT,
                 highlightbackground=theme.BORDER, highlightthickness=1,
                 relief="flat").pack(side="left", padx=8)

        log_frame   = tk.Frame(inner, bg=theme.BG)
        log_frame.pack(fill="x")
        all_entries = activity_log.recent(200)

        def refresh_log(*_):
            for w in log_frame.winfo_children():
                w.destroy()
            q = log_search_var.get().strip().lower()
            matches = [e for e in all_entries if q in e.lower()] if q else all_entries
            if matches:
                c = _card_here(log_frame)
                for entry in matches[:100]:
                    tk.Label(c, text=entry, font=("Courier New", 10),
                             fg=theme.TEXT, bg=theme.SIDEBAR, anchor="w",
                             padx=14, pady=4).pack(fill="x")
                if len(matches) > 100:
                    tk.Label(log_frame,
                             text=f"Showing 100 of {len(matches)} matches.",
                             font=F_SMALL, fg=theme.MUTED, bg=theme.BG).pack(anchor="w", pady=(4, 0))
            else:
                tk.Label(log_frame,
                         text=("No activity recorded yet."
                               if not all_entries else "No entries match your filter."),
                         font=F_BODY, fg=theme.MUTED, bg=theme.BG).pack(anchor="w")

        log_search_var.trace_add("write", refresh_log)
        refresh_log()


# ── Private helpers (used only within this module) ────────────────────────────
def _pf(entry, name) -> float:
    """Parse float from Entry."""
    raw = entry.get().strip()
    if not raw:
        raise ValueError(f"{name} cannot be empty.")
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name}: please enter a valid number (e.g. 12.50).")


def _card_here(parent, pady=6) -> tk.Frame:
    """Inline card helper (avoids importing widgets.card which uses theme at definition)."""
    outer = tk.Frame(parent, bg=theme.SIDEBAR,
                     highlightbackground=theme.BORDER, highlightthickness=1)
    outer.pack(fill="x", pady=pady)
    return outer
