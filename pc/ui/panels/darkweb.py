from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QPushButton, QComboBox, QTextEdit, QGroupBox,
                             QFrame, QGridLayout)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from ..stat_card import StatCard

THREAT_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f59e0b",
    "MEDIUM": "#4f8cff",
    "LOW": "#64748b",
}

CATEGORY_TAGS = {
    "MALWARE": "#ef4444",
    "BOTNET_C2": "#f59e0b",
    "RANSOMWARE": "#dc2626",
    "THREAT_INTEL": "#4f8cff",
    "EXPOSED_INFRA": "#34d399",
}

class DarkWebPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._setup_ui()
        self._connect_signals()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Dark Web Intelligence")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        cards = QHBoxLayout()
        self.total_card = StatCard("Total Intel", "—", "#ef4444")
        self.critical_card = StatCard("Critical", "—", "#ef4444")
        self.today_card = StatCard("Last 24h", "—", "#f59e0b")
        cards.addWidget(self.total_card)
        cards.addWidget(self.critical_card)
        cards.addWidget(self.today_card)
        layout.addLayout(cards)

        filters = QHBoxLayout()
        self.category_filter = QComboBox()
        self.category_filter.addItems(["All Categories", "MALWARE", "BOTNET_C2", "RANSOMWARE", "THREAT_INTEL", "EXPOSED_INFRA"])
        self.threat_filter = QComboBox()
        self.threat_filter.addItems(["All Threats", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        self.refresh_btn = QPushButton("Refresh")
        filters.addWidget(QLabel("Category:"))
        filters.addWidget(self.category_filter)
        filters.addWidget(QLabel("Threat Level:"))
        filters.addWidget(self.threat_filter)
        filters.addStretch()
        filters.addWidget(self.refresh_btn)
        layout.addLayout(filters)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Source", "Title", "Category", "Threat Level", "Tags", "Discovered"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)

    def _connect_signals(self):
        self.api_client.darkwebDataReady.connect(self._on_data)
        self.refresh_btn.clicked.connect(self._refresh)
        self.category_filter.currentIndexChanged.connect(self._refresh)
        self.threat_filter.currentIndexChanged.connect(self._refresh)

    def _refresh(self):
        cat = self.category_filter.currentText()
        threat = self.threat_filter.currentText()
        self.api_client.fetch_darkweb(
            category=None if cat == "All Categories" else cat,
            threat_level=None if threat == "All Threats" else threat,
        )
        self.api_client._get("/api/darkweb/stats", "darkweb_stats")

    def _on_data(self, data):
        items = data.get("items", data) if isinstance(data, dict) else data
        if isinstance(data, dict) and "total" in data:
            self.total_card.set_value(data.get("total", 0))
            self.critical_card.set_value(data.get("critical", 0))
            self.today_card.set_value(data.get("today", 0))
            return

        self.table.setRowCount(0)
        if not items:
            return
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            tags = ", ".join(item.get("tags", [])[:3]) if isinstance(item.get("tags"), list) else ""
            threat = item.get("threat_level", "")
            threat_item = QTableWidgetItem(threat)
            threat_item.setForeground(QColor(THREAT_COLORS.get(threat, "#64748b")))

            cat = item.get("category", "")
            cat_item = QTableWidgetItem(cat)
            cat_item.setForeground(QColor(CATEGORY_TAGS.get(cat, "#94a3b8")))

            items_row = [
                QTableWidgetItem(item.get("source", "")),
                QTableWidgetItem(item.get("title", "")[:80]),
                cat_item,
                threat_item,
                QTableWidgetItem(tags),
                QTableWidgetItem(item.get("discovered_at", "")[:16]),
            ]
            for col, it in enumerate(items_row):
                self.table.setItem(row, col, it)
