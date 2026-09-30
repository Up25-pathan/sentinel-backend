"""
SENTINEL CIC — Command Deck (UI-ONLY PREVIEW)
=============================================
Jarvis-style command surface. This panel is intentionally UI-only:
it renders a fully animated threat-intelligence dashboard from static
demo data so we can shape the visual design before wiring the
Assistant Core / live data sources in the next phase.

No network calls, no server dependency, no matplotlib.
All visualisations are custom QPainter widgets.
"""
import math
import random
from collections import deque
from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QObject, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSplitter,
)

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

# ─── Mock data (replaces live sources until Assistant Core lands) ────
MOCK_KPIS = [
    ("EVENTS TRACKED",       "1,284", "+38", GREEN,  "last 24h"),
    ("ACTIVE THREATS",       "47",    "+6",  RED,    "3 CRITICAL"),
    ("RISK INDEX",           "72",    "+4",  AMBER,  "ELEVATED"),
    ("DARK WEB SIGNALS",     "112",   "+19", PURPLE, "new IOCs"),
    ("AI BRIEFINGS",         "9",     "+2",  CYAN,   "today"),
    ("UNCONFIRMED REPORTS",  "23",    "-11", BLUE,   "pending"),
]

MOCK_CRISES = [
    ("WAR",        "Eastern front: artillery activity doubles near occupied corridor", "CRITICAL"),
    ("SANCTIONS",  "Treasury expands export controls across three target entities",     "HIGH"),
    ("NUCLEAR",    "Inspectors report irregular traffic at enrichment site",            "CRITICAL"),
    ("CYBER",      "Unexplained spike in OT network scans against energy grid",         "HIGH"),
    ("DIPLOMACY",  "Summit postponed amid visa disputes",                                "MEDIUM"),
    ("OSINT",      "Mobilisation chatter increases on monitored channels",              "HIGH"),
    ("ECONOMIC",   "Rouble-denominated energy contracts gain share",                    "MEDIUM"),
    ("AVIATION",   "Rerouted carriers around closed airspace segment",                  "LOW"),
]

MOCK_SECTORS = [("DEFENSE", 38, RED), ("ENERGY", 22, AMBER), ("CYBER", 24, CYAN), ("DIPLO", 10, PURPLE), ("OTHER", 6, BLUE)]

ORCHESTRATOR = [("SENSE", "ingestion / feeds", 98), ("THINK", "reasoning core", 84),
                ("REMEMBER", "long-term memory", 61), ("ACT", "safe executors", 42), ("SPEAK", "voice layer", 0)]

MOCK_TICKER = (
    " >> LIVE OVERVIEW :: 47 ACTIVE THREATS     3 CRITICAL      RISK INDEX 72 (ELEVATED)      "
    "DARK WEB: 112 SIGNALS / 19 NEW IOCs     AI: 9 BRIEFINGS TODAY      EASTERN FRONT: ESCALATING      "
    "INSPECTORS FLAG IRREGULAR TRAFFIC AT ENRICHMENT SITE      CYBER: OT SCANS AGAINST ENERGY GRID "
)


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


