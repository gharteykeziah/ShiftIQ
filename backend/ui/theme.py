"""
theme.py — Color palettes, fonts, live theme switching, and ThemeManager.

All pages and widgets import colors from here so there is one source of truth.
The ThemeManager lets the dark-mode toggle reconfigure widgets IN PLACE instead
of destroying and rebuilding them.
"""
import tkinter as tk

# ── Palettes ──────────────────────────────────────────────────────────────────
_LIGHT = dict(
    BG="#F0F4F1", SIDEBAR="#FFFFFF", BORDER="#D8E4DC",
    TEXT="#1A2E22", MUTED="#7A9485", ACCENT="#1B6B3A",
    ACCENT_L="#D4EDDA", DANGER="#C0392B", NAV_SEL="#E6F2EB", BLUE="#2563EB",
)
_DARK = dict(
    BG="#0F1A14", SIDEBAR="#1A2820", BORDER="#2D4A38",
    TEXT="#E8F5EC", MUTED="#7EB896", ACCENT="#3DCC7A",
    ACCENT_L="#1A3A28", DANGER="#FF6B6B", NAV_SEL="#22402E", BLUE="#60A5FA",
)

_dark_mode: bool = False

# ── Live color variables (reassigned by apply_theme) ──────────────────────────
BG       = _LIGHT["BG"]
SIDEBAR  = _LIGHT["SIDEBAR"]
BORDER   = _LIGHT["BORDER"]
TEXT     = _LIGHT["TEXT"]
MUTED    = _LIGHT["MUTED"]
ACCENT   = _LIGHT["ACCENT"]
ACCENT_L = _LIGHT["ACCENT_L"]
DANGER   = _LIGHT["DANGER"]
NAV_SEL  = _LIGHT["NAV_SEL"]
BLUE     = _LIGHT["BLUE"]

# ── Fonts (never change with theme) ───────────────────────────────────────────
F_BODY  = ("Inter", 11)
F_SMALL = ("Inter", 10)
F_H1    = ("Inter", 20, "bold")
F_H2    = ("Inter", 13, "bold")
F_NUM   = ("Inter", 26, "bold")
F_NAV   = ("Inter", 11)


# ── Helpers ───────────────────────────────────────────────────────────────────
def is_dark() -> bool:
    return _dark_mode


def apply_theme(dark: bool) -> None:
    """Reassign all palette globals to the chosen theme."""
    global _dark_mode, BG, SIDEBAR, BORDER, TEXT, MUTED, ACCENT, ACCENT_L, DANGER, NAV_SEL, BLUE
    _dark_mode = dark
    p = _DARK if dark else _LIGHT
    BG, SIDEBAR, BORDER = p["BG"], p["SIDEBAR"], p["BORDER"]
    TEXT, MUTED         = p["TEXT"], p["MUTED"]
    ACCENT, ACCENT_L    = p["ACCENT"], p["ACCENT_L"]
    DANGER, NAV_SEL     = p["DANGER"], p["NAV_SEL"]
    BLUE                = p["BLUE"]


def darken(hex_color: str, factor: float = 0.80) -> str:
    """Return a darkened version of a hex color for hover states."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


# ── ThemeManager ─────────────────────────────────────────────────────────────
class ThemeManager:
    """
    Tracks on-screen widgets and reconfigures them in place when the theme
    changes — no page teardown or rebuild required for structural widgets.

    Each widget is registered with a dict of { config_key: callable } where
    each callable returns the current theme value at the moment of calling.

    Example:
        theme_mgr.track(label, fg=lambda: theme.TEXT, bg=lambda: theme.BG)
        # Later:
        theme_mgr.refresh()   # all tracked widgets updated live
    """

    def __init__(self) -> None:
        self._entries: list = []

    def track(self, widget: tk.Widget, **roles) -> tk.Widget:
        """
        Register widget.  roles are zero-arg callables that return current
        theme values.  Returns the widget for inline use:
            lbl = theme_mgr.track(tk.Label(...), fg=lambda: theme.TEXT)
        """
        self._entries.append((widget, roles))
        return widget

    def refresh(self) -> None:
        """Reapply current theme to all live widgets; discard destroyed ones."""
        live = []
        for widget, roles in self._entries:
            try:
                if widget.winfo_exists():
                    widget.config(**{k: v() for k, v in roles.items()})
                    live.append((widget, roles))
            except tk.TclError:
                pass   # widget was destroyed — drop silently
        self._entries = live

    def clear(self) -> None:
        """Discard all registrations."""
        self._entries.clear()


# Module-level singleton — imported and used by widgets.py and pages.
theme_mgr = ThemeManager()
