from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QPushButton, QTextEdit, QGroupBox, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

ALERT_TYPE_COLORS = {
    "BREAKING": "#ef4444",
    "CRITICAL": "#ef4444",
    "UPDATE": "#4f8cff",
    "ESCALATION": "#f59e0b",
}

class AlertsPanel(QWidget):
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

        title = QLabel("Security Alerts")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.mark_read_btn = QPushButton("Mark Read")
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.mark_read_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Type", "Message", "Time", "Read"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self.table, 1)

        self.detail_box = QGroupBox("Alert Detail")
        detail_layout = QVBoxLayout(self.detail_box)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(100)
        detail_layout.addWidget(self.detail_text)
        self.detail_box.setVisible(False)
        layout.addWidget(self.detail_box)

    def _connect_signals(self):
        self.api_client.alertsDataReady.connect(self._on_alerts)
        self.refresh_btn.clicked.connect(self._refresh)

    def _refresh(self):
        self.api_client.fetch_alerts()

    def _on_alerts(self, alerts):
        self.table.setRowCount(0)
        self.table.setRowCount(len(alerts))
        for row, alert in enumerate(alerts):
            atype = alert.get("type", "")
            type_item = QTableWidgetItem(atype)
            type_item.setForeground(QColor(ALERT_TYPE_COLORS.get(atype, "#64748b")))
            font = QFont()
            font.setBold(atype in ("BREAKING", "CRITICAL"))
            type_item.setFont(font)

            items = [
                type_item,
                QTableWidgetItem(alert.get("message", "")),
                QTableWidgetItem(alert.get("created_at", "")[:16]),
                QTableWidgetItem("Read" if alert.get("is_read") else "Unread"),
            ]
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, alert.get("id", ""))
                self.table.setItem(row, col, item)

    def _on_select(self):
        rows = self.table.selectedItems()
        if not rows:
            self.detail_box.setVisible(False)
            return
        row = rows[0].row()
        items = [self.table.item(row, c) for c in range(4)]
        if items[1]:
            self.detail_text.setHtml(
                f"<b>Type:</b> {items[0].text() if items[0] else ''}<br>"
                f"<b>Message:</b> {items[1].text() if items[1] else ''}<br>"
                f"<b>Time:</b> {items[2].text() if items[2] else ''}"
            )
            self.detail_box.setVisible(True)
