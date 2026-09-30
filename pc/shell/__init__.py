"""Shared application shell for SENTINEL.

SENTINEL CIC (intel/reporting) and SENTINEL REDLAB (offensive operations) are
separate applications that present the same way: a header with live system
state, a compact icon rail, a stacked content area and a status bar. Only the
chrome lives here, so the two apps stay visually identical without either
importing the other's panels.
"""

from .shell import ShellWindow, load_stylesheet, excepthook

__all__ = ["ShellWindow", "load_stylesheet", "excepthook"]
