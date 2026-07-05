from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QPushButton)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from utils import audit

COLOR_MAP = {
    "JOB_START": "#4f8cff",
    "CAMPAIGN_CREATE": "#34d399",
    "CAMPAIGN_UPDATE": "#34d399",
    "CAMPAIGN_DELETE": "#ef4444",
    "DOCKER_START": "#f59e0b",
    "DOCKER_STOP": "#ef4444",
    "VM_START": "#f59e0b",
    "VM_STOP": "#ef4444",
    "VM_RESET": "#f59e0b",
    "GUI_START": "#64748b",
}

class AuditLogPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Audit Log")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #64748b; font-size: 9pt;")
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Action", "Details"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

    def _refresh(self):
        logs = audit.get_latest_logs(100)
        self.table.setRowCount(len(logs))
        for row, (timestamp, action, details) in enumerate(logs):
            color = QColor(COLOR_MAP.get(action, "#94a3b8"))
            items = [
                QTableWidgetItem(timestamp),
                QTableWidgetItem(action),
                QTableWidgetItem(details),
            ]
            for item in items:
                item.setForeground(color)
                self.table.setItem(row, 0, items[0])
                self.table.setItem(row, 1, items[1])
                self.table.setItem(row, 2, items[2])
        self.table.scrollToBottom()
        self.status_label.setText(f"{len(logs)} entries")
