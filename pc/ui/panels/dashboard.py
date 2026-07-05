from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from ..stat_card import StatCard

RISK_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f59e0b",
    "MEDIUM": "#22d3ee",
    "LOW": "#475569",
}

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

class DashboardPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._setup_ui()
        self._connect_signals()
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

    def _refresh(self):
        self.api_client.fetch_dashboard()
        self.api_client.fetch_breaking_events()
        self.api_client.fetch_osint(limit=10)
        self.api_client.fetch_darkweb(limit=10)
        from utils import audit
        self._update_audit(audit.get_latest_logs(15))

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
