from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QPushButton, QComboBox, QTextEdit, QGroupBox,
                             QSplitter)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

PLATFORM_COLORS = {
    "Telegram": "#0088cc",
    "X": "#1da1f2",
    "Reddit": "#ff4500",
}

class OSINTFeedPanel(QWidget):
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

        title = QLabel("OSINT Intelligence Feeds")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        filters = QHBoxLayout()
        self.platform_filter = QComboBox()
        self.platform_filter.addItems(["All Platforms", "Telegram", "X", "Reddit"])
        self.refresh_btn = QPushButton("Refresh")
        filters.addWidget(QLabel("Platform:"))
        filters.addWidget(self.platform_filter)
        filters.addStretch()
        filters.addWidget(self.refresh_btn)
        layout.addLayout(filters)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Source", "Title", "Description", "Published", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self.table, 1)

        self.detail_box = QGroupBox("Article Preview")
        detail_layout = QVBoxLayout(self.detail_box)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(120)
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
        self.api_client.osintDataReady.connect(self._on_osint)
        self.refresh_btn.clicked.connect(self._refresh)
        self.platform_filter.currentIndexChanged.connect(self._refresh)

    def _refresh(self):
        platform = self.platform_filter.currentText()
        self.api_client.fetch_osint(
            page=self._current_page,
            platform=None if platform == "All Platforms" else platform,
        )

    def _on_osint(self, data):
        articles = data.get("data", [])
        pagination = data.get("pagination", {})
        self.table.setRowCount(0)
        self.table.setRowCount(len(articles))

        for row, art in enumerate(articles):
            source = art.get("source_name", "")
            source_pretty = source.replace("OSINT:", "")
            source_item = QTableWidgetItem(source_pretty)
            color = PLATFORM_COLORS.get(source_pretty, "#94a3b8")
            source_item.setForeground(QColor(color))

            items = [
                source_item,
                QTableWidgetItem(art.get("title", "")[:80]),
                QTableWidgetItem(art.get("description", "")[:120]),
                QTableWidgetItem(art.get("published_at", "")[:16]),
                QTableWidgetItem(art.get("url", "")),
            ]
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

        total = pagination.get("total", 0)
        pages = pagination.get("pages", 1)
        self.page_label.setText(f"Page {self._current_page} of {pages} ({total} articles)")
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < pages)

    def _on_select(self):
        rows = self.table.selectedItems()
        if not rows:
            self.detail_box.setVisible(False)
            return
        row = rows[0].row()
        items = [self.table.item(row, c) for c in range(5)]
        if items[1]:
            self.detail_text.setHtml(
                f"<b>Source:</b> {items[0].text() if items[0] else ''}<br>"
                f"<b>Title:</b> {items[1].text() if items[1] else ''}<br>"
                f"<b>URL:</b> <a href='{items[4].text() if items[4] else ''}'>{items[4].text() if items[4] else ''}</a>"
            )
            self.detail_box.setVisible(True)

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._refresh()

    def _next_page(self):
        self._current_page += 1
        self._refresh()
