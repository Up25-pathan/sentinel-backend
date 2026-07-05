from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QComboBox, QProgressBar, QMenu, QFrame)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QColor, QAction
import random


class NetworkScannerPanel(QWidget):
    STYLESHEET = """
    NetworkScannerPanel {
        background-color: #080a0e;
    }
    QLabel#sectionTitle {
        color: #f59e0b;
        font-size: 13px;
        font-weight: bold;
        letter-spacing: 2px;
        padding: 4px 0px;
    }
    QLabel#statusLabel {
        color: #475569;
        font-size: 11px;
        font-weight: bold;
        letter-spacing: 1px;
        padding: 2px 8px;
        border: 1px solid #1a1e2e;
        border-radius: 3px;
        background-color: #0d0f14;
    }
    QLineEdit {
        background-color: #0d0f14;
        color: #e2e8f0;
        border: 1px solid #1a1e2e;
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 12px;
    }
    QLineEdit:focus {
        border-color: #f59e0b;
    }
    QComboBox {
        background-color: #0d0f14;
        color: #e2e8f0;
        border: 1px solid #1a1e2e;
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 12px;
        min-width: 120px;
    }
    QComboBox:focus {
        border-color: #f59e0b;
    }
    QComboBox QAbstractItemView {
        background-color: #0d0f14;
        color: #e2e8f0;
        border: 1px solid #1a1e2e;
        selection-background-color: #1a1e2e;
    }
    QPushButton {
        background-color: #1a1e2e;
        color: #e2e8f0;
        border: 1px solid #1a1e2e;
        border-radius: 4px;
        padding: 6px 18px;
        font-size: 11px;
        font-weight: bold;
        letter-spacing: 1px;
    }
    QPushButton:hover {
        border-color: #f59e0b;
        color: #f59e0b;
    }
    QPushButton:pressed {
        background-color: #f59e0b;
        color: #080a0e;
    }
    QPushButton:disabled {
        border-color: #1a1e2e;
        color: #475569;
    }
    QPushButton#clearBtn {
        background-color: transparent;
        border: 1px solid #475569;
        color: #475569;
    }
    QPushButton#clearBtn:hover {
        border-color: #ef4444;
        color: #ef4444;
    }
    QTableWidget {
        background-color: #0a0c12;
        color: #e2e8f0;
        border: 1px solid #1a1e2e;
        border-radius: 4px;
        gridline-color: #1a1e2e;
        font-size: 11px;
    }
    QTableWidget::item {
        padding: 4px 8px;
    }
    QTableWidget::item:selected {
        background-color: #1a1e2e;
        color: #f59e0b;
    }
    QHeaderView::section {
        background-color: #0d0f14;
        color: #22d3ee;
        border: none;
        border-bottom: 1px solid #1a1e2e;
        border-right: 1px solid #1a1e2e;
        padding: 6px 8px;
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 1px;
    }
    QProgressBar {
        background-color: #0d0f14;
        border: 1px solid #1a1e2e;
        border-radius: 3px;
        text-align: center;
        color: #e2e8f0;
        font-size: 10px;
        height: 18px;
    }
    QProgressBar::chunk {
        background-color: #22d3ee;
        border-radius: 2px;
    }
    QFrame#sep {
        border: none;
        border-top: 1px solid #1a1e2e;
    }
    """

    SCAN_TYPES = ["Ping", "Port Scan", "Service Scan", "Full Scan"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self.STYLESHEET)

        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(150)
        self._scan_timer.timeout.connect(self._tick)

        self._scan_progress = 0
        self._scan_step = 0
        self._scan_rows = []
        self._scan_type = "Ping"

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("NETWORK SCANNER")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        target_row = QHBoxLayout()
        target_row.setSpacing(8)

        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Target IP or hostname")
        target_row.addWidget(self.target_input)

        self.scan_type_combo = QComboBox()
        self.scan_type_combo.addItems(self.SCAN_TYPES)
        target_row.addWidget(self.scan_type_combo)

        self.scan_btn = QPushButton("SCAN")
        self.scan_btn.clicked.connect(self._start_scan)
        target_row.addWidget(self.scan_btn)

        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.refresh)
        target_row.addWidget(self.clear_btn)

        layout.addLayout(target_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        self.status_label = QLabel("IDLE")
        self.status_label.setObjectName("statusLabel")
        status_row.addWidget(self.status_label)
        status_row.addStretch()

        layout.addLayout(status_row)

        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(
            ["Target", "Type", "Port", "Service", "Status", "Response Time"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.results_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self.results_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.results_table.customContextMenuRequested.connect(self._show_context_menu)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setAlternatingRowColors(False)
        layout.addWidget(self.results_table, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

    def refresh(self):
        self._scan_timer.stop()
        self._scan_progress = 0
        self._scan_step = 0
        self._scan_rows = []
        self._scan_type = "Ping"
        self.results_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.status_label.setText("IDLE")
        self.status_label.setStyleSheet("")
        self.scan_btn.setEnabled(True)
        self.target_input.clear()
        self.scan_type_combo.setCurrentIndex(0)

    def _start_scan(self):
        target = self.target_input.text().strip()
        if not target:
            return

        self._scan_type = self.scan_type_combo.currentText()
        self.results_table.setRowCount(0)
        self._scan_progress = 0
        self._scan_step = 0
        self._scan_rows = self._generate_results(target, self._scan_type)

        self.scan_btn.setEnabled(False)
        self.status_label.setText("SCANNING...")
        self.status_label.setStyleSheet(
            "color: #f59e0b; border-color: #f59e0b; background-color: #0d0f14;"
        )
        self.progress_bar.setValue(0)
        self._scan_timer.start()

    def _generate_results(self, target, scan_type):
        rows = []
        if scan_type == "Ping":
            alive = random.random() > 0.25
            rtt = round(random.uniform(1.5, 120.0), 1) if alive else None
            status = "ALIVE" if alive else "TIMEOUT"
            rtt_str = f"{rtt}ms" if rtt else "---"
            rows.append((target, "Ping", "---", "---", status, rtt_str))

        elif scan_type == "Port Scan":
            ports = [22, 80, 443, 8080, 8443]
            for port in ports:
                status = random.choices(
                    ["OPEN", "CLOSED", "FILTERED"], weights=[3, 5, 2]
                )[0]
                rtt = round(random.uniform(0.5, 45.0), 1) if status != "FILTERED" else None
                rtt_str = f"{rtt}ms" if rtt else "---"
                rows.append((target, "Port Scan", str(port), "---", status, rtt_str))

        elif scan_type == "Service Scan":
            services = {
                22: "SSH",
                80: "HTTP",
                443: "HTTPS",
                8080: "HTTP-Proxy",
                8443: "HTTPS-Alt",
                21: "FTP",
                25: "SMTP",
            }
            selected = random.sample(list(services.items()), k=random.randint(4, 6))
            for port, svc in sorted(selected):
                status = random.choices(
                    ["OPEN", "CLOSED", "FILTERED"], weights=[4, 4, 2]
                )[0]
                rtt = round(random.uniform(0.5, 45.0), 1) if status != "FILTERED" else None
                rtt_str = f"{rtt}ms" if rtt else "---"
                rows.append((target, "Service Scan", str(port), svc, status, rtt_str))

        elif scan_type == "Full Scan":
            all_ports = [
                21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445,
                993, 995, 1433, 1521, 2049, 3306, 3389, 5432, 5900, 6379,
                8080, 8443, 27017,
            ]
            selected_ports = random.sample(all_ports, k=random.randint(12, 18))
            for port in sorted(selected_ports):
                status = random.choices(
                    ["OPEN", "CLOSED", "FILTERED"], weights=[2, 6, 2]
                )[0]
                rtt = round(random.uniform(0.5, 45.0), 1) if status != "FILTERED" else None
                rtt_str = f"{rtt}ms" if rtt else "---"
                rows.append((target, "Full Scan", str(port), "---", status, rtt_str))

        random.shuffle(rows)
        return rows

    def _tick(self):
        total_steps = max(len(self._scan_rows), 5)
        batch_size = max(1, total_steps // 8)

        for _ in range(batch_size):
            if self._scan_step < len(self._scan_rows):
                row_data = self._scan_rows[self._scan_step]
                self._add_row(row_data)
                self._scan_step += 1
                self._scan_progress = int((self._scan_step / total_steps) * 100)
                self.progress_bar.setValue(min(self._scan_progress, 99))

        if self._scan_step >= len(self._scan_rows):
            self._scan_finished()

    def _add_row(self, row_data):
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        colors = {
            "OPEN": "#22d3ee",
            "CLOSED": "#475569",
            "FILTERED": "#f59e0b",
            "ALIVE": "#22d3ee",
            "TIMEOUT": "#ef4444",
        }

        for col, val in enumerate(row_data):
            item = QTableWidgetItem(str(val))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 4:
                color = colors.get(val, "#e2e8f0")
                item.setForeground(QColor(color))
            else:
                item.setForeground(QColor("#e2e8f0"))
            self.results_table.setItem(row, col, item)

    def _scan_finished(self):
        self._scan_timer.stop()
        self.progress_bar.setValue(100)
        self.status_label.setText("COMPLETE")
        self.status_label.setStyleSheet(
            "color: #22d3ee; border-color: #22d3ee; background-color: #0d0f14;"
        )
        self.scan_btn.setEnabled(True)

    def _show_context_menu(self, pos: QPoint):
        item = self.results_table.itemAt(pos)
        if item is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #0d0f14;
                border: 1px solid #1a1e2e;
                padding: 4px;
            }
            QMenu::item {
                color: #e2e8f0;
                padding: 6px 24px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #1a1e2e;
                color: #f59e0b;
            }
            """
        )

        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self._copy_selected)
        menu.addAction(copy_action)

        menu.exec(self.results_table.viewport().mapToGlobal(pos))

    def _copy_selected(self):
        selected = self.results_table.selectedItems()
        if not selected:
            return

        rows = {}
        for item in selected:
            row = item.row()
            col = item.column()
            rows.setdefault(row, {})[col] = item.text()

        lines = []
        for row in sorted(rows.keys()):
            cells = [rows[row].get(c, "") for c in range(self.results_table.columnCount())]
            lines.append("\t".join(cells))

        clipboard = self.window().findChild(QWidget, "").parent() if self.window() else None
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(lines))
