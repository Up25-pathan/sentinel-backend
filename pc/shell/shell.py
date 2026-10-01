"""Shared PyQt6 shell: header, nav rail, content stack, status bar.

Deliberately panel-agnostic. Subclasses pass a list of (key, factory) pairs and
get the chrome around them. The two SENTINEL apps differ only in which panels
they pass, so nav, keyboard shortcuts, panel lifecycle and connection state are
implemented once.
"""

import os
import sys
import traceback
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QAction, QColor, QFontMetrics, QIcon, QKeySequence, QPixmap,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QSystemTrayIcon, QVBoxLayout,
    QWidget,
)

from utils import system_monitor


def app_root():
    """Directory the app was launched from, bundler-aware."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_stylesheet(target):
    """Apply the shared QSS to a widget. Missing styles are reported, not fatal."""
    candidates = [
        os.path.join(app_root(), "ui", "style.qss"),
        os.path.join(os.path.dirname(app_root()), "ui", "style.qss"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                target.setStyleSheet(handle.read())
            return True
    print(f"Warning: style.qss not found (looked in {candidates})")
    return False


def excepthook(exc_type, exc_value, exc_tb):
    """Log crashes to crash.log and continue running.

    Qt callbacks that raise otherwise abort the process, taking unsaved UI state
    with them. Reporting and surviving is the better failure mode here.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Ctrl+C in the user's terminal is not a crash worth recording; Qt
        # routes it through here because the hook is installed process-wide.
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(f"CRASH: {text}", flush=True)
    try:
        with open("crash.log", "a", encoding="utf-8") as handle:
            handle.write(f"\n{'=' * 60}\n{datetime.now().isoformat()}\n{text}")
    except OSError:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


# Qt adds the 3px left border outside the height declared in the stylesheet, so
# a 28px rule renders as 30px. This matches the rendered height, which is what
# the row spacing below is calculated from.
RAIL_ITEM_H = 30
# Horizontal space an item spends on: stylesheet padding (14 left + 10 right),
# button side margins (6 + 6) and the vertical scrollbar (8). Mirrors
# ui/style.qss; used only to size the rail, never to lay out an item.
RAIL_CHROME = 14 + 10 + 12 + 8
RAIL_MIN_W = 104
RAIL_MAX_W = 260


class NavRail(QWidget):
    """Text rail with grouped sections."""

    navigationChanged = pyqtSignal(str)

    def __init__(self, items, title, parent=None):
        """items: list of (key, icon, short_label, tooltip) or ("__group", None, LABEL, None)."""
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.buttons = {}
        self._items = items

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        label = QLabel(title)
        label.setObjectName("SidebarTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(label)

        # The merged app lists every panel of both halves, which is taller than
        # the window at its minimum size. Without this the lower entries were
        # simply unreachable.
        scroll = QScrollArea()
        scroll.setObjectName("RailScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        holder = QWidget()
        holder.setObjectName("RailScrollBody")
        body = QVBoxLayout(holder)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        for key, icon, short, tooltip in items:
            if key == "__group":
                separator = QLabel(short)
                separator.setObjectName("SidebarGroup")
                body.addWidget(separator)
                continue
            # The icon field is kept in the tuple for compatibility but is not
            # drawn: glyph prefixes rendered at wildly different sizes and read
            # as decoration rather than information.
            #
            # A plain QPushButton is used rather than a focus-stripping wrapper.
            # The wrapper sized its inner button from its own rect, which left
            # the button at its 100px default while the wrapper grew, so labels
            # clipped no matter how wide the rail was. Focus is removed directly.
            btn = QPushButton(short)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCheckable(True)
            btn.setFixedHeight(RAIL_ITEM_H)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip or "")
            btn.clicked.connect(lambda _checked=False, k=key: self.select(k))
            body.addWidget(btn)
            self.buttons[key] = btn

        body.addStretch()
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)
        self._scroll = scroll

        # Sized here so the rail is never left at the layout default, which is
        # several hundred pixels wide.
        self.resize_to_labels()

    def resize_to_labels(self):
        """Set the rail width from the real button metrics.

        Called once while building and again after the stylesheet has been
        polished. Font resolution changes between those points, so a single
        measurement is either taken against the app-wide default face (too
        narrow) or against the final one (correct); measuring twice converges
        instead of guessing.
        """
        if not self.buttons:
            return
        metrics = QFontMetrics(next(iter(self.buttons.values())).font())
        longest = max(
            (metrics.horizontalAdvance(b.text()) for b in self.buttons.values()),
            default=0,
        )
        width = max(RAIL_MIN_W, min(longest + RAIL_CHROME, RAIL_MAX_W))
        self.setFixedWidth(width)
        self._scroll.setFixedWidth(width)
        # widgetResizable resizes the holder to the viewport, but the holder's
        # minimum size hint comes from the group labels and kept it far wider
        # than the rail. That mismatch is what made the scroll background show
        # as a band wider than the sidebar, so the floor is cleared.
        holder = self._scroll.widget()
        holder.setMinimumWidth(0)
        holder.setFixedWidth(width)

    def showEvent(self, event):
        super().showEvent(event)
        # Second pass: by show time the stylesheet is polished and the metrics
        # are final.
        self.resize_to_labels()

    def select(self, key):
        """Highlight `key` and announce the navigation."""
        for candidate, item in self.buttons.items():
            item.setChecked(candidate == key)
        self.navigationChanged.emit(key)


