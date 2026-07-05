from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QLineEdit, QScrollArea,
                             QFrame, QDialog)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from utils.api_client import SERVER_URL
from ..stat_card import StatCard
import json


class FeedDetailDialog(QDialog):
    def __init__(self, article, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feed Detail")
        self.setMinimumSize(500, 350)
        self.setObjectName("FeedDetailDialog")
        self.setStyleSheet("""
            #FeedDetailDialog {
                background: #080a0e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        src = article.get("source_name", article.get("source", ""))
        src_label = QLabel(src)
        src_label.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 11pt;")

        title = article.get("title", "")
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("color: #e2e8f0; font-size: 14pt; font-weight: 600;")

        summary = article.get("summary", article.get("description", ""))
        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("color: #94a3b8; font-size: 10pt;")

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
                padding: 8px 24px; border-radius: 4px; font-weight: 600;
            }
            QPushButton:hover { background: #334155; }
        """)
        close_btn.clicked.connect(self.accept)

        layout.addWidget(src_label)
        layout.addWidget(title_label)
        layout.addWidget(summary_label)
        layout.addStretch()
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class ArticleCard(QFrame):
    def __init__(self, article, parent=None):
        super().__init__(parent)
        self.setObjectName("HUDFrame")
        self.article = article
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        src = article.get("source_name", article.get("source", ""))
        self.source_label = QLabel(src)
        self.source_label.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 10pt;")

        title = article.get("title", "")
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: #e2e8f0; font-size: 11pt; font-weight: 600;")

        summary = article.get("summary", article.get("description", ""))
        if len(summary) > 150:
            summary = summary[:147] + "..."
        self.summary_label = QLabel(summary)
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #94a3b8; font-size: 9pt;")

        bottom = QHBoxLayout()
        cat = article.get("category", "")
        self.category_badge = QLabel(cat.upper())
        self.category_badge.setStyleSheet(
            "background: #1e293b; color: #22d3ee; padding: 2px 8px; "
            "border-radius: 3px; font-size: 8pt; font-weight: 600;"
        )

        ts = article.get("published_at", article.get("timestamp", ""))[:16]
        self.timestamp_label = QLabel(ts)
        self.timestamp_label.setStyleSheet("color: #475569; font-size: 8pt;")

        bottom.addWidget(self.category_badge)
        bottom.addStretch()
        bottom.addWidget(self.timestamp_label)

        layout.addWidget(self.source_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addLayout(bottom)

        self.setCursor(Qt.CursorShape.PointingHandCursor)


class ThreatFeedsPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._nam = QNetworkAccessManager(self)
        self._articles = []
        self._setup_ui()
        self._connect_signals()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("THREAT FEEDS")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        top_bar = QHBoxLayout()

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search feeds...")

        self.source_filter = QComboBox()
        self.source_filter.addItems(["All Sources"])

        self.category_filter = QComboBox()
        self.category_filter.addItems(["All Categories"])

        self.refresh_btn = QPushButton("Refresh")

        top_bar.addWidget(self.search_field, 1)
        top_bar.addWidget(self.source_filter)
        top_bar.addWidget(self.category_filter)
        top_bar.addWidget(self.refresh_btn)
        layout.addLayout(top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.card_layout = QVBoxLayout(self.scroll_content)
        self.card_layout.setSpacing(8)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll, 1)

        self.no_data_label = QLabel("NO INTELLIGENCE FEEDS AVAILABLE")
        self.no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_data_label.setStyleSheet("color: #475569; font-size: 14pt; font-weight: 600;")
        self.no_data_label.setVisible(False)
        layout.addWidget(self.no_data_label)

    def _connect_signals(self):
        self.api_client.osintDataReady.connect(self._on_osint)
        self.refresh_btn.clicked.connect(self._refresh)
        self.search_field.textChanged.connect(self._filter_cards)
        self.source_filter.currentIndexChanged.connect(self._filter_cards)
        self.category_filter.currentIndexChanged.connect(self._filter_cards)
        self._nam.finished.connect(self._on_feeds_reply)

    def _refresh(self):
        self.api_client.fetch_osint(limit=50)
        url = QUrl(f"{SERVER_URL}/api/intelligence/feeds")
        req = QNetworkRequest(url)
        if self.api_client.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.api_client.token}".encode())
        self._nam.get(req)

    def _on_osint(self, data):
        articles = data.get("data", [])
        if articles:
            self._articles = articles
            self._populate_cards()

    def _on_feeds_reply(self, reply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = json.loads(reply.readAll().data().decode())
            feeds = data if isinstance(data, list) else data.get("feeds", [])
            if feeds:
                self._articles = feeds
                self._populate_cards()
        reply.deleteLater()

    def _populate_cards(self):
        sources = set()
        categories = set()
        for a in self._articles:
            src = a.get("source_name", a.get("source", ""))
            cat = a.get("category", "")
            if src:
                sources.add(src)
            if cat:
                categories.add(cat)

        current_src = self.source_filter.currentText()
        current_cat = self.category_filter.currentText()
        self.source_filter.blockSignals(True)
        self.category_filter.blockSignals(True)
        self.source_filter.clear()
        self.source_filter.addItems(["All Sources"] + sorted(sources))
        self.category_filter.clear()
        self.category_filter.addItems(["All Categories"] + sorted(categories))
        self.source_filter.blockSignals(False)
        self.category_filter.blockSignals(False)
        idx_src = self.source_filter.findText(current_src)
        if idx_src >= 0:
            self.source_filter.setCurrentIndex(idx_src)
        idx_cat = self.category_filter.findText(current_cat)
        if idx_cat >= 0:
            self.category_filter.setCurrentIndex(idx_cat)

        self._filter_cards()

    def _filter_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        search = self.search_field.text().lower()
        source = self.source_filter.currentText()
        category = self.category_filter.currentText()

        visible = 0
        for a in self._articles:
            title = a.get("title", "")
            summary = a.get("summary", a.get("description", ""))
            src = a.get("source_name", a.get("source", ""))
            cat = a.get("category", "")

            if source != "All Sources" and src != source:
                continue
            if category != "All Categories" and cat != category:
                continue
            if search and search not in title.lower() and search not in summary.lower():
                continue

            card = ArticleCard(a)
            card.mousePressEvent = lambda e, art=a: self._show_detail(art)
            self.card_layout.addWidget(card)
            visible += 1

        self.no_data_label.setVisible(visible == 0)

    def _show_detail(self, article):
        dlg = FeedDetailDialog(article, self)
        dlg.exec()

    def refresh(self):
        self._refresh()
