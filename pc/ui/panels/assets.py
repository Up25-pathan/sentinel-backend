from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QComboBox, QDialog, QFormLayout, QTextEdit, QMenu,
                             QDialogButtonBox, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QAction
from ui.stat_card import StatCard
from utils import campaign_manager
import sqlite3, os
from datetime import datetime

DB_PATH = os.path.join("db", "assets.db")

STATUS_COLORS = {
    "ACTIVE": "#22d3ee",
    "COMPROMISED": "#ef4444",
    "RETIRED": "#475569",
    "MONITORING": "#f59e0b",
}


def _init_db():
    os.makedirs("db", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            name TEXT,
            value TEXT,
            campaign TEXT,
            status TEXT,
            notes TEXT,
            created TEXT
        )"""
    )
    conn.commit()
    conn.close()


class AddAssetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Asset")
        self.setMinimumWidth(420)
        self.setStyleSheet("background:#0a0e12; color:#e2e8f0;")
        self._setup_ui()
        self._load_campaigns()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Server", "Domain", "IP", "Credential"])
        layout.addRow("Type:", self.type_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Asset display name")
        layout.addRow("Name:", self.name_edit)

        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("IP, domain, or username")
        layout.addRow("Value:", self.value_edit)

        self.campaign_combo = QComboBox()
        layout.addRow("Campaign:", self.campaign_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Active", "Monitoring", "Compromised", "Retired"])
        layout.addRow("Status:", self.status_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional notes...")
        self.notes_edit.setMaximumHeight(80)
        layout.addRow("Notes:", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        for w in [self.name_edit, self.value_edit, self.notes_edit, self.type_combo,
                  self.campaign_combo, self.status_combo]:
            w.setStyleSheet(
                "background:#14181f; color:#e2e8f0; border:1px solid #1a1e2e; "
                "padding:6px; border-radius:4px;"
            )

    def _load_campaigns(self):
        self.campaign_combo.clear()
        self.campaign_combo.addItem("None")
        campaigns = campaign_manager.get_campaigns()
        for cid, name in campaigns:
            self.campaign_combo.addItem(name, userData=cid)

    def get_data(self):
        return {
            "type": self.type_combo.currentText(),
            "name": self.name_edit.text().strip(),
            "value": self.value_edit.text().strip(),
            "campaign": self.campaign_combo.currentText(),
            "status": self.status_combo.currentText().upper(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class AssetsPanel(QWidget):
    def __init__(self):
        super().__init__()
        _init_db()
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("ASSETS REGISTRY")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        stats_layout = QHBoxLayout()
        self.card_total = StatCard("Total Assets", "0", "#22d3ee")
        self.card_servers = StatCard("Servers", "0", "#4f8cff")
        self.card_domains = StatCard("Domains", "0", "#a78bfa")
        self.card_creds = StatCard("Credentials", "0", "#f59e0b")
        for card in [self.card_total, self.card_servers, self.card_domains, self.card_creds]:
            stats_layout.addWidget(card)
        layout.addLayout(stats_layout)

        toolbar = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Server", "Domain", "IP", "Credential"])
        self.filter_combo.currentTextChanged.connect(self.refresh)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search assets...")
        self.search_edit.textChanged.connect(self._debounce_search)

        self.add_btn = QPushButton("ADD ASSET")
        self.add_btn.clicked.connect(self._add_asset)

        self.refresh_btn = QPushButton("REFRESH")
        self.refresh_btn.clicked.connect(self.refresh)

        toolbar.addWidget(QLabel("Type:"))
        toolbar.addWidget(self.filter_combo)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.search_edit, 1)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Type", "Name", "Value", "Campaign", "Status", "Notes", "Created"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.table, 1)

        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.refresh)

    def _debounce_search(self):
        self._search_timer.start(300)

    def refresh(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        conditions = []
        params = []

        filter_type = self.filter_combo.currentText()
        if filter_type != "All":
            conditions.append("type = ?")
            params.append(filter_type)

        search = self.search_edit.text().strip()
        if search:
            conditions.append("(name LIKE ? OR value LIKE ? OR notes LIKE ? OR campaign LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like, like])

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        cursor.execute(f"SELECT id, type, name, value, campaign, status, notes, created FROM assets {where} ORDER BY created DESC")
        rows = cursor.fetchall()
        conn.close()

        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))

        total = len(rows)
        servers = domains = creds = 0

        for row_idx, row in enumerate(rows):
            asset_id, atype, name, value, campaign, status, notes, created = row
            items = [QTableWidgetItem(atype), QTableWidgetItem(name),
                     QTableWidgetItem(value), QTableWidgetItem(campaign),
                     QTableWidgetItem(status), QTableWidgetItem(notes),
                     QTableWidgetItem(created if created else "")]
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, asset_id)
                if col == 4:
                    item.setForeground(QColor(STATUS_COLORS.get(status, "#64748b")))
                self.table.setItem(row_idx, col, item)

            if atype == "Server":
                servers += 1
            elif atype == "Domain":
                domains += 1
            elif atype == "Credential":
                creds += 1

        self.card_total.set_value(total)
        self.card_servers.set_value(servers)
        self.card_domains.set_value(domains)
        self.card_creds.set_value(creds)

    def _add_asset(self):
        dialog = AddAssetDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["name"] or not data["value"]:
                QMessageBox.warning(self, "Warning", "Name and Value are required.")
                return
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO assets (type, name, value, campaign, status, notes, created) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (data["type"], data["name"], data["value"], data["campaign"],
                 data["status"], data["notes"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            conn.close()
            self.refresh()

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#0a0e12; color:#e2e8f0; border:1px solid #1a1e2e; }"
            "QMenu::item:selected { background:#1a1e2e; }"
        )
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")
        copy_action = menu.addAction("Copy Value")
        action = menu.exec(self.table.mapToGlobal(pos))
        if action == edit_action:
            self._edit_asset(row)
        elif action == delete_action:
            self._delete_asset(row)
        elif action == copy_action:
            self._copy_value(row)

    def _edit_asset(self, row):
        item = self.table.item(row, 0)
        if not item:
            return
        asset_id = item.data(Qt.ItemDataRole.UserRole)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT type, name, value, campaign, status, notes FROM assets WHERE id = ?", (asset_id,))
        row_data = cursor.fetchone()
        conn.close()
        if not row_data:
            return
        atype, name, value, campaign, status, notes = row_data

        dialog = AddAssetDialog(self)
        dialog.setWindowTitle("Edit Asset")
        dialog.type_combo.setCurrentText(atype)
        dialog.name_edit.setText(name)
        dialog.value_edit.setText(value)
        ci = dialog.campaign_combo.findText(campaign)
        if ci >= 0:
            dialog.campaign_combo.setCurrentIndex(ci)
        dialog.status_combo.setCurrentText(status.capitalize())
        dialog.notes_edit.setPlainText(notes)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["name"] or not data["value"]:
                QMessageBox.warning(self, "Warning", "Name and Value are required.")
                return
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE assets SET type=?, name=?, value=?, campaign=?, status=?, notes=? WHERE id=?",
                (data["type"], data["name"], data["value"], data["campaign"],
                 data["status"], data["notes"], asset_id),
            )
            conn.commit()
            conn.close()
            self.refresh()

    def _delete_asset(self, row):
        item = self.table.item(row, 0)
        if not item:
            return
        asset_id = item.data(Qt.ItemDataRole.UserRole)
        name_item = self.table.item(row, 1)
        asset_name = name_item.text() if name_item else "this asset"
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete asset '{asset_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            conn.commit()
            conn.close()
            self.refresh()

    def _copy_value(self, row):
        item = self.table.item(row, 2)
        if item and item.text():
            clipboard = QApplication.clipboard()
            clipboard.setText(item.text())
