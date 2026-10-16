# theme.py - bảng màu (token) sáng/tối và stylesheet Qt; không phụ thuộc Qt nên kiểm thử được
"""`build_qss(name)` → stylesheet cho 'dark' | 'light'. `resolve(pref, system_dark)` → 'dark' | 'light'.
Màu nhấn (hồng) giữ nguyên ở cả hai chế độ để nhận diện thương hiệu của app."""
from __future__ import annotations

ACCENT = "#ec4899"

TOKENS = {
    "dark": {
        "bg": "#0d0f1f", "fg": "#eceef5", "panel": "#10121f", "button": "#1b1e30", "border": "rgba(255,255,255,.10)",
        "border_btn": "rgba(255,255,255,.12)", "muted": "#a3a7ba", "muted2": "#9aa0b4", "disabled": "#717690",
        "tab_sel": "#3a1830", "tab_sel_fg": "#ffffff", "toast_bg": "#1b1e30", "toast_fg": "#eceef5",
    },
    "light": {
        "bg": "#f6f7fb", "fg": "#1c1f2e", "panel": "#ffffff", "button": "#eceef6", "border": "rgba(0,0,0,.14)",
        "border_btn": "rgba(0,0,0,.18)", "muted": "#5b6075", "muted2": "#6a7088", "disabled": "#9a9fb3",
        "tab_sel": "#fde4f1", "tab_sel_fg": "#7a1148", "toast_bg": "#ffffff", "toast_fg": "#1c1f2e",
    },
}


def resolve(pref: str | None, system_dark: bool = True) -> str:
    """pref: 'auto' | 'dark' | 'light' (giá trị lạ → auto)."""
    if pref in ("dark", "light"):
        return pref
    return "dark" if system_dark else "light"


def build_qss(name: str = "dark") -> str:
    t = TOKENS.get(name, TOKENS["dark"])
    return f"""
QWidget {{ background:{t['bg']}; color:{t['fg']}; font-size:13px; }}
QGroupBox {{ border:1px solid {t['border']}; border-radius:10px; margin-top:10px; padding:10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left:10px; padding:0 4px; color:{ACCENT}; font-weight:bold; }}
QComboBox, QPlainTextEdit, QListWidget, QLineEdit {{ background:{t['panel']}; border:1px solid {t['border']};
    border-radius:7px; padding:5px; color:{t['fg']}; }}
QPushButton {{ background:{t['button']}; border:1px solid {t['border_btn']}; border-radius:7px; padding:6px 12px; }}
QPushButton:hover {{ border-color:{ACCENT}; }}
QPushButton:disabled {{ color:{t['disabled']}; }}
QPushButton:focus {{ border-color:{ACCENT}; }}
QProgressBar {{ border:1px solid {t['border']}; border-radius:6px; text-align:center; background:{t['panel']}; }}
QProgressBar::chunk {{ background:{ACCENT}; border-radius:6px; }}
QTabBar::tab {{ background:{t['panel']}; padding:8px 16px; border-top-left-radius:8px; border-top-right-radius:8px; }}
QTabBar::tab:selected {{ background:{t['tab_sel']}; color:{t['tab_sel_fg']}; }}
QCheckBox {{ spacing:6px; }}
QCheckBox::indicator {{ width:16px; height:16px; border:1px solid {t['border_btn']}; border-radius:4px; background:{t['panel']}; }}
QCheckBox::indicator:checked {{ background:{ACCENT}; border-color:{ACCENT}; }}
QScrollArea {{ background:{t['bg']}; }}
QLabel#muted {{ color:{t['muted']}; }}
QLabel#toast {{ background:{t['toast_bg']}; color:{t['toast_fg']}; border:1px solid {ACCENT}; border-radius:8px; padding:8px 14px; }}
QPushButton#primary {{ background:{ACCENT}; color:#fff; font-weight:bold; padding:9px; border-radius:8px; }}
QPushButton#primary:disabled {{ background:{t['button']}; color:{t['disabled']}; }}
QPushButton#danger {{ border-color:#ef4444; }}
"""
