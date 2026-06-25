"""
widgets.py — Shared UI primitives for the ShiftIQ.

Every helper registers its widgets with ThemeManager so a dark/light-mode
toggle can reconfigure them in place without destroying any pages.
"""
import sys
import tkinter as tk
from tkinter import ttk

import theme
from theme import theme_mgr, darken, F_BODY, F_SMALL, F_H1, F_H2, F_NAV


# ── Utility ───────────────────────────────────────────────────────────────────
def _T(widget: tk.Widget, **roles) -> tk.Widget:
    """Register widget with ThemeManager and return it — one-liner convenience."""
    return theme_mgr.track(widget, **roles)


# ── Input parsing ─────────────────────────────────────────────────────────────
def get_float(entry_widget: tk.Entry, field_name: str) -> float:
    raw = entry_widget.get().strip()
    if not raw:
        raise ValueError(f"{field_name} cannot be empty.")
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{field_name}: please enter a valid number (e.g. 12.50).")


def get_int(entry_widget: tk.Entry, field_name: str) -> int:
    raw = entry_widget.get().strip()
    if not raw:
        raise ValueError(f"{field_name} cannot be empty.")
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{field_name}: please enter a whole number (e.g. 4).")


# ── ScrollFrame ───────────────────────────────────────────────────────────────
class ScrollFrame(tk.Frame):
    """A vertically scrollable container. Uses theme colors at construction time."""

    _active = None  # which canvas is currently under the cursor

    def _contains(self, widget) -> bool:
        """Return True if widget is self or a descendant of self."""
        try:
            w = widget
            while w is not None:
                if w is self:
                    return True
                w = w.master
        except Exception:
            pass
        return False

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=kw.pop("bg", theme.BG))
        _T(self, bg=lambda: theme.BG)

        canvas    = tk.Canvas(self, bg=theme.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = tk.Frame(canvas, bg=theme.BG)
        _T(canvas,    bg=lambda: theme.BG)
        _T(self.inner, bg=lambda: theme.BG)

        _win = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        # Keep inner frame width in sync with the canvas so fill="x" works.
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(_win, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.inner.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # ── Scroll binding ────────────────────────────────────────────────────
        # Strategy: use a single global bind_all on the root window.
        # Track which canvas is "active" (cursor inside this ScrollFrame).
        # <Leave> checks actual pixel bounds so moving to a child widget
        # inside the frame does NOT deactivate scrolling.

        def _on_scroll(ev):
            if ScrollFrame._active is not canvas:
                return
            if sys.platform == "darwin":
                canvas.yview_scroll(-1 * ev.delta, "units")
            else:
                delta = ev.delta // 120 or (1 if ev.delta > 0 else -1)
                canvas.yview_scroll(-1 * delta, "units")

        def _enter(_ev):
            ScrollFrame._active = canvas
            # Register our handler globally (replaces any previous ScrollFrame's)
            self.bind_all("<MouseWheel>", _on_scroll)

        def _leave(ev):
            # Only deactivate if cursor truly left this frame's bounding box
            rx, ry = ev.x_root - self.winfo_rootx(), ev.y_root - self.winfo_rooty()
            if rx < 0 or ry < 0 or rx >= self.winfo_width() or ry >= self.winfo_height():
                if ScrollFrame._active is canvas:
                    ScrollFrame._active = None

        self.bind("<Enter>", _enter)
        self.bind("<Leave>", _leave)
        # Also activate when cursor enters any child widget inside the frame
        self.bind_all("<Enter>", lambda ev: _enter(ev) if self._contains(ev.widget) else None)


# ── TabBar ────────────────────────────────────────────────────────────────────
class TabBar(tk.Frame):
    """
    Underline-indicator tab bar.  Active tab gets a 3 px ACCENT underline.
    Buttons and indicators are registered with ThemeManager.
    """

    def __init__(self, parent, tabs):
        super().__init__(parent, bg=theme.BG, pady=0)
        _T(self, bg=lambda: theme.BG)

        self._line = _T(tk.Frame(parent, bg=theme.BORDER, height=1),
                        bg=lambda: theme.BORDER)

        self.pack(fill="x", padx=0, pady=(4, 0))
        self._line.pack(fill="x")

        self._btns       = {}
        self._indicators = {}
        self._on_select  = None

        for key, label in tabs:
            col = _T(tk.Frame(self, bg=theme.BG), bg=lambda: theme.BG)
            col.pack(side="left")

            b = tk.Button(
                col, text=f" {label} ", font=("Inter", 10),
                fg=theme.MUTED, bg=theme.BG, relief="flat",
                padx=8, pady=8, cursor="hand2", bd=0,
                activebackground=theme.BG, activeforeground=theme.ACCENT,
                command=lambda k=key: self._select(k)
            )
            b.pack()
            _T(b, fg=lambda btn=b: theme.ACCENT if btn.cget("fg") == theme.ACCENT else theme.MUTED,
               bg=lambda: theme.BG,
               activebackground=lambda: theme.BG,
               activeforeground=lambda: theme.ACCENT)

            ind = _T(tk.Frame(col, bg=theme.BG, height=3), bg=lambda: theme.BG)
            ind.pack(fill="x")

            self._btns[key]       = b
            self._indicators[key] = ind

    def bind_select(self, fn):
        self._on_select = fn

    def _select(self, key):
        for k, b in self._btns.items():
            if k == key:
                b.config(fg=theme.ACCENT, font=("Inter", 10, "bold"))
                self._indicators[k].config(bg=theme.ACCENT)
            else:
                b.config(fg=theme.MUTED, font=("Inter", 10))
                self._indicators[k].config(bg=theme.BG)
        if self._on_select:
            self._on_select(key)

    def activate(self, key):
        self._select(key)


# ── Shared widget helpers ─────────────────────────────────────────────────────
def page_title(parent, text, subtitle=None):
    """Renders a page heading with a small accent rule."""
    acc = _T(tk.Frame(parent, bg=theme.ACCENT, height=3, width=40),
             bg=lambda: theme.ACCENT)
    acc.pack(anchor="w", pady=(0, 6))

    lbl = _T(tk.Label(parent, text=text, font=F_H1, fg=theme.TEXT, bg=theme.BG),
             fg=lambda: theme.TEXT, bg=lambda: theme.BG)
    lbl.pack(anchor="w", pady=(0, 2))

    if subtitle:
        sub = _T(tk.Label(parent, text=subtitle, font=F_SMALL,
                          fg=theme.MUTED, bg=theme.BG),
                 fg=lambda: theme.MUTED, bg=lambda: theme.BG)
        sub.pack(anchor="w", pady=(0, 14))
    else:
        _T(tk.Frame(parent, bg=theme.BG, height=10), bg=lambda: theme.BG).pack()


def card(parent, pady=6, accent=False) -> tk.Frame:
    """
    A content card with optional green top accent bar.
    Returns the outer frame so callers can pack children into it.
    """
    outer = _T(
        tk.Frame(parent, bg=theme.SIDEBAR,
                 highlightbackground=theme.BORDER, highlightthickness=1),
        bg=lambda: theme.SIDEBAR,
        highlightbackground=lambda: theme.BORDER,
    )
    outer.pack(fill="x", pady=pady)
    if accent:
        _T(tk.Frame(outer, bg=theme.ACCENT, height=3),
           bg=lambda: theme.ACCENT).pack(fill="x")
    return outer


def kv_row(parent, key, value, v_color=None) -> None:
    """Key / value row inside a card. v_color resolves to TEXT if omitted."""
    _vc = v_color  # captured explicit color or None

    row = _T(tk.Frame(parent, bg=theme.SIDEBAR), bg=lambda: theme.SIDEBAR)
    row.pack(fill="x", padx=18, pady=6)

    key_lbl = _T(
        tk.Label(row, text=key, font=F_BODY, fg=theme.MUTED,
                 bg=theme.SIDEBAR, width=26, anchor="w"),
        fg=lambda: theme.MUTED, bg=lambda: theme.SIDEBAR,
    )
    key_lbl.pack(side="left")

    # Value color: if caller passed an explicit color, keep it; else use TEXT.
    # We store whether an explicit color was passed so refresh uses the right source.
    if _vc is None:
        val_lbl = _T(
            tk.Label(row, text=value, font=("Inter", 11, "bold"),
                     fg=theme.TEXT, bg=theme.SIDEBAR),
            fg=lambda: theme.TEXT, bg=lambda: theme.SIDEBAR,
        )
    else:
        val_lbl = _T(
            tk.Label(row, text=value, font=("Inter", 11, "bold"),
                     fg=_vc, bg=theme.SIDEBAR),
            bg=lambda: theme.SIDEBAR,   # fg stays fixed (caller intent)
        )
    val_lbl.pack(side="left")


def labeled_entry(parent, label_text, width=28) -> tk.Entry:
    """A labeled text entry with theme-tracked label."""
    lbl = _T(
        tk.Label(parent, text=label_text, font=("Inter", 10, "bold"),
                 fg=theme.TEXT, bg=theme.BG),
        fg=lambda: theme.TEXT, bg=lambda: theme.BG,
    )
    lbl.pack(anchor="w", pady=(12, 3))

    e = _T(
        tk.Entry(parent, font=F_BODY, width=width, relief="flat",
                 highlightbackground=theme.ACCENT, highlightthickness=1,
                 bg=theme.SIDEBAR, fg=theme.TEXT, insertbackground=theme.TEXT),
        bg=lambda: theme.SIDEBAR,
        fg=lambda: theme.TEXT,
        insertbackground=lambda: theme.TEXT,
        highlightbackground=lambda: theme.ACCENT,
    )
    e.pack(anchor="w", ipady=7)
    return e


def action_btn(parent, text, command, color=None) -> tk.Button:
    """
    Primary action button with hover darkening.
    color=None → uses ACCENT (live, updates with theme).
    color=explicit → fixed color (caller's intent).
    """
    use_accent = color is None
    c = theme.ACCENT if use_accent else color

    btn = tk.Button(
        parent, text=f"  {text}  ", command=command,
        bg=c, fg="white", font=("Inter", 11, "bold"),
        relief="flat", padx=4, pady=10,
        activebackground=darken(c), activeforeground="white",
        cursor="hand2", bd=0,
    )

    if use_accent:
        theme_mgr.track(btn,
                        bg=lambda: theme.ACCENT,
                        activebackground=lambda: darken(theme.ACCENT))

    btn.bind("<Enter>", lambda e, b=btn: b.config(bg=darken(b.cget("bg"))))
    btn.bind("<Leave>", lambda e, b=btn, ua=use_accent, fc=c:
             b.config(bg=theme.ACCENT if ua else fc,
                      activebackground=darken(theme.ACCENT if ua else fc)))
    btn.pack(anchor="w", pady=(12, 4))
    return btn


def status_lbl(parent, text, ok=True) -> tk.Label:
    prefix = "✓  " if ok else "✗  "
    fg     = theme.ACCENT if ok else theme.DANGER
    lbl    = _T(
        tk.Label(parent, text=prefix + text, font=("Inter", 10, "bold"),
                 fg=fg, bg=theme.BG),
        bg=lambda: theme.BG,
    )
    lbl.pack(anchor="w", pady=4)
    return lbl


def section_divider(parent) -> None:
    _T(tk.Frame(parent, bg=theme.BORDER, height=1),
       bg=lambda: theme.BORDER).pack(fill="x", pady=18)