class ShellWindow(QMainWindow):
    """Chrome around a set of panels. Subclasses implement build_panels()."""

    connectionChanged = pyqtSignal(bool, str)

    def __init__(self, title, version, nav_items, nav_title, subtitle="",
                 client_factory=None):
        super().__init__()
        self.setWindowTitle(f"{title} — v{version}")
        self.setGeometry(80, 40, 1800, 960)
        self.setMinimumSize(1280, 760)
        self.version = version
        self.subtitle = subtitle
        self._load_stylesheet()
        self._online = False
        self._last_status = "STANDBY"

        # Panels take the client in their constructor, so it has to exist
        # before build_panels() runs.
        self.api_client = client_factory() if client_factory else None
        self.panels = {}
        self.panel_keys = []

        self._setup_ui(nav_items, nav_title)
        self._setup_tray()
        self._setup_monitor()

    # ── chrome ──────────────────────────────────────────────────────
    def _load_stylesheet(self):
        load_stylesheet(self)

    def _setup_ui(self, nav_items, nav_title):
        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self._build_header(main)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.rail = NavRail(nav_items, nav_title)
        body.addWidget(self.rail)

        self.content = QStackedWidget()
        self.content.setObjectName("ContentArea")
        self.build_panels()
        self._polish_panels()
        body.addWidget(self.content, 1)
        main.addLayout(body, 1)

        self._build_status(main)
        self.rail.navigationChanged.connect(self._on_nav)
        self._install_shortcuts()
        if self.panel_keys:
            self._on_nav(self.panel_keys[0])

    def _polish_panels(self):
        """Apply the shared polish pass to every panel, once, at startup."""
        from .polish import polish
        self._polished = 0
        for key in self.panel_keys:
            try:
                self._polished += polish(self.panels[key])
            except Exception as exc:  # noqa: BLE001 - polish must never block boot
                print(f"Polish skipped for {key}: {exc}")

    def _build_header(self, parent):
        header = QWidget()
        header.setObjectName("HeaderBar")
        header.setFixedHeight(36)
        row = QHBoxLayout(header)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(12)

        title = QLabel(self.windowTitle().split(" — v")[0])
        title.setObjectName("HeaderTitle")
        row.addWidget(title)

        if self.subtitle:
            sub = QLabel(self.subtitle)
            sub.setStyleSheet("color: #334155; font-size: 7pt; letter-spacing: 2px;")
            row.addWidget(sub)

        self.conn_label = QLabel("● OFFLINE")
        self.conn_label.setStyleSheet(
            "color: #ef4444; font-size: 8pt; letter-spacing: 1px;")
        self.conn_label.setToolTip("Backend connection state")
        row.addWidget(self.conn_label)

        self.sse_label = QLabel("")
        self.sse_label.setStyleSheet("color: #475569; font-size: 7pt;")
        row.addWidget(self.sse_label)

        row.addStretch()

        self.cpu_bar = self._meter("#22d3ee", "CPU usage")
        self.mem_bar = self._meter("#f59e0b", "Memory usage")
        for label, bar in (("CPU", self.cpu_bar), ("MEM", self.mem_bar)):
            caption = QLabel(label)
            caption.setStyleSheet("color: #334155; font-size: 7pt;")
            row.addWidget(caption)
            row.addWidget(bar)

        self.clock_label = QLabel("")
        self.clock_label.setStyleSheet(
            "color: #475569; font-size: 8pt; letter-spacing: 1px;")
        self.clock_label.setToolTip("Local time")
        row.addWidget(self.clock_label)

        parent.addWidget(header)

        self._update_clock()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

    @staticmethod
    def _meter(color, tooltip):
        bar = QProgressBar()
        bar.setFixedWidth(80)
        bar.setToolTip(tooltip)
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 0px; }}")
        return bar

    def _build_status(self, parent):
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(24)
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(12)

        self.status_label = QLabel("STANDBY")
        self.status_label.setStyleSheet("color: #475569; font-size: 7pt; letter-spacing: 1px;")
        row.addWidget(self.status_label)
        row.addStretch()

        version = QLabel(f"v{self.version}")
        version.setStyleSheet("color: #1e293b; font-size: 7pt;")
        row.addWidget(version)
        parent.addWidget(bar)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip(self.windowTitle())
        menu = self.tray.contextMenu()
        if menu is None:
            from PyQt6.QtWidgets import QMenu
            menu = QMenu()
        menu.addAction("Show Window").triggered.connect(self.show)
        menu.addAction("Quit").triggered.connect(QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show() if reason ==
            QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.setIcon(self._tray_icon())
        self.tray.show()

    @staticmethod
    def _tray_icon():
        icon = QIcon()
        pix = QPixmap(16, 16)
        if not pix.isNull():
            pix.fill(QColor(245, 158, 11))
            return QIcon(pix)
        return icon

    def _setup_monitor(self):
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._update_stats)
        self.monitor_timer.start(3000)

    def _update_stats(self):
        try:
            self.cpu_bar.setValue(int(system_monitor.get_cpu_usage()))
            self.mem_bar.setValue(int(system_monitor.get_memory_usage()))
        except Exception:  # noqa: BLE001 - a meter is never worth an exception
            pass

    def _update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def _install_shortcuts(self):
        for index, key in enumerate(self.panel_keys, start=1):
            action = QAction(self)
            action.setShortcut(QKeySequence(f"Ctrl+{index}"))
            action.triggered.connect(lambda _=False, k=key: self._on_nav(k))
            self.addAction(action)
        refresh = QAction(self)
        refresh.setShortcut(QKeySequence("F5"))
        refresh.triggered.connect(self._on_refresh)
        self.addAction(refresh)

    # ── overridable ─────────────────────────────────────────────────
    def build_panels(self):
        raise NotImplementedError

    def on_login(self, ok, message):
        pass

    def on_startup(self):
        """Hook for the subclass: auth dialogs, SSE, first fetch."""

    # ── behaviour ───────────────────────────────────────────────────
    def _on_nav(self, key):
        if key not in self.panels:
            return
        self.content.setCurrentWidget(self.panels[key])
        self._set_status(f"SECTION: {key.upper()}")
        refresh = getattr(self.panels[key], "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except Exception as exc:  # noqa: BLE001
                # One panel failing to refresh must not break navigation.
                self._set_status(f"REFRESH FAILED: {key} — {exc}"[:90], error=True)

    def _on_refresh(self):
        if self.panel_keys:
            self._on_nav(self.panel_keys[self.content.currentIndex()])

    def _set_status(self, text, error=False):
        self._last_status = text
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {'#ef4444' if error else '#475569'}; font-size: 7pt; letter-spacing: 1px;")

    def set_connection(self, online, detail=""):
        self._online = bool(online)
        color = "#22d3ee" if online else "#ef4444"
        mark = "●" if online else "○"
        self.conn_label.setText(f"{mark} {'ONLINE' if online else 'OFFLINE'}"
                                + (f" — {detail}" if detail and not online else ""))
        self.conn_label.setStyleSheet(
            f"color: {color}; font-size: 8pt; letter-spacing: 1px;")
        self.connectionChanged.emit(self._online, detail)

    def closeEvent(self, event):
        if getattr(self, "tray", None):
            self.tray.hide()
        event.accept()
