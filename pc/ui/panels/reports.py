import csv
import io
import json
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QFileDialog, QMessageBox, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import QUrl
from utils.api_client import SERVER_URL

class ReportsPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._nam = QNetworkAccessManager(self)
        self._events_data = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Export & Reports")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        # Export controls
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["CSV", "JSON"])
        controls.addWidget(QLabel("Format:"))
        controls.addWidget(self.format_combo)

        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["50", "100", "500", "All"])
        controls.addWidget(QLabel("Limit:"))
        controls.addWidget(self.limit_combo)

        self.fetch_btn = QPushButton("LOAD DATA")
        self.fetch_btn.clicked.connect(self._fetch_events)
        controls.addWidget(self.fetch_btn)

        self.export_btn = QPushButton("EXPORT")
        self.export_btn.clicked.connect(self._export)
        self.export_btn.setEnabled(False)
        controls.addWidget(self.export_btn)

        controls.addStretch()
        layout.addLayout(controls)

        # Preview table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Title", "Category", "Risk", "Country", "Breaking", "Time"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        # Stats
        self.stats_label = QLabel("No data loaded")
        self.stats_label.setStyleSheet("color:#475569; font-size:8pt;")
        layout.addWidget(self.stats_label)

    def _fetch_events(self):
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("LOADING...")

        limit = self.limit_combo.currentText()
        limit_param = "500" if limit == "All" else limit

        url = QUrl(f"{SERVER_URL}/api/events?limit={limit_param}")
        req = QNetworkRequest(url)
        if self.api_client.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.api_client.token}".encode())
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_data(r))

    def _on_data(self, reply):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("LOAD DATA")

        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = json.loads(reply.readAll().data().decode())
            self._events_data = data.get("events", [])
            self._render_table()
            self.export_btn.setEnabled(len(self._events_data) > 0)

            critical = sum(1 for e in self._events_data if e.get("risk_level") == "CRITICAL")
            high = sum(1 for e in self._events_data if e.get("risk_level") == "HIGH")
            breaking = sum(1 for e in self._events_data if e.get("is_breaking"))
            self.stats_label.setText(
                f"{len(self._events_data)} events loaded | "
                f"{breaking} breaking | {critical} critical | {high} high"
            )
        else:
            QMessageBox.warning(self, "Error", f"Failed to fetch: {reply.errorString()}")
            self.stats_label.setText("Load failed")

        reply.deleteLater()

    def _render_table(self):
        self.table.setRowCount(0)
        self.table.setRowCount(len(self._events_data))
        for row, ev in enumerate(self._events_data):
            items = [
                QTableWidgetItem(ev.get("title", "")),
                QTableWidgetItem(ev.get("category", "")),
                QTableWidgetItem(ev.get("risk_level", "")),
                QTableWidgetItem(ev.get("country", "")),
                QTableWidgetItem("YES" if ev.get("is_breaking") else ""),
                QTableWidgetItem(ev.get("created_at", "")[:19]),
            ]
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

    def _export(self):
        fmt = self.format_combo.currentText()
        if fmt == "CSV":
            self._export_csv()
        else:
            self._export_json()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", f"sentinel_export_{datetime.now():%Y%m%d_%H%M%S}.csv", "CSV Files (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Title", "Category", "Risk Level", "Location", "Country", "Breaking", "Summary", "Time"])
                for ev in self._events_data:
                    writer.writerow([
                        ev.get("title", ""),
                        ev.get("category", ""),
                        ev.get("risk_level", ""),
                        ev.get("location_name", ""),
                        ev.get("country", ""),
                        "YES" if ev.get("is_breaking") else "",
                        ev.get("summary", ""),
                        ev.get("created_at", ""),
                    ])
            QMessageBox.information(self, "Success", f"Exported {len(self._events_data)} events to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON", f"sentinel_export_{datetime.now():%Y%m%d_%H%M%S}.json", "JSON Files (*.json)")
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"exported_at": datetime.now().isoformat(), "events": self._events_data}, f, indent=2)
            QMessageBox.information(self, "Success", f"Exported {len(self._events_data)} events to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def refresh(self):
        pass
