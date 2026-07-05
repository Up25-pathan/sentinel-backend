from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import QUrl
from ..stat_card import StatCard
from utils.api_client import SERVER_URL
import json

RISK_COLORS = {
    "CRITICAL": "#ef4444", "HIGH": "#f59e0b",
    "MEDIUM": "#22d3ee", "LOW": "#475569",
}

try:
    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except:
    HAS_MPL = False

class HUDWidget(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("HUDFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.title = QLabel(title)
        self.title.setObjectName("FrameTitle")
        layout.addWidget(self.title)
        self.content = QVBoxLayout()
        self.content.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(self.content)

class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, figsize=(5, 2.5), dpi=80):
        self.fig = Figure(figsize=figsize, dpi=dpi)
        self.fig.patch.set_facecolor('#0a0c12')
        super().__init__(self.fig)

class DashboardPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._nam = QNetworkAccessManager(self)
        self._setup_ui()
        self._connect_signals()
        self._maybe_fetch_chart_data()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        stats = QHBoxLayout()
        stats.setSpacing(6)
        self.total_card = StatCard("Total Events", "—", "#22d3ee")
        self.critical_card = StatCard("Critical", "—", "#ef4444")
        self.breaking_card = StatCard("Breaking", "—", "#f59e0b")
        self.alerts_card = StatCard("Alerts", "—", "#ef4444")
        self.today_card = StatCard("24H", "—", "#22d3ee")
        stats.addWidget(self.total_card)
        stats.addWidget(self.critical_card)
        stats.addWidget(self.breaking_card)
        stats.addWidget(self.alerts_card)
        stats.addWidget(self.today_card)
        layout.addLayout(stats)

        mid = QSplitter(Qt.Orientation.Horizontal)
        mid.setHandleWidth(1)

        left = QWidget()
        l = QVBoxLayout(left)
        l.setContentsMargins(0, 0, 3, 0)
        l.setSpacing(0)
        self.breaking_frame = HUDWidget("BREAKING EVENTS")
        self.breaking_table = QTableWidget()
        self.breaking_table.setColumnCount(4)
        self.breaking_table.setHorizontalHeaderLabels(["Title", "Category", "Risk", "Location"])
        self.breaking_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.breaking_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.breaking_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.breaking_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.breaking_table.verticalHeader().setVisible(False)
        self.breaking_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.breaking_frame.content.addWidget(self.breaking_table)
        l.addWidget(self.breaking_frame)

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setHandleWidth(1)

        osint_frame = HUDWidget("OSINT STREAM")
        self.osint_table = QTableWidget()
        self.osint_table.setColumnCount(2)
        self.osint_table.setHorizontalHeaderLabels(["Source", "Headline"])
        self.osint_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.osint_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.osint_table.verticalHeader().setVisible(False)
        self.osint_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        osint_frame.content.addWidget(self.osint_table)
        right_split.addWidget(osint_frame)

        dw_frame = HUDWidget("DARK WEB")
        self.dw_table = QTableWidget()
        self.dw_table.setColumnCount(3)
        self.dw_table.setHorizontalHeaderLabels(["Category", "Title", "Threat"])
        self.dw_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.dw_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.dw_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.dw_table.verticalHeader().setVisible(False)
        self.dw_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        dw_frame.content.addWidget(self.dw_table)
        right_split.addWidget(dw_frame)

        mid.addWidget(left)
        mid.addWidget(right_split)
        mid.setSizes([600, 400])
        layout.addWidget(mid, 1)

        # ── Charts row ──
        if HAS_MPL:
            charts = QHBoxLayout()
            charts.setSpacing(6)
            self.trend_canvas = MplCanvas(figsize=(5, 2))
            self.cat_canvas = MplCanvas(figsize=(3.5, 2))
            charts.addWidget(self.trend_canvas, 2)
            charts.addWidget(self.cat_canvas, 1)
            layout.addLayout(charts)
        else:
            no_mpl = QLabel("Install matplotlib for trend charts: pip install matplotlib")
            no_mpl.setStyleSheet("color:#475569; font-size:7pt; padding:4px;")
            layout.addWidget(no_mpl)

        # ── Audit log ──
        bottom_frame = HUDWidget("AUDIT LOG")
        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(3)
        self.audit_table.setHorizontalHeaderLabels(["Timestamp", "Action", "Details"])
        self.audit_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.audit_table.verticalHeader().setVisible(False)
        self.audit_table.setMaximumHeight(120)
        bottom_frame.content.addWidget(self.audit_table)
        layout.addWidget(bottom_frame)

    def _connect_signals(self):
        self.api_client.dashboardDataReady.connect(self._on_dashboard)
        self.api_client.breakingEventsReady.connect(self._on_breaking)
        self.api_client.osintDataReady.connect(self._on_osint)
        self.api_client.darkwebDataReady.connect(self._on_darkweb)

    def _maybe_fetch_chart_data(self):
        if not HAS_MPL:
            return
        self._nam.finished.connect(self._on_chart_reply)
        url = QUrl(f"{SERVER_URL}/api/intelligence/trends?days=14")
        req = QNetworkRequest(url)
        if self.api_client.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.api_client.token}".encode())
        self._nam.get(req)

    def _on_chart_reply(self, reply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = json.loads(reply.readAll().data().decode())
            trends = data.get("trends", [])
            self._update_trend_chart(trends)
        reply.deleteLater()

    def _update_trend_chart(self, trends):
        if not HAS_MPL or not trends:
            return
        dates = [t.get("date", "")[-5:] for t in trends]
        criticals = [t.get("critical", 0) for t in trends]
        highs = [t.get("high", 0) for t in trends]
        mediums = [t.get("medium", 0) for t in trends]

        self.trend_canvas.fig.clear()
        ax = self.trend_canvas.fig.add_subplot(111)
        ax.set_facecolor('#0a0c12')
        ax.spines['bottom'].set_color('#1e293b')
        ax.spines['top'].set_color('#1e293b')
        ax.spines['left'].set_color('#1e293b')
        ax.spines['right'].set_color('#1e293b')
        ax.tick_params(colors='#475569', labelsize=7)
        ax.set_ylabel('Events', color='#475569', fontsize=7)

        ax.fill_between(range(len(dates)), 0, criticals, color='#ef4444', alpha=0.6, label='Critical')
        ax.fill_between(range(len(dates)), criticals, [c + h for c, h in zip(criticals, highs)], color='#f59e0b', alpha=0.6, label='High')
        ax.fill_between(range(len(dates)), [c + h for c, h in zip(criticals, highs)], [c + h + m for c, h, m in zip(criticals, highs, mediums)], color='#22d3ee', alpha=0.4, label='Medium')
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, ha='right', fontsize=6)
        ax.legend(loc='upper left', fontsize=6, facecolor='#0a0c12', edgecolor='#1e293b', labelcolor='#94a3b8')
        self.trend_canvas.fig.tight_layout()
        self.trend_canvas.draw()

        self._fetch_category_data()

    def _fetch_category_data(self):
        url = QUrl(f"{SERVER_URL}/api/intelligence/dashboard")
        req = QNetworkRequest(url)
        if self.api_client.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.api_client.token}".encode())
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_cat_data(r))

    def _on_cat_data(self, reply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = json.loads(reply.readAll().data().decode())
            cat_dist = data.get("category_distribution", [])
            self._update_cat_chart(cat_dist)
        reply.deleteLater()

    def _update_cat_chart(self, cat_dist):
        if not HAS_MPL or not cat_dist:
            return

        cat_colors = {
            "WAR": "#ef4444", "MILITARY_MOVEMENT": "#f59e0b",
            "SANCTIONS": "#a78bfa", "COUP": "#ef4444",
            "DIPLOMATIC_ESCALATION": "#f59e0b", "NUCLEAR_THREAT": "#ef4444",
            "POLITICAL_INSTABILITY": "#f59e0b", "TERRORISM": "#ef4444",
            "CYBER_ATTACK": "#22d3ee", "HUMANITARIAN": "#22d3ee",
        }

        cats = [c.get("category", "") for c in cat_dist[:8]]
        counts = [c.get("count", 0) for c in cat_dist[:8]]
        colors = [cat_colors.get(c, "#475569") for c in cats]

        self.cat_canvas.fig.clear()
        ax = self.cat_canvas.fig.add_subplot(111)
        ax.set_facecolor('#0a0c12')
        ax.spines['bottom'].set_color('#1e293b')
        ax.spines['top'].set_color('#1e293b')
        ax.spines['left'].set_color('#1e293b')
        ax.spines['right'].set_color('#1e293b')
        ax.tick_params(colors='#475569', labelsize=6)
        ax.set_xlabel('Category', color='#475569', fontsize=7)

        bars = ax.barh(range(len(cats)), counts, color=colors, height=0.6)
        ax.set_yticks(range(len(cats)))
        ax.set_yticklabels(cats, fontsize=7, color='#94a3b8')
        for bar, count in zip(bars, counts):
            ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                    str(count), va='center', fontsize=7, color='#64748b')
        self.cat_canvas.fig.tight_layout()
        self.cat_canvas.draw()

    def _refresh(self):
        self.api_client.fetch_dashboard()
        self.api_client.fetch_breaking_events()
        self.api_client.fetch_osint(limit=10)
        self.api_client.fetch_darkweb(limit=10)
        from utils import audit
        self._update_audit(audit.get_latest_logs(15))
        self._maybe_fetch_chart_data()

    def _on_dashboard(self, data):
        ov = data.get("overview", {})
        self.total_card.set_value(ov.get("total_events", "—"))
        self.critical_card.set_value(ov.get("critical_events", "—"))
        self.breaking_card.set_value(ov.get("breaking_events", "—"))
        self.alerts_card.set_value(ov.get("unread_alerts", "—"))
        self.today_card.set_value(ov.get("events_last_24h", "—"))

    def _on_breaking(self, events):
        self.breaking_table.setRowCount(0)
        self.breaking_table.setRowCount(len(events))
        for r, e in enumerate(events):
            risk = e.get("risk_level", "")
            items = [
                QTableWidgetItem(e.get("title", "")),
                QTableWidgetItem(e.get("category", "")),
                QTableWidgetItem(risk),
                QTableWidgetItem(e.get("location_name", "")),
            ]
            items[2].setForeground(QColor(RISK_COLORS.get(risk, "#64748b")))
            for c, it in enumerate(items):
                self.breaking_table.setItem(r, c, it)

    def _on_osint(self, data):
        articles = data.get("data", [])
        self.osint_table.setRowCount(0)
        self.osint_table.setRowCount(min(len(articles), 8))
        for r, a in enumerate(articles[:8]):
            src = a.get("source_name", "").replace("OSINT:", "")
            self.osint_table.setItem(r, 0, QTableWidgetItem(src))
            self.osint_table.setItem(r, 1, QTableWidgetItem(a.get("title", "")[:80]))

    def _on_darkweb(self, data):
        items = data if isinstance(data, list) else data.get("items", [])
        if isinstance(data, dict) and "total" in data:
            return
        self.dw_table.setRowCount(0)
        self.dw_table.setRowCount(min(len(items), 8))
        for r, i in enumerate(items[:8]):
            threat = i.get("threat_level", "")
            ti = QTableWidgetItem(threat)
            ti.setForeground(QColor(RISK_COLORS.get(threat, "#64748b")))
            self.dw_table.setItem(r, 0, QTableWidgetItem(i.get("category", "")))
            self.dw_table.setItem(r, 1, QTableWidgetItem(i.get("title", "")[:60]))
            self.dw_table.setItem(r, 2, ti)

    def _update_audit(self, logs):
        self.audit_table.setRowCount(len(logs))
        for r, (ts, action, details) in enumerate(logs):
            self.audit_table.setItem(r, 0, QTableWidgetItem(ts))
            self.audit_table.setItem(r, 1, QTableWidgetItem(action))
            self.audit_table.setItem(r, 2, QTableWidgetItem(details))
        self.audit_table.scrollToBottom()

    def refresh(self):
        self._refresh()
