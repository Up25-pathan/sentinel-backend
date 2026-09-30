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

DEFAULT_COLOR = QColor("#94a3b8")

# Built once. This ran every 5 seconds and parsed a colour string per row.
COLOR_CACHE = {action: QColor(value) for action, value in COLOR_MAP.items()}

REFRESH_MS = 5000
MAX_ROWS = 100


class AuditLogPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._last_rows = None
        self._setup_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        # Started from showEvent instead. A timer is not a widget, so Qt does not
        # stop it when its parent panel is hidden by the QStackedWidget: this
        # used to query SQLite and rebuild 100 rows every 5 seconds for the
        # entire lifetime of the process, whether or not anyone opened this tab.
        self._timer.setInterval(REFRESH_MS)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

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
        logs = audit.get_latest_logs(MAX_ROWS)
        rows = [tuple(row) for row in logs]

        # Nothing changed, so leave the table alone. Rebuilding 100 rows x 3
        # items on every tick was the cost of this panel even when idle.
        if rows == self._last_rows:
            self.status_label.setText(f"{len(rows)} entries")
            return

        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            color = None
            for column, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                if column == 1:
                    color = COLOR_CACHE.get(value, DEFAULT_COLOR)
                item.setForeground(color or DEFAULT_COLOR)
                self.table.setItem(row, column, item)
        self.table.scrollToBottom()

        self._last_rows = rows
        self.status_label.setText(f"{len(rows)} entries")
