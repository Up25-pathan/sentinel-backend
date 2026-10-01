"""
SENTINEL CIC — Command Deck
===========================
Live threat-intelligence dashboard.

This panel used to be an explicitly labelled "UI-ONLY PREVIEW": it held six
hardcoded KPI cards, eight invented crisis headlines, a hardcoded sector
breakdown, a hardcoded ticker string, five hardcoded orchestrator rows
(SENSE/THINK/REMEMBER/ACT/SPEAK at 98/84/61/42/0), and two animated widgets that
manufactured their own values — ThreatPulse summed sines plus `random.uniform`
and RiskGauge drifted on a sine wave. None of it came from the server, and
/api/intelligence/dashboard already existed and was never called.

Everything here is now derived from live endpoints:
    /api/intelligence/dashboard  overview counts, risk trend, top threats,
                                 category distribution, vulnerability stats
    /api/health                  real per-source ingestion health

Where the server has no data the widget says so instead of inventing a value.
All visualisations are custom QPainter widgets; no matplotlib.
"""
import json
import math
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlencode

from PyQt6.QtCore import Qt, QObject, QTimer, QRectF, QPointF, QUrl
from PyQt6.QtGui import (QColor, QFont, QPainter, QPainterPath, QPen, QBrush,
                         QLinearGradient)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSplitter,
    QSizePolicy, QSpacerItem,
)

from utils.api_client import SERVER_URL

# ─── Palette ──────────────────────────────────────────────────────────
BG       = QColor("#080a0e")
PANEL    = QColor("#0c0e14")
PANEL2   = QColor("#0a0c12")
BORDER    = QColor("#1a1e2e")
TXT      = "#c8d6e0"
DIM      = "#475569"
FAINT    = "#334155"

AMBER    = QColor("#f59e0b")
CYAN     = QColor("#22d3ee")
RED      = QColor("#ef4444")
GREEN    = QColor("#10b981")
PURPLE   = QColor("#a78bfa")
BLUE     = QColor("#4f8cff")

# ─── Hot-path paint objects ───────────────────────────────────────────
# These are rebuilt on every frame inside paintEvent, at up to 30 fps. Each one
# was parsed from a string on every paint: the Ticker alone allocated roughly
# 120 QFont + 240 QColor + 120 QRectF per frame, about 5,000 QFont a second,
# and RiskGauge rebuilt 22 QPen/QColor from the same constant per frame.
# Qt wants them created once and reused.
TICKER_FONT      = QFont("Consolas", 8)
TICKER_PEN_SPACE = QColor("#94a3b8")
TICKER_PEN_CHAR  = QColor("#475569")
GAUGE_TICK_PEN   = QPen(QColor(FAINT), 1)
GAUGE_TICK_COLOR = QColor(FAINT)
GAUGE_SMALL_FONT = QFont("Consolas", 6)
PULSE_SMALL_FONT = QFont("Consolas", 6)
PULSE_GRID_PEN   = QPen(QColor("#151a26"), 1)

# Gauge risk bands: colour plus the pen actually used to draw it.
GAUGE_BANDS = [
    (0.00, 0.40, QColor(34, 211, 238, 70), QPen(QColor(34, 211, 238, 70), 16)),
    (0.40, 0.68, QColor(245, 158, 11, 70), QPen(QColor(245, 158, 11, 70), 16)),
    (0.68, 1.00, QColor(239, 68, 68, 90), QPen(QColor(239, 68, 68, 90), 16)),
]

# Posture thresholds, applied to the server's global_risk_score (0-100).
# None means the server sent no score - rendered as an explicit unknown state
# rather than being rounded down to LOW, which would fabricate calm.
POSTURE_BANDS = [
    (75, "SEVERE", "#7f1d1d", "#fecaca"),
    (50, "ELEVATED", "#78350f", "#fbbf24"),
    (25, "GUARDED", "#1e3a5f", "#7dd3fc"),
    (0, "LOW", "#14532d", "#86efac"),
]
POSTURE_UNKNOWN = ("NO DATA", "#27272a", "#a1a1aa")

# Category colours for the distribution donut. Unknown categories fall back to
# a neutral blue rather than being dropped.
CATEGORY_COLORS = {
    "WAR": RED, "MILITARY_MOVEMENT": RED, "NUCLEAR_THREAT": RED,
    "TERRORISM": RED, "CYBER_ATTACK": PURPLE, "SANCTIONS": AMBER,
    "DIPLOMATIC_ESCALATION": AMBER, "COUP": AMBER,
    "POLITICAL_INSTABILITY": AMBER, "HUMANITARIAN": CYAN, "OTHER": BLUE,
}

REFRESH_MS = 60_000


def posture_for(score):
    if score is None:
        return POSTURE_UNKNOWN
    for threshold, name, bg, fg in POSTURE_BANDS:
        if score >= threshold:
            return name, bg, fg
    return POSTURE_UNKNOWN


