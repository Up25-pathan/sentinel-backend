from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QComboBox, QPushButton, QLineEdit, QGroupBox,
                             QTextEdit, QSplitter, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from ..stat_card import StatCard

RISK_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f59e0b",
    "MEDIUM": "#4f8cff",
    "LOW": "#64748b",
}

class IntelEventsPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._current_page = 1
        self._setup_ui()
        self._connect_signals()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Intelligence Events")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.category_filter = QComboBox()
        self.category_filter.addItems(["All Categories", "WAR", "MILITARY_MOVEMENT", "SANCTIONS", "COUP", "DIPLOMATIC_ESCALATION", "NUCLEAR_THREAT", "POLITICAL_INSTABILITY", "TERRORISM", "CYBER_ATTACK", "HUMANITARIAN"])
        self.risk_filter = QComboBox()
        self.risk_filter.addItems(["All Risk Levels", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search events...")
        self.refresh_btn = QPushButton("Refresh")
        filters.addWidget(QLabel("Category:"))
        filters.addWidget(self.category_filter)
        filters.addWidget(QLabel("Risk:"))
        filters.addWidget(self.risk_filter)
        filters.addWidget(self.search_input, 1)
        filters.addWidget(self.refresh_btn)
        layout.addLayout(filters)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Title", "Category", "Risk", "Location", "Country", "Time"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self.table, 1)

        self.detail_box = QGroupBox("Event Details")
        detail_layout = QVBoxLayout(self.detail_box)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(150)
        detail_layout.addWidget(self.detail_text)
        self.detail_box.setVisible(False)
        layout.addWidget(self.detail_box)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self._prev_page)
        self.page_label = QLabel("Page 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self._next_page)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.page_label, 1)
        nav.addWidget(self.next_btn)
        layout.addLayout(nav)

    def _connect_signals(self):
        self.api_client.eventsDataReady.connect(self._on_events)
        self.refresh_btn.clicked.connect(self._refresh)
        self.category_filter.currentIndexChanged.connect(self._refresh)
        self.risk_filter.currentIndexChanged.connect(self._refresh)

    def _refresh(self):
        cat = self.category_filter.currentText()
        risk = self.risk_filter.currentText()
        self.api_client.fetch_events(
            page=self._current_page,
            category=None if cat == "All Categories" else cat,
            risk_level=None if risk == "All Risk Levels" else risk,
        )

    def _on_events(self, data):
        events = data.get("events", [])
        pagination = data.get("pagination", {})
        self.table.setRowCount(0)
        self.table.setRowCount(len(events))

        for row, ev in enumerate(events):
            items = [
                QTableWidgetItem(ev.get("title", "")),
                QTableWidgetItem(ev.get("category", "")),
                QTableWidgetItem(ev.get("risk_level", "")),
                QTableWidgetItem(ev.get("location_name", "")),
                QTableWidgetItem(ev.get("country", "")),
                QTableWidgetItem(ev.get("created_at", "")),
            ]
            risk = ev.get("risk_level", "")
            items[2].setForeground(QColor(RISK_COLORS.get(risk, "#64748b")))
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, ev.get("id", ""))
                self.table.setItem(row, col, item)

        total = pagination.get("total", 0)
        pages = pagination.get("pages", 1)
        self.page_label.setText(f"Page {self._current_page} of {pages} ({total} events)")
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < pages)

    def _on_select(self):
        rows = self.table.selectedItems()
        if not rows:
            self.detail_box.setVisible(False)
            return
        event_id = rows[0].data(Qt.ItemDataRole.UserRole)
        if event_id:
            title = self.table.item(rows[0].row(), 0).text()
            cat = self.table.item(rows[0].row(), 1).text()
            risk = self.table.item(rows[0].row(), 2).text()
            loc = self.table.item(rows[0].row(), 3).text()
            clr = RISK_COLORS.get(risk, "#fff")
            self.detail_text.setHtml(
                f"<b>ID:</b> {event_id}<br>"
                f"<b>Title:</b> {title}<br>"
                f"<b>Category:</b> {cat}<br>"
                f"<b>Risk:</b> <span style='color:{clr}'>{risk}</span><br>"
                f"<b>Location:</b> {loc}"
            )
            self.detail_box.setVisible(True)

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._refresh()

    def _next_page(self):
        self._current_page += 1
        self._refresh()