# ─── KPI card with inline sparkline ───────────────────────────────────
class KpiCard(QWidget):
    def __init__(self, title, value, delta, color, sub):
        super().__init__()
        self.title = title
        self.value = value
        self.delta = delta
        self.color = QColor(color)
        self.sub = sub
        r = random.Random(hash(title) & 0xffff)
        self.spark = [10 + r.randint(-6, 6) + i * 0.8 for i in range(28)]
        self.setMinimumHeight(96)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)
        # accent top line
        p.setPen(QPen(self.color, 2))
        p.drawLine(0, 0, 34, 0)

        # sparkline
        sw, sh = w - 24, 30
        if len(self.spark) > 1:
            sx = QPainterPath()
            lo, hi = min(self.spark), max(self.spark)
            rng = (hi - lo) or 1
            for idx, v in enumerate(self.spark):
                x = 12 + idx * (sw / (len(self.spark) - 1))
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

        # texts
        p.setFont(QFont("Consolas", 7, QFont.Weight.DemiBold))
        p.setPen(QColor(DIM))
        p.drawText(QRectF(12, 8, w - 24, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)
        p.setFont(QFont("Consolas", 20, QFont.Weight.Bold))
        p.setPen(self.color)
        p.drawText(QRectF(12, h - 62, w * 0.55, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.value)
        p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        p.setPen(GREEN if self.delta.startswith("+") else RED)
        p.drawText(QRectF(w * 0.52, h - 60, w * 0.42, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.delta)
        p.setFont(QFont("Consolas", 7))
        p.setPen(QColor(FAINT))
        p.drawText(QRectF(w * 0.52, h - 42, w * 0.42, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.sub)
        p.end()


# ─── Animated threat pulse chart ──────────────────────────────────────
class _AnimationGroup(QObject):
    """One timer driving every animation on the dashboard.

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


class ThreatPulse(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(160)
        self.buf = deque([30 + (i % 9) * 4 for i in range(90)], maxlen=100)
        self.t = 0.0

    def _tick(self):
        self.t += 0.23
        base = 46 + math.sin(self.t * 0.9) * 10
        noise = math.sin(self.t * 4.7) * 6 + math.sin(self.t * 9.1) * 3
        spike = random.uniform(0, 1) < 0.04
        v = base + noise + (random.uniform(18, 34) if spike else random.uniform(-4, 4))
        self.buf.append(max(4, min(100, v)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        plot = QRectF(46, 12, w - 58, h - 40)
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)

        # grid
        gpen = PULSE_GRID_PEN
        label_font = PULSE_SMALL_FONT
        label_color = GAUGE_TICK_COLOR
        for i in range(5):
            y = plot.top() + plot.height() * i / 4
            p.setPen(gpen)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(label_color)
            p.setFont(label_font)
            p.drawText(QRectF(2, y - 8, 40, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{100 - i * 25}")

        data = list(self.buf)
        path = QPainterPath()
        n = len(data)
        for i, v in enumerate(data):
            x = plot.left() + i * (plot.width() / max(n - 1, 1))
            y = plot.bottom() - (v / 100) * plot.height()
            (path.moveTo(x, y) if i == 0 else path.lineTo(x, y))

        # gradient fill
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

        # dashed critical threshold
        cy = plot.bottom() - 0.75 * plot.height()
        p.setPen(QPen(QColor(239, 68, 68, 120), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(plot.left(), cy), QPointF(plot.right(), cy))
        p.setFont(QFont("Consolas", 6))
        p.setPen(QColor(FAINT))
        p.drawText(QRectF(plot.right() - 70, cy - 12, 66, 12), Qt.AlignmentFlag.AlignRight, "75  THREAT CEILING")

        # live line + end dot
        p.setPen(QPen(CYAN, 1.8))
        p.drawPath(path)
        last = path.pointAtPercent(1.0)
        p.setBrush(CYAN)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(last, 3, 3)

        # axis labels
        p.setFont(QFont("Consolas", 6))
        p.setPen(QColor(FAINT))
        p.drawText(QRectF(plot.left(), h - 20, 90, 12), f"NOW -14d  (T+{int(self.t) * 14 // 90}H)")
        p.drawText(QRectF(plot.right() - 90, 4, 86, 12), Qt.AlignmentFlag.AlignRight, "THREAT PULSE // SIMULATED")
        p.end()


# ─── Semicircular risk gauge ──────────────────────────────────────────
class RiskGauge(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(220, 150)
        self.level = 0.27
        self.target = 0.27

    def _tick(self):
        self.target = 0.5 + math.sin(datetime.now().timestamp() / 9) * 0.23 + random.uniform(-0.03, 0.03)
        self.target = max(0.08, min(0.96, self.target))
        self.level += (self.target - self.level) * 0.12
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(34, 22, w - 68, (w - 68) * 0.92)

        # colored arc segments
        bands = GAUGE_BANDS
        for a0, a1, col, pen in bands:
            start = 180 * (1 - a0)
            span = -180 * (a1 - a0)
            p.setPen(pen)
            p.drawArc(rect, int(start * 16), int(span * 16))

        # border ring
        p.setPen(QPen(BORDER, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(rect, int(0 * 16), int(-180 * 16))

        # ticks
        p.setFont(GAUGE_SMALL_FONT)
        cx, cy = rect.center().x(), rect.bottom()
        r = rect.width() / 2
        # Both pens are constant across the loop and across every frame; they
        # were previously rebuilt 22 times per paint.
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
            p.drawText(QRectF(x1 - 12, y1 - 24, 24, 14), Qt.AlignmentFlag.AlignCenter, str(i * 10))

        # needle
        ang = math.pi * (1 - self.level)
        n_len = r - 30
        nx = cx + n_len * math.cos(ang)
        ny = cy - n_len * math.sin(ang)
        color = QColor("#ef4444") if self.level > 0.68 else QColor("#f59e0b") if self.level > 0.4 else QColor("#22d3ee")
        p.setPen(QPen(color, 3))
        p.drawLine(QPointF(cx, cy - 4), QPointF(nx, ny))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(cx, cy - 4), 7, 7)

        # label
        p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        p.setPen(QColor(DIM))
        p.drawText(QRectF(0, cy - r + 8, w, 16), Qt.AlignmentFlag.AlignCenter, "GEOPOLITICAL RISK INDEX")
        p.setFont(QFont("Consolas", 20, QFont.Weight.Bold))
        p.setPen(color)
        p.drawText(QRectF(0, cy - r + 26, w, 26), Qt.AlignmentFlag.AlignCenter, f"{int(self.level * 100)}")
        p.end()


# ─── Donut chart ──────────────────────────────────────────────────────
class DonutChart(QWidget):
    def __init__(self, data):
        super().__init__()
        self.setMinimumSize(200, 170)
        self.data = data

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        total = sum(d[1] for d in self.data) or 1
        rect = QRectF(20, 26, min(w, h) - 90, min(w, h) - 90)
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)

        start = 90 * 16
        for name, val, col in self.data:
            span = -360 * 16 * (val / total)
            p.setPen(QPen(col, 12))
            p.drawArc(rect, int(start), int(span))
            start += span

        # center
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL2)
        p.drawEllipse(rect.adjusted(16, 16, -16, -16))

        # legend right
        lx = rect.right() + 26
        ly = rect.top() + 10
        p.setFont(QFont("Consolas", 7))
        for name, val, col in self.data:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRect(int(lx), int(ly), 8, 8)
            p.setPen(QColor(TXT))
            p.drawText(QRectF(lx + 12, ly - 3, 120, 14), f"{name}  {val}%")
            ly += 22

        p.setFont(QFont("Consolas", 7, QFont.Weight.DemiBold))
        p.setPen(QColor(DIM))
        p.drawText(QRectF(0, h - 18, w, 14), Qt.AlignmentFlag.AlignCenter, "SECTOR DISTRIBUTION")
        p.end()


# ─── Orchestrator status rows ─────────────────────────────────────────
class OrchestratorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(150)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(BORDER, 1))
        p.setBrush(PANEL)
        p.drawRect(0, 0, w - 1, h - 1)

        p.setFont(QFont("Consolas", 7, QFont.Weight.DemiBold))
        p.setPen(QColor("#22d3ee"))
        p.drawText(QRectF(10, 8, w - 20, 16), "ORCHESTRATOR // ASSISTANT CORE")

        rows = [(name, desc, v) for name, desc, v in ORCHESTRATOR]
        y = 32
        row_h = (h - 40) / len(rows)
        for name, desc, v in rows:
            p.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            p.setPen(QColor(TXT))
            p.drawText(QRectF(12, y + (row_h - 14) / 2, 64, 14), name)
            p.setFont(QFont("Consolas", 6))
            p.setPen(QColor(FAINT))
            p.drawText(QRectF(80, y + (row_h - 14) / 2, 100, 14), desc)
            # bar
            bw = w - 210
            bx = w - 14 - bw
            by = y + (row_h - 8) / 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#151a26"))
            p.drawRect(int(bx), int(by), int(bw), 8)
            col = GREEN if v >= 80 else AMBER if v >= 50 else CYAN
            grad = QLinearGradient(bx, 0, bx + bw, 0)
            grad.setColorAt(0, col)
            grad.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 120))
            p.setBrush(grad)
            p.drawRect(int(bx), int(by), int(bw * v / 100), 8)
            p.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            p.setPen(col)
            p.drawText(QRectF(bx + bw + 8, y + (row_h - 14) / 2, 34, 14), f"{v}%")
            y += row_h
        p.end()


# ─── Scrolling ticker ─────────────────────────────────────────────────
class Ticker(QWidget):
    def __init__(self, text):
        super().__init__()
        self.full = text
        self.offset = 0
        self.setFixedHeight(34)

    def _tick(self):
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

        segment = 40
        total = w - tag_w + len(self.full) * 14
        char_font = TICKER_FONT
        pen_space = TICKER_PEN_SPACE
        pen_char = TICKER_PEN_CHAR
        char_rect_h = h
        for i, ch in enumerate(self.full):
            x = tag_w + self.offset + i * 14
            if x < tag_w: x += total
            if x > w: continue
            p.setFont(char_font)
            p.setPen(pen_space if ch == " " else pen_char)
            p.drawText(QRectF(x, 0, 14, char_rect_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, ch)
        p.end()


# ─── Crisis tracker row ───────────────────────────────────────────────
def _risk_color(lvl):
    return RED if lvl == "CRITICAL" else AMBER if lvl == "HIGH" else CYAN


# ═══════════════════════════════════════════════════════════════════════
#  Dashboard Panel
# ═══════════════════════════════════════════════════════════════════════
class DashboardPanel(QWidget):
    """SENTINEL Command Deck — UI-only preview. Constructor kept identical
    (api_client) so redlab_ui.py needs no change. All data is static demo
    data pending the Assistant Core integration."""

    def __init__(self, api_client=None):
        super().__init__()
        self.setObjectName("DashboardPreview")
        self._setup_ui()
        # Intervals are set here but nothing runs until showEvent. A QTimer is
        # not a widget, so hiding this panel in the QStackedWidget never paused
        # these; the dashboard used to burn ~70 GUI-thread wakeups a second from
        # the moment the app launched, even while the user was on another tab.
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._update_clock()
        self._tick_index = 0
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(6000)
        self._status_timer.timeout.connect(self._advance_status)
        self._animations = _AnimationGroup(parent=self)
        self._animations.add(self._pulse._tick)
        self._animations.add(self._gauge._tick)
        self._animations.add(self._ticker._tick)

    def showEvent(self, event):
        super().showEvent(event)
        self._animations.start()
        self._clock_timer.start()
        self._status_timer.start()
        self._update_clock()

    def hideEvent(self, event):
        self._animations.stop()
        self._clock_timer.stop()
        self._status_timer.stop()
        super().hideEvent(event)

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
        for cat, head, lvl in MOCK_CRISES:
            self._crises_box.addWidget(self._crisis_row(cat, head, lvl))
        self._crises_box.addStretch()
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
        donut_panel.body.addWidget(DonutChart(MOCK_SECTORS))
        rl.addWidget(donut_panel, 4)

        orch_panel = Panel("")
        orch_panel.body.addWidget(OrchestratorWidget())
        rl.addWidget(orch_panel, 3)

        dock.addWidget(right)
        dock.setSizes([1180, 520])
        root.addWidget(dock, 1)

        ticker_row = QHBoxLayout()
        ticker_row.setSpacing(8)
        self._ticker = Ticker(MOCK_TICKER)
        ticker_row.addWidget(self._ticker, 1)
        badge = QLabel("UI PREVIEW — SIMULATED DATA")
        badge.setStyleSheet(
            "background:#1a1e2e; color:#f59e0b; font-size:7pt; letter-spacing:1px; padding:0 10px;")
        badge.setFixedHeight(34)
        ticker_row.addWidget(badge)
        root.addLayout(ticker_row)

    # ── Status band ──────────────────────────────────────────────
    def _build_status_band(self):
        band = QWidget()
        band.setStyleSheet("background:" + PANEL2.name() + "; border:1px solid " + BORDER.name() + ";")
        band.setFixedHeight(64)
        l = QHBoxLayout(band)
        l.setContentsMargins(16, 6, 16, 6)
        l.setSpacing(14)

        brand = QLabel("SENTINEL // COMMAND DECK")
        brand.setStyleSheet(
            "font-size:17pt; font-weight:800; color:#f59e0b; letter-spacing:4px;")
        l.addWidget(brand)

        self.core_lbl = QLabel("●  NOVA CORE  ·  ONLINE")
        self.core_lbl.setStyleSheet(
            "color:#22d3ee; font-size:9pt; font-weight:700; letter-spacing:2px;")
        l.addWidget(self.core_lbl)

        l.addStretch()

        posture = QFrame()
        post_l = QHBoxLayout(posture)
        post_l.setContentsMargins(10, 4, 10, 4)
        post_l.setSpacing(6)
        self.posture_badge = QLabel("THREAT POSTURE      ELEVATED")
        self.posture_badge.setStyleSheet(
            "background:#78350f; color:#fbbf24; font-size:9pt; font-weight:800; letter-spacing:2px; padding:0 10px;")
        post_l.addWidget(self.posture_badge)
        l.addWidget(posture)

        surfaces = QLabel("PC ●  MOBILE ●  WEB ●")
        surfaces.setStyleSheet("color:#475569; font-size:7pt; letter-spacing:1px;")
        l.addWidget(surfaces)

        self.clock_lbl = QLabel("")
        self.clock_lbl.setStyleSheet("color:#22d3ee; font-size:10pt; font-weight:700; letter-spacing:1px;")
        l.addWidget(self.clock_lbl)

        ver = QLabel("v3.0  PREVIEW")
        ver.setStyleSheet("color:#334155; font-size:7pt; letter-spacing:1px;")
        l.addWidget(ver)
        return band

    def _update_clock(self):
        now = datetime.now(timezone.utc)
        self.clock_lbl.setText(now.strftime("%H:%M:%S UTC"))
        # ambient posture drift for demo
        vals = ["ELEVATED", "ELEVATED", "ELEVATED", "HEIGHTENED", "ELEVATED"]
        v = vals[int(now.timestamp() / 30) % len(vals)]
        self.posture_badge.setText(f"THREAT POSTURE      {v}")

    # ── KPI row ──────────────────────────────────────────────────
    def _build_kpis(self):
        row = QHBoxLayout()
        row.setSpacing(8)
        for title, val, delta, color, sub in MOCK_KPIS:
            card = KpiCard(title, val, delta, color.name(), sub)
            row.addWidget(card)
        return row

    # ── Crisis row widget ────────────────────────────────────────
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

    # ── Status message rotation (simulated assistant chatter) ────
    def _advance_status(self):
        self._tick_index += 1
        msgs = [
            "SCANNING 1,284 EVENTS · 47 THREATS · 112 DARK WEB SIGNALS",
            "DETECTED OSCILLATION IN EASTERN FRONT ESCALATION CURVE",
            "QUANTUM OF NEW SANCTIONS ENTITIES NEEDS DISAMBIGUATION",
            "PREPARING DAILY GEOPOLITICAL BRIEFING · 06:00 / 18:00 UTC",
            "DARK WEB: 19 NEW IOCS → CROSS-REFERENCING EVENT CLUSTER",
            "MONITORING 8 CRISIS TRACKS · CEILING BREACH RISK AT +6%",
        ]
        self.core_lbl.setText(f"●  NOVA CORE · {msgs[self._tick_index % len(msgs)]}")

    def refresh(self):
        """Kept for compatibility with redlab_ui.py navigation."""
        pass