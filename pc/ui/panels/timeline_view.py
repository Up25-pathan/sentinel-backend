from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                             QCheckBox, QPushButton, QListWidget, QListWidgetItem, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont

TYPE_COLORS = {
    "events": "#22d3ee",
    "alerts": "#ef4444",
    "jobs": "#f59e0b",
    "phases": "#22d3ee",
    "intel": "#a78bfa",
}

TYPE_BADGE_COLORS = {
    "events": "#155e75",
    "alerts": "#7f1d1d",
    "jobs": "#78350f",
    "phases": "#155e75",
    "intel": "#4c1d95",
}


class TimelineEntryFrame(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("TimelineEntry")
        self.setFixedHeight(48)
        self.setStyleSheet("""
            QFrame#TimelineEntry {
                background: transparent;
                border-bottom: 1px solid #1a1e2e;
            }
            QFrame#TimelineEntry:hover {
                background: #0f1320;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        dot = QFrame()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(
            f"background: {TYPE_COLORS.get(entry['type'], '#475569')}; "
            f"border-radius: 5px; border: none;"
        )
        layout.addWidget(dot)

        ts_label = QLabel(entry.get("timestamp", ""))
        ts_label.setStyleSheet("color: #475569; font-size: 7pt; font-family: 'Consolas', monospace; background: transparent; border: none;")
        ts_label.setFixedWidth(120)
        layout.addWidget(ts_label)

        title_label = QLabel(entry.get("title", ""))
        title_label.setStyleSheet("color: #c8d6e0; font-size: 8pt; background: transparent; border: none;")
        title_label.setWordWrap(False)
        layout.addWidget(title_label, 1)

        badge = QLabel(entry["type"].upper())
        badge.setFixedHeight(16)
        badge.setStyleSheet(
            f"background: {TYPE_BADGE_COLORS.get(entry['type'], '#1e293b')}; "
            f"color: {TYPE_COLORS.get(entry['type'], '#94a3b8')}; "
            f"font-size: 6pt; font-weight: 700; padding: 0 6px; "
            f"border-radius: 3px; border: none;"
        )
        layout.addWidget(badge)

    def mousePressEvent(self, event):
        self.clicked.emit(self.entry)
        super().mousePressEvent(event)


class TimelinePanel(QWidget):
    entryClicked = pyqtSignal(dict)

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._all_entries = []
        self._filtered_entries = []
        self._dashboard_data = {}
        self._alerts_data = []
        self._audit_logs = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(12, 8, 12, 8)
        filter_bar.setSpacing(8)

        filter_label = QLabel("FILTER:")
        filter_label.setStyleSheet("color: #64748b; font-size: 7pt; font-weight: 600; background: transparent;")
        filter_bar.addWidget(filter_label)

        self._checkboxes = {}
        for key in TYPE_COLORS:
            cb = QCheckBox(key.upper())
            cb.setChecked(True)
            cb.setStyleSheet(
                f"QCheckBox {{ color: {TYPE_COLORS[key]}; font-size: 7pt; }}"
                f"QCheckBox::indicator {{ width: 10px; height: 10px; }}"
            )
            cb.toggled.connect(self._apply_filter)
            filter_bar.addWidget(cb)
            self._checkboxes[key] = cb

        filter_bar.addStretch()

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #475569; font-size: 7pt; background: transparent;")
        filter_bar.addWidget(self._count_label)

        refresh_btn = QPushButton("REFRESH")
        refresh_btn.setFixedWidth(70)
        refresh_btn.clicked.connect(self.refresh)
        filter_bar.addWidget(refresh_btn)

        container = QWidget()
        container.setStyleSheet("background: #080a0e; border-bottom: 1px solid #1a1e2e;")
        container.setLayout(filter_bar)
        layout.addWidget(container)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: #080a0e;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border: none;
                background: transparent;
            }
            QListWidget::item:selected {
                background: transparent;
            }
        `")
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget, 1)

    def _connect_signals(self):
        self.api_client.dashboardDataReady.connect(self._on_dashboard)
        self.api_client.alertsDataReady.connect(self._on_alerts)

    def refresh(self):
        self.api_client.fetch_dashboard()
        self.api_client.fetch_alerts()
        from utils import audit
        try:
            self._audit_logs = audit.get_latest_logs(100) or []
        except Exception:
            self._audit_logs = []
        self._merge_and_render()

    def _on_dashboard(self, data):
        self._dashboard_data = data
        self._merge_and_render()

    def _on_alerts(self, alerts):
        self._alerts_data = alerts if isinstance(alerts, list) else []
        self._merge_and_render()

    def _merge_and_render(self):
        self._all_entries = []

        overview = self._dashboard_data.get("overview", {}) if self._dashboard_data else {}
        recent_events = self._dashboard_data.get("recent_events", []) if self._dashboard_data else []
        if not recent_events and "events" in self._dashboard_data:
            recent_events = self._dashboard_data["events"]

        for evt in recent_events:
            self._all_entries.append({
                "type": "events",
                "timestamp": evt.get("created_at", evt.get("timestamp", ""))[:19],
                "title": evt.get("title", evt.get("name", "Unknown event")),
                "details": evt,
            })

        for alert in self._alerts_data:
            self._all_entries.append({
                "type": "alerts",
                "timestamp": alert.get("created_at", "")[:19],
                "title": alert.get("message", "Unknown alert"),
                "details": alert,
            })

        for log in self._audit_logs:
            ts, action, details = log if len(log) == 3 else (log[0] if len(log) > 0 else "", log[1] if len(log) > 1 else "unknown", "")
            self._all_entries.append({
                "type": "jobs",
                "timestamp": str(ts)[:19],
                "title": action,
                "details": details,
            })

        campaign_phases = self._dashboard_data.get("campaign_phases", []) if self._dashboard_data else []
        if not campaign_phases and "phases" in self._dashboard_data:
            campaign_phases = self._dashboard_data["phases"]
        for phase in campaign_phases:
            self._all_entries.append({
                "type": "phases",
                "timestamp": phase.get("updated_at", phase.get("created_at", ""))[:19],
                "title": phase.get("phase_name", phase.get("name", "Campaign phase")),
                "details": phase,
            })

        intel_items = self._dashboard_data.get("intel_summary", []) if self._dashboard_data else []
        for item in intel_items:
            self._all_entries.append({
                "type": "intel",
                "timestamp": item.get("date", item.get("timestamp", ""))[:19],
                "title": item.get("title", item.get("summary", "Intel item")),
                "details": item,
            })

        def _sort_key(e):
            return e.get("timestamp", "")

        self._all_entries.sort(key=_sort_key, reverse=True)
        self._apply_filter()

    def _apply_filter(self):
        active_types = {k for k, cb in self._checkboxes.items() if cb.isChecked()}
        self._filtered_entries = [e for e in self._all_entries if e["type"] in active_types]

        self._count_label.setText(f"{len(self._filtered_entries)} items")
        self._render()

    def _render(self):
        self.list_widget.clear()

        for entry in self._filtered_entries:
            item = QListWidgetItem(self.list_widget)
            frame = TimelineEntryFrame(entry)
            frame.clicked.connect(self._on_frame_clicked)
            item.setSizeHint(frame.sizeHint())
            self.list_widget.setItemWidget(item, frame)

    def _on_frame_clicked(self, entry):
        self.entryClicked.emit(entry)

    def _on_item_clicked(self, item):
        widget = self.list_widget.itemWidget(item)
        if isinstance(widget, TimelineEntryFrame):
            self.entryClicked.emit(widget.entry)