# ─── Utility: painted panel frame ─────────────────────────────────────
class Panel(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("HUDFrame")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        if title:
            bar = QWidget()
            bar.setFixedHeight(26)
            bl = QHBoxLayout(bar)
            bl.setContentsMargins(10, 0, 10, 0)
            lbl = QLabel(title)
            lbl.setStyleSheet("font-size:8pt; font-weight:700; color:#22d3ee; letter-spacing:2px;")
            bl.addWidget(lbl)
            bl.addStretch()
            outer.addWidget(bar)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(10, 8, 10, 10)
        self.body.setSpacing(6)
        outer.addLayout(self.body, 1)


def dim_label(text, size=7, color=DIM, letter="1px"):
    l = QLabel(text)
    l.setStyleSheet(f"font-size:{size}pt; color:{color}; letter-spacing:{letter};")
    return l


def fmt_count(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "—"


# ─── KPI card with inline sparkline ───────────────────────────────────
class KpiCard(QWidget):
    """`series` is a real per-day list from the server's risk_trend. When it is
    absent the card draws no sparkline rather than generating a random one."""

    def __init__(self, title, value, delta, color, sub, series=None):
        super().__init__()
        self.title = title
        self.value = value
        self.delta = delta
        self.color = QColor(color)
        self.sub = sub
        self.series = list(series) if series else []
        self.setMinimumHeight(96)

    def update_values(self, value, delta, sub, series=None):
        self.value = value
        self.delta = delta
        self.sub = sub
        if series is not None:
            self.series = list(series)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)
        p.setPen(QPen(self.color, 2))
        p.drawLine(0, 0, 34, 0)

        sw, sh = w - 24, 30
        if len(self.series) > 1:
            sx = QPainterPath()
            lo, hi = min(self.series), max(self.series)
            rng = (hi - lo) or 1
            for idx, v in enumerate(self.series):
                x = 12 + idx * (sw / (len(self.series) - 1))
                y = h - 16 - ((v - lo) / rng) * sh
                (sx.moveTo(x, y) if idx == 0 else sx.lineTo(x, y))
            grad = QLinearGradient(0, h - 46, 0, h - 12)
            c = QColor(self.color)
            grad.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 90))
            grad.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
            p.setBrush(QBrush(grad))
            fill = QPainterPath(sx)
            fill.lineTo(w - 12, h - 12)
            fill.lineTo(12, h - 12)
            fill.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(fill)
            p.setPen(QPen(self.color, 1.4))
            p.drawPath(sx)
        elif not self.series:
            p.setPen(QPen(QColor("#151a26"), 1))
            p.setFont(QFont("Consolas", 6))
            p.drawText(QRectF(12, h - 34, w - 24, 12),
                       Qt.AlignmentFlag.AlignRight, "NO HISTORY")

        p.setFont(QFont("Consolas", 7, QFont.Weight.DemiBold))
        p.setPen(QColor(DIM))
        p.drawText(QRectF(12, 8, w - 24, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)
        p.setFont(QFont("Consolas", 20, QFont.Weight.Bold))
        p.setPen(self.color)
        p.drawText(QRectF(12, h - 62, w * 0.55, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.value)

        # A delta is only drawn when the server actually supplied a trend to
        # compute it from. Previously every card showed a hardcoded "+38".
        if self.delta:
            rising = self.delta.startswith("+")
            p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            p.setPen(GREEN if rising else RED)
            p.drawText(QRectF(w * 0.52, h - 60, w * 0.42, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.delta)

        p.setFont(QFont("Consolas", 7))
        p.setPen(QColor(FAINT))
        p.drawText(QRectF(w * 0.52, h - 42, w * 0.42, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.sub)
        p.end()


# ─── Shared animation driver ──────────────────────────────────────────
class _AnimationGroup(QObject):
    """One timer driving the panel's animation.

    ThreatPulse (90ms), RiskGauge (60ms) and Ticker (24ms) each owned a timer,
    which together woke the GUI thread about 69 times a second. They are now
    driven from a single 33ms tick, and the group is stopped whenever the
    panel is hidden: Qt does not pause a QTimer because its parent widget was
    hidden by the QStackedWidget, so those animations previously ran for the
    whole life of the process no matter which tab was on screen.
    """

    def __init__(self, parent=None, interval=33):
        super().__init__(parent)
        self._callbacks = []
        self._timer = QTimer(self)
        self._timer.setInterval(interval)
        self._timer.timeout.connect(self._tick)

    def add(self, callback):
        self._callbacks.append(callback)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        for callback in self._callbacks:
            callback()


# ─── Threat pulse, plotted from the server's daily risk trend ─────────
class ThreatPulse(QWidget):
    """Plots real per-day event volumes. The chart holds still when the data
    does — it no longer fabricates a value on every frame."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(160)
        self.series = []
        self.labels = []
        self.empty_text = "NO TREND DATA"

    def set_series(self, series, labels):
        self.series = list(series or [])
        self.labels = list(labels or [])
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        plot = QRectF(46, 12, w - 58, h - 40)
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)

        peak = max(self.series) if self.series else 100
        top = max(peak, 1)

        gpen = PULSE_GRID_PEN
        for i in range(5):
            y = plot.top() + plot.height() * i / 4
            p.setPen(gpen)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(GAUGE_TICK_COLOR)
            p.setFont(PULSE_SMALL_FONT)
            p.drawText(QRectF(2, y - 8, 40, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{int(top * (1 - i / 4))}")

        if not self.series:
            p.setFont(QFont("Consolas", 7))
            p.setPen(QColor(FAINT))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, self.empty_text)
            p.end()
            return

        path = QPainterPath()
        n = len(self.series)
        for i, v in enumerate(self.series):
            x = plot.left() + i * (plot.width() / max(n - 1, 1))
            y = plot.bottom() - (v / top) * plot.height()
            (path.moveTo(x, y) if i == 0 else path.lineTo(x, y))

        grad = QLinearGradient(0, plot.top(), 0, plot.bottom())
        grad.setColorAt(0, QColor(34, 211, 238, 70))
        grad.setColorAt(1, QColor(34, 211, 238, 0))
        fill = QPainterPath(path)
        fill.lineTo(plot.right(), plot.bottom())
        fill.lineTo(plot.left(), plot.bottom())
        fill.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill)

        p.setPen(QPen(CYAN, 1.8))
        p.drawPath(path)
        last = path.pointAtPercent(1.0)
        p.setBrush(CYAN)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(last, 3, 3)

        p.setFont(QFont("Consolas", 6))
        p.setPen(QColor(FAINT))
        span = f"{self.labels[0]} → {self.labels[-1]}" if self.labels else f"{n} DAYS"
        p.drawText(QRectF(plot.left(), h - 20, 200, 12), span)
        p.drawText(QRectF(plot.right() - 150, 4, 146, 12),
                   Qt.AlignmentFlag.AlignRight, f"EVENTS/DAY  ·  PEAK {top}")
        p.end()


# ─── Semicircular risk gauge ──────────────────────────────────────────
class RiskGauge(QWidget):
    """Needle eases toward the server's global_risk_score. The easing is
    presentation only; the value it converges on is always the real one."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(220, 150)
        self.level = 0.0
        self.target = 0.0
        self.has_data = False

    def set_level(self, value):
        """value is the server's global_risk_score, 0-100. None clears the gauge."""
        if value is None:
            self.has_data = False
            self.level = 0.0
            self.target = 0.0
            self.update()
            return
        try:
            v = float(value)
        except (TypeError, ValueError):
            self.set_level(None)
            return
        self.has_data = True
        self.target = max(0.0, min(1.0, v / 100.0))
        self.update()

    def _tick(self):
        if not self.has_data:
            return
        if abs(self.target - self.level) < 0.0005:
            self.level = self.target
            return
        self.level += (self.target - self.level) * 0.12
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(34, 22, w - 68, (w - 68) * 0.92)

        for a0, a1, _col, pen in GAUGE_BANDS:
            start = 180 * (1 - a0)
            span = -180 * (a1 - a0)
            p.setPen(pen)
            p.drawArc(rect, int(start * 16), int(span * 16))

        p.setPen(QPen(BORDER, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(rect, 0, int(-180 * 16))

        p.setFont(GAUGE_SMALL_FONT)
        cx, cy = rect.center().x(), rect.bottom()
        r = rect.width() / 2
        tick_pen = GAUGE_TICK_PEN
        tick_color = GAUGE_TICK_COLOR
        for i in range(11):
            ang = math.pi * (1 - i / 10)
            x1 = cx + (r - 22) * math.cos(ang)
            y1 = cy - (r - 22) * math.sin(ang)
            x2 = cx + (r - 15) * math.cos(ang)
            y2 = cy - (r - 15) * math.sin(ang)
            p.setPen(tick_pen)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            p.setPen(tick_color)
            p.drawText(QRectF(x1 - 12, y1 - 24, 24, 14),
                       Qt.AlignmentFlag.AlignCenter, str(i * 10))

        color = QColor("#ef4444") if self.level > 0.68 else QColor("#f59e0b") if self.level > 0.4 else QColor("#22d3ee")
        if self.has_data:
            # A parked needle at zero would read as "all clear" when in fact the
            # server sent no score, so the needle is only drawn with real data.
            ang = math.pi * (1 - self.level)
            n_len = r - 30
            nx = cx + n_len * math.cos(ang)
            ny = cy - n_len * math.sin(ang)
            p.setPen(QPen(color, 3))
            p.drawLine(QPointF(cx, cy - 4), QPointF(nx, ny))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(QPointF(cx, cy - 4), 7, 7)

        p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        p.setPen(QColor(DIM))
        p.drawText(QRectF(0, cy - r + 8, w, 16), Qt.AlignmentFlag.AlignCenter, "GEOPOLITICAL RISK INDEX")
        p.setFont(QFont("Consolas", 20, QFont.Weight.Bold))
        if self.has_data:
            p.setPen(color)
            p.drawText(QRectF(0, cy - r + 26, w, 26), Qt.AlignmentFlag.AlignCenter, f"{int(self.level * 100)}")
        else:
            p.setPen(QColor(FAINT))
            p.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            p.drawText(QRectF(0, cy - r + 26, w, 26), Qt.AlignmentFlag.AlignCenter, "NO DATA")
        p.end()


# ─── Donut chart ──────────────────────────────────────────────────────
class DonutChart(QWidget):
    """`data` is [(label, value, QColor)] from category_distribution."""

    def __init__(self, data=None, empty_text="NO CATEGORISED EVENTS"):
        super().__init__()
        self.setMinimumSize(200, 170)
        self.data = list(data or [])
        self.empty_text = empty_text

    def set_data(self, data, empty_text=None):
        self.data = list(data or [])
        if empty_text:
            self.empty_text = empty_text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)

        total = sum(d[1] for d in self.data) or 0
        if not self.data or not total:
            p.setFont(QFont("Consolas", 7))
            p.setPen(QColor(FAINT))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self.empty_text)
            p.end()
            return

        rect = QRectF(20, 26, min(w, h) - 90, min(w, h) - 90)
        start = 90 * 16
        for name, val, col in self.data:
            span = -360 * 16 * (val / total)
            p.setPen(QPen(col, 12))
            p.drawArc(rect, int(start), int(span))
            start += span

        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL2)
        p.drawEllipse(rect.adjusted(16, 16, -16, -16))

        lx = rect.right() + 26
        ly = rect.top() + 10
        p.setFont(QFont("Consolas", 7))
        for name, val, col in self.data:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRect(int(lx), int(ly), 8, 8)
            p.setPen(QColor(TXT))
            pct = 100.0 * val / total
            p.drawText(QRectF(lx + 12, ly - 3, 130, 14), f"{name}  {pct:.0f}%")
            ly += 22

        p.setFont(QFont("Consolas", 7, QFont.Weight.DemiBold))
        p.setPen(QColor(DIM))
        p.drawText(QRectF(0, h - 18, w, 14), Qt.AlignmentFlag.AlignCenter, "CATEGORY DISTRIBUTION")
        p.end()


# ─── Live ingestion health, from /api/health ──────────────────────────
STATUS_BAR = {
    "online": (100, GREEN, "ONLINE"),
    "degraded": (50, AMBER, "DEGRADED"),
    "down": (0, RED, "DOWN"),
    "unconfigured": (0, "#64748b", "NO KEY"),
    "unknown": (0, "#64748b", "NEVER RAN"),
}


class OrchestratorWidget(QWidget):
    """Replaces the five hardcoded SENSE/THINK/REMEMBER/ACT/SPEAK rows, which
    were fixed at 98/84/61/42/0 and never changed. These rows are the real
    per-source health reported by /api/health."""

    MAX_ROWS = 7

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(150)
        self.rows = []
        self.summary = ""

    def set_rows(self, rows, summary=""):
        self.rows = list(rows or [])[:self.MAX_ROWS]
        self.summary = summary
        self.setMinimumHeight(34 + max(1, len(self.rows)) * 20)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)

        p.setFont(QFont("Consolas", 7, QFont.Weight.DemiBold))
        p.setPen(QColor("#22d3ee"))
        p.drawText(QRectF(10, 8, w - 20, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "INGESTION HEALTH  ·  LIVE")

        if not self.rows:
            p.setFont(QFont("Consolas", 7))
            p.setPen(QColor(FAINT))
            p.drawText(QRectF(0, 26, w, h - 26), Qt.AlignmentFlag.AlignCenter,
                       "NO SOURCE HEALTH REPORTED" if self.summary else "HEALTH UNAVAILABLE")
            p.end()
            return

        rows = self.rows
        y = 32
        row_h = min(20.0, (h - 42) / len(rows))
        for name, status, items in rows:
            bar, col, label = STATUS_BAR.get(status, STATUS_BAR["unknown"])
            p.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            p.setPen(QColor(TXT))
            p.drawText(QRectF(12, y, 96, row_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

            bw = w - 220
            bx = w - 108 - bw
            by = y + (row_h - 7) / 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#151a26"))
            p.drawRect(int(bx), int(by), int(bw), 7)
            if bar > 0:
                p.setBrush(col)
                p.drawRect(int(bx), int(by), max(2, int(bw * bar / 100)), 7)

            p.setFont(QFont("Consolas", 6, QFont.Weight.Bold))
            p.setPen(col)
            p.drawText(QRectF(bx + bw + 6, y, 54, row_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(QColor(FAINT))
            p.setFont(QFont("Consolas", 6))
            p.drawText(QRectF(w - 50, y, 46, row_h),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{items:,}" if items else "—")
            y += row_h

        if self.summary:
            p.setFont(QFont("Consolas", 6))
            p.setPen(QColor(DIM))
            p.drawText(QRectF(12, h - 14, w - 24, 12), self.summary)
        p.end()


# ─── Scrolling ticker ─────────────────────────────────────────────────
class Ticker(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self.full = text or "NO DATA"
        self.offset = 0
        self.setFixedHeight(34)

    def set_text(self, text):
        new = text or "NO DATA"
        if new != self.full:
            self.full = new
            self.offset = 0
            self.update()

    def _tick(self):
        if not self.full:
            return
        self.offset -= 2
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)
        tag_w = 110
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(AMBER)
        p.drawRect(0, 0, tag_w, h)
        p.setFont(QFont("Consolas", 7, QFont.Weight.DemiBold))
        p.setPen(QColor("#0c0e14"))
        p.drawText(QRectF(0, 0, tag_w, h), Qt.AlignmentFlag.AlignCenter, "SYSTEM FEED")

        total = w - tag_w + len(self.full) * 14
        char_rect_h = h
        for i, ch in enumerate(self.full):
            x = tag_w + self.offset + i * 14
            if x < tag_w:
                x += total
            if x > w:
                continue
            p.setFont(TICKER_FONT)
            p.setPen(TICKER_PEN_SPACE if ch == " " else TICKER_PEN_CHAR)
            p.drawText(QRectF(x, 0, 14, char_rect_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, ch)
        p.end()


# ─── Crisis tracker row ───────────────────────────────────────────────
def _risk_color(lvl):
    return RED if lvl == "CRITICAL" else AMBER if lvl == "HIGH" else CYAN


def _shorten(text, limit=96):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


# ═══════════════════════════════════════════════════════════════════════
#  Dashboard Panel
# ═══════════════════════════════════════════════════════════════════════
class DashboardPanel(QWidget):
    """SENTINEL Command Deck. Constructor keeps the (api_client) signature so
    cic_ui.py needs no change; every figure comes from the server."""

    # (key, title, colour, sub) — `delta_key` is the risk_trend field used for
    # the 24h delta, and is None where the server exposes no per-day series.
    CARDS = [
        ("total_events", "EVENTS TRACKED", CYAN, "total", "all time"),
        ("active_threats", "ACTIVE THREATS", RED, "critical+high", "critical + high"),
        ("dark_web_signals", "DARK WEB SIGNALS", PURPLE, None, "stored"),
        ("kev_count", "EXPLOITED IN THE WILD", AMBER, None, "CISA KEV"),
        ("unread_alerts", "UNREAD ALERTS", BLUE, None, "awaiting review"),
        ("briefings_today", "BRIEFINGS TODAY", GREEN, None, "auto-generated"),
    ]

    def __init__(self, api_client=None):
        super().__init__()
        self.setObjectName("DashboardPanel")
        self.api_client = api_client
        self._overview = None
        self._dashboard = None
        self._health = None
        self._error = None
        self._last_update = None
        self._tick_index = 0
        self._status_lines = []

        self._setup_ui()

        # Intervals are set here but nothing runs until showEvent. A QTimer is
        # not a widget, so hiding this panel in the QStackedWidget never paused
        # these; the dashboard used to burn ~70 GUI-thread wakeups a second from
        # the moment the app launched, even while the user was on another tab.
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._update_clock()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(REFRESH_MS)
        self._refresh_timer.timeout.connect(self._load)

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(6000)
        self._status_timer.timeout.connect(self._advance_status)

        self._animations = _AnimationGroup(parent=self)
        self._animations.add(self._gauge._tick)
        self._animations.add(self._ticker._tick)

        self._nam = QNetworkAccessManager(self)
        self._nam.finished.connect(self._on_reply)

    # ── lifecycle ─────────────────────────────────────────────────────
    def showEvent(self, event):
        super().showEvent(event)
        self._clock_timer.start()
        self._status_timer.start()
        self._animations.start()
        # Re-poll on every visit so the deck is never showing stale counts.
        self._load()
        self._refresh_timer.start()

    def hideEvent(self, event):
        self._animations.stop()
        self._refresh_timer.stop()
        self._status_timer.stop()
        self._clock_timer.stop()
        super().hideEvent(event)

    # ── UI construction ───────────────────────────────────────────────
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        root.addWidget(self._build_status_band())
        root.addLayout(self._build_kpis())

        dock = QSplitter(Qt.Orientation.Horizontal)
        dock.setHandleWidth(1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)

        pulse_panel = Panel("LIVE THREAT PULSE")
        self._pulse = ThreatPulse()
        pulse_panel.body.addWidget(self._pulse)
        ll.addWidget(pulse_panel, 3)

        crises_panel = Panel("CRISIS TRACKER")
        self._crises_box = QVBoxLayout()
        self._crises_box.setSpacing(5)
        self._crises_widgets = []
        self._crises_stretch = None
        self._crises_placeholder = dim_label("NO CRITICAL OR HIGH EVENTS", size=8, color=FAINT)
        self._crises_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._crises_placeholder.setWordWrap(True)
        self._crises_box.addWidget(self._crises_placeholder)
        crises_panel.body.addLayout(self._crises_box)
        ll.addWidget(crises_panel, 2)

        dock.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        gauge_panel = Panel("RISK METER")
        self._gauge = RiskGauge()
        gauge_panel.body.addWidget(self._gauge)
        rl.addWidget(gauge_panel, 3)

        donut_panel = Panel("")
        self._donut = DonutChart()
        donut_panel.body.addWidget(self._donut)
        rl.addWidget(donut_panel, 4)

        orch_panel = Panel("")
        self._orchestrator = OrchestratorWidget()
        orch_panel.body.addWidget(self._orchestrator)
        rl.addWidget(orch_panel, 3)

        dock.addWidget(right)
        dock.setSizes([1180, 520])
        root.addWidget(dock, 1)

        ticker_row = QHBoxLayout()
        ticker_row.setSpacing(8)
        self._ticker = Ticker()
        ticker_row.addWidget(self._ticker, 1)
        self.badge = QLabel("CONNECTING…")
        self.badge.setStyleSheet(
            "background:#1a1e2e; color:#64748b; font-size:7pt; letter-spacing:1px; padding:0 10px;")
        self.badge.setFixedHeight(34)
        ticker_row.addWidget(self.badge)
        root.addLayout(ticker_row)

    def _build_status_band(self):
        band = QWidget()
        band.setStyleSheet("background:" + PANEL2.name() + "; border:1px solid " + BORDER.name() + ";")
        band.setFixedHeight(64)
        l = QHBoxLayout(band)
        l.setContentsMargins(16, 6, 16, 6)
        l.setSpacing(14)

        brand = QLabel("SENTINEL // COMMAND DECK")
        brand.setStyleSheet("font-size:17pt; font-weight:800; color:#f59e0b; letter-spacing:4px;")
        l.addWidget(brand)

        self.core_lbl = QLabel("●  CONNECTING TO SENTINEL CORE…")
        self.core_lbl.setStyleSheet("color:#64748b; font-size:9pt; font-weight:700; letter-spacing:2px;")
        l.addWidget(self.core_lbl)

        l.addStretch()

        posture = QFrame()
        post_l = QHBoxLayout(posture)
        post_l.setContentsMargins(10, 4, 10, 4)
        post_l.setSpacing(6)
        self.posture_badge = QLabel("THREAT POSTURE      UNKNOWN")
        self.posture_badge.setStyleSheet(
            "background:#1a1e2e; color:#475569; font-size:9pt; font-weight:800; letter-spacing:2px; padding:0 10px;")
        post_l.addWidget(self.posture_badge)
        l.addWidget(posture)

        self.clock_lbl = QLabel("")
        self.clock_lbl.setStyleSheet("color:#22d3ee; font-size:10pt; font-weight:700; letter-spacing:1px;")
        l.addWidget(self.clock_lbl)

        self.freshness = QLabel("")
        self.freshness.setStyleSheet("color:#334155; font-size:7pt; letter-spacing:1px;")
        l.addWidget(self.freshness)
        return band

    def _update_clock(self):
        now = datetime.now(timezone.utc)
        self.clock_lbl.setText(now.strftime("%H:%M:%S UTC"))
        if self._last_update:
            age = int((now - self._last_update).total_seconds())
            self.freshness.setText(f"UPDATED {age}s AGO" if age < 3600
                                   else f"UPDATED {age // 3600}h AGO")

    def _build_kpis(self):
        row = QHBoxLayout()
        row.setSpacing(8)
        self._cards = {}
        for key, title, color, _delta, sub in self.CARDS:
            card = KpiCard(title, "—", "", color.name(), sub, series=None)
            self._cards[key] = card
            row.addWidget(card)
        return row

    def _crisis_row(self, cat, head, lvl):
        w = QWidget()
        w.setStyleSheet("background:" + PANEL.name() + "; border:1px solid " + BORDER.name() + ";")
        l = QHBoxLayout(w)
        l.setContentsMargins(10, 6, 10, 6)
        l.setSpacing(10)

        cat_lbl = QLabel(cat)
        cat_lbl.setFixedWidth(86)
        cat_lbl.setStyleSheet("color:#22d3ee; font-size:7pt; font-weight:700; letter-spacing:1px;")
        l.addWidget(cat_lbl)

        head_lbl = QLabel(head)
        head_lbl.setStyleSheet("color:#c8d6e0; font-size:8pt;")
        head_lbl.setWordWrap(True)
        head_lbl.setToolTip(head)
        l.addWidget(head_lbl, 1)

        lvl_lbl = QLabel(lvl)
        lvl_lbl.setFixedWidth(64)
        c = _risk_color(lvl)
        lvl_lbl.setStyleSheet(
            f"background:{c.name()}; color:#080a0e; font-size:7pt; font-weight:800;"
            "letter-spacing:1px; padding:2px 0; border-radius:2px;")
        lvl_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(lvl_lbl)
        return w

    def _set_crises(self, threats):
        for w in self._crises_widgets:
            w.setParent(None)
            w.deleteLater()
        self._crises_widgets = []
        # Idempotent: the bottom stretch is re-created each refresh, never stacked.
        if self._crises_stretch is not None:
            self._crises_box.removeItem(self._crises_stretch)
            self._crises_stretch = None

        if not threats:
            self._crises_placeholder.setText("NO CRITICAL OR HIGH EVENTS")
            if self._crises_placeholder.parent() is None:
                self._crises_box.insertWidget(0, self._crises_placeholder)
            self._crises_placeholder.show()
            return

        self._crises_placeholder.setParent(None)
        for t in threats:
            cat = t.get("category") or "OTHER"
            lvl = t.get("risk_level") or "MEDIUM"
            country = t.get("country")
            title = _shorten(t.get("title") or "(untitled)")
            if country:
                title = f"{country} — {title}"
            w = self._crisis_row(cat.replace("_", " ")[:12], title, lvl)
            w.setToolTip(t.get("title") or "")
            self._crises_box.addWidget(w)
            self._crises_widgets.append(w)
        # addStretch() returns None in PyQt6, so the spacer is built explicitly
        # to keep a handle for removal - otherwise each refresh stacks another
        # stretch into the layout and the panel grows without bound.
        self._crises_stretch = QSpacerItem(
            0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        self._crises_box.addItem(self._crises_stretch)

    # ── data ──────────────────────────────────────────────────────────
    def _load(self):
        if not self.api_client:
            self._set_error("no API client")
            return
        # Polling while unauthenticated produced a 401 every cycle, which the
        # server counts against its limiter and answered with 429. Wait for a
        # token instead, then load once per login.
        if not (getattr(self.api_client, "token", None) or ""):
            self._status_label.setText("AUTH REQUIRED")
            return
        self._status_label.setText("LIVE")
        self._request(f"{SERVER_URL}/api/intelligence/dashboard", self._on_dashboard)
        self._request(f"{SERVER_URL}/api/health", self._on_health)

    def _request(self, url, handler):
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"Accept", b"application/json")
        token = getattr(self.api_client, "token", None)
        if token:
            req.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        reply = self._nam.get(req)
        reply._sentinel_handler = handler
        reply._sentinel_url = url

    def _on_reply(self, reply):
        handler = getattr(reply, "_sentinel_handler", None)
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._set_error(reply.errorString())
                return
            try:
                data = json.loads(bytes(reply.readAll().data()).decode("utf-8", errors="replace"))
            except Exception as err:  # noqa: BLE001
                self._set_error(f"malformed response ({err})")
                return
            if handler:
                handler(data)
        finally:
            reply.deleteLater()

    def _set_error(self, message):
        self._error = message
        self.badge.setText("FEED ERROR")
        self.badge.setStyleSheet(
            "background:#1a1e2e; color:#ef4444; font-size:7pt; letter-spacing:1px; padding:0 10px;")
        self.badge.setToolTip(message)
        self.core_lbl.setText("●  NOVA CORE  ·  FEED ERROR")
        self.core_lbl.setStyleSheet(
            "color:#ef4444; font-size:9pt; font-weight:700; letter-spacing:2px;")
        self._status_lines = [f"FEED ERROR: {message}"]

    def _on_dashboard(self, data):
        if not isinstance(data, dict):
            self._set_error("unexpected dashboard response")
            return
        self._dashboard = data
        overview = data.get("overview") or {}
        self._overview = overview
        vulns = data.get("vulnerabilities") or {}
        self._error = None
        self._last_update = datetime.now(timezone.utc)

        trend = data.get("risk_trend") or []
        labels = [str(t.get("date", ""))[5:] for t in trend]
        totals = [int(t.get("total") or 0) for t in trend]
        threats = [int(t.get("critical") or 0) + int(t.get("high") or 0) for t in trend]
        self._pulse.set_series(totals, labels)

        # Latest two days give a real 24h delta. Cards with no server-provided
        # series (delta_spec is None) and payloads with <2 days of data show no
        # delta at all rather than a made-up one.
        def delta_for(series):
            if not series or len(series) < 2:
                return None
            diff = series[-1] - series[-2]
            return f"{diff:+,}"

        values = {
            "total_events": overview.get("total_events"),
            "active_threats": overview.get("active_threats"),
            "dark_web_signals": overview.get("dark_web_signals"),
            "kev_count": vulns.get("kev_count"),
            "unread_alerts": overview.get("unread_alerts"),
            "briefings_today": overview.get("briefings_today"),
        }
        series_for = {"total_events": totals, "active_threats": threats}
        delta_spec = {"total_events": totals, "active_threats": threats}

        for key, title, color, _d, sub in self.CARDS:
            raw = values.get(key)
            if raw is None and key == "kev_count":
                raw = None
            text = "—" if raw is None else fmt_count(raw)
            d = delta_for(delta_spec.get(key))
            self._cards[key].update_values(text, d or "", sub, series_for.get(key))

        risk = overview.get("global_risk_score")
        if risk is not None:
            self._gauge.set_level(risk)
        else:
            # No score from the server: say so, never inherit the last known value.
            self._gauge.set_level(None)

        dist = []
        for row in (data.get("category_distribution") or [])[:8]:
            name = str(row.get("category") or "OTHER")
            dist.append((name, int(row.get("count") or 0),
                         CATEGORY_COLORS.get(name, BLUE)))
        self._donut.set_data(dist, "NO CATEGORISED EVENTS")

        self._set_crises(data.get("top_threats") or [])

        name, bg, fg = posture_for(risk) if risk is not None else posture_for(None)
        self.posture_badge.setText(f"THREAT POSTURE      {name}")
        self.posture_badge.setStyleSheet(
            f"background:{bg}; color:{fg}; font-size:9pt; font-weight:800;"
            "letter-spacing:2px; padding:0 10px;")

        self._ticker.set_text(self._compose_ticker(overview, vulns))
        self._build_status_lines(overview, vulns)
        self._advance_status()

        self.badge.setText("LIVE FEED")
        self.badge.setStyleSheet(
            "background:#1a1e2e; color:#10b981; font-size:7pt; letter-spacing:1px; padding:0 10px;")
        self.badge.setToolTip(f"Updated {self._last_update.strftime('%H:%M:%S UTC')}")
        self._update_clock()

    def _on_health(self, data):
        if not isinstance(data, dict):
            return
        self._health = data
        sources = (data.get("sources") or {}).get("sources") or []
        # Most recently successful first — that is the useful ordering.
        ordered = sorted(
            sources,
            key=lambda s: (s.get("lastSuccessAt") or ""),
            reverse=True,
        )
        rows = [(s.get("name", "?"), s.get("status", "unknown"),
                 int(s.get("lastItemCount") or 0)) for s in ordered]
        sh = data.get("sources") or {}
        summary = (f"COVERAGE {str(sh.get('coverage', '?')).upper()}"
                   f"  ·  {sh.get('healthy', 0)}/{sh.get('total', 0)} HEALTHY")
        self._orchestrator.set_rows(rows, summary)

    def _compose_ticker(self, o, v):
        parts = [
            f" >> LIVE FEED :: {fmt_count(o.get('total_events'))} EVENTS",
            f"{fmt_count(o.get('active_threats'))} ACTIVE THREATS",
            f"{fmt_count(o.get('critical_events'))} CRITICAL",
            f"RISK INDEX {o.get('global_risk_score') if o.get('global_risk_score') is not None else '—'}",
            f"LAST 24H {fmt_count(o.get('events_last_24h'))}",
            f"DARK WEB {fmt_count(o.get('dark_web_signals'))}",
            f"KEV {fmt_count(v.get('kev_count'))} EXPLOITED",
            f"ALERTS {fmt_count(o.get('unread_alerts'))}",
        ]
        return "     ".join(parts) + "     "

    def _build_status_lines(self, o, v):
        lines = [
            f"TRACKING {fmt_count(o.get('total_events'))} EVENTS  ·  {fmt_count(o.get('events_last_24h'))} IN 24H",
            f"ACTIVE THREATS {fmt_count(o.get('active_threats'))}  ·  {fmt_count(o.get('critical_events'))} CRITICAL",
            f"CISA KEV {fmt_count(v.get('kev_count'))} EXPLOITED IN THE WILD",
            f"DARK WEB {fmt_count(o.get('dark_web_signals'))} SIGNALS  ·  {fmt_count(o.get('dark_web_critical'))} CRITICAL",
            f"ENTITIES {fmt_count(o.get('total_entities'))}  ·  LINKS {fmt_count(o.get('total_nexus_links'))}",
            f"SOURCES {fmt_count(o.get('active_sources'))}  ·  ALERTS {fmt_count(o.get('unread_alerts'))} UNREAD",
        ]
        self._status_lines = lines

    def _advance_status(self):
        if not self._status_lines:
            return
        self._tick_index += 1
        line = self._status_lines[self._tick_index % len(self._status_lines)]
        self.core_lbl.setText(f"●  NOVA CORE  ·  {line}")
        self.core_lbl.setStyleSheet(
            "color:#22d3ee; font-size:9pt; font-weight:700; letter-spacing:2px;")

    def refresh(self):
        """Called by cic_ui.py navigation and after a successful login."""
        if self.isVisible():
            self._load()
