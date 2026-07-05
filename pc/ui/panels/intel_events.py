from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QPushButton,
    QLineEdit, QGroupBox, QTextEdit, QSplitter, QFrame, QScrollArea,
    QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from ..stat_card import StatCard
from utils.api_client import SERVER_URL

RISK_COLORS = {
    "CRITICAL": "#ef4444", "HIGH": "#f59e0b",
    "MEDIUM": "#22d3ee", "LOW": "#64748b",
}
CAT_COLORS = {
    "WAR": "#ef4444", "MILITARY_MOVEMENT": "#f59e0b",
    "SANCTIONS": "#a78bfa", "COUP": "#ef4444",
    "DIPLOMATIC_ESCALATION": "#f59e0b", "NUCLEAR_THREAT": "#ef4444",
    "POLITICAL_INSTABILITY": "#f59e0b", "TERRORISM": "#ef4444",
    "CYBER_ATTACK": "#22d3ee", "HUMANITARIAN": "#22d3ee",
}

class DetailWidget(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setObjectName("DetailWidget")
        self.inner = QWidget()
        self.inner.setObjectName("DetailInner")
        self.lay = QVBoxLayout(self.inner)
        self.lay.setContentsMargins(12, 12, 12, 12)
        self.lay.setSpacing(8)
        self.setWidget(self.inner)
        self._clear()

    def _clear(self):
        for i in reversed(range(self.lay.count())):
            w = self.lay.itemAt(i).widget()
            if w: w.deleteLater()
        self.lay.addWidget(QLabel("Select an event to view details"))
        self._is_busy = False

    def _loading(self):
        for i in reversed(range(self.lay.count())):
            w = self.lay.itemAt(i).widget()
            if w: w.deleteLater()
        self.lay.addWidget(QLabel("Loading..."))
        self._is_busy = True

    def show_event(self, data):
        self._is_busy = False
        for i in reversed(range(self.lay.count())):
            w = self.lay.itemAt(i).widget()
            if w: w.deleteLater()

        # ── Header ──
        title = QLabel(data.get("title", ""))
        title.setStyleSheet("font-size: 13pt; font-weight: 700; color: #f59e0b; letter-spacing: 1px;")
        title.setWordWrap(True)
        self.lay.addWidget(title)

        # ── Meta badges ──
        meta = QHBoxLayout()
        meta.setSpacing(6)

        is_breaking = data.get("is_breaking", 0)
        if is_breaking:
            b = QLabel("BREAKING")
            b.setStyleSheet("background:#7f1d1d; color:#fca5a5; padding:2px 8px; font-size:7pt; font-weight:700; letter-spacing:1px;")
            meta.addWidget(b)

        risk = data.get("risk_level", "")
        r = QLabel(risk)
        c = RISK_COLORS.get(risk, "#64748b")
        r.setStyleSheet(f"background:#1a1e2e; color:{c}; padding:2px 8px; font-size:7pt; font-weight:700; letter-spacing:1px;")
        meta.addWidget(r)

        cat = data.get("category", "")
        cc = QLabel(cat)
        cc.setStyleSheet(f"background:#1a1e2e; color:{CAT_COLORS.get(cat, '#94a3b8')}; padding:2px 8px; font-size:7pt; letter-spacing:1px;")
        meta.addWidget(cc)

        loc = data.get("location_name", "") or data.get("country", "")
        if loc:
            l = QLabel(loc)
            l.setStyleSheet("color: #64748b; font-size:7pt; padding:2px 8px;")
            meta.addWidget(l)

        meta.addStretch()
        self.lay.addLayout(meta)

        # ── AI Brief ──
        ai_brief = data.get("ai_brief", "")
        if ai_brief:
            grp = QGroupBox("AI ANALYSIS")
            g = QVBoxLayout(grp)
            tb = QTextEdit()
            tb.setReadOnly(True)
            tb.setMaximumHeight(120)
            tb.setHtml(f"<pre style='font-family:Consolas,monospace;font-size:8pt;color:#cbd5e1;white-space:pre-wrap'>{ai_brief}</pre>")
            g.addWidget(tb)
            self.lay.addWidget(grp)

        # ── Summary ──
        summary = data.get("summary", "")
        if summary:
            grp2 = QGroupBox("SUMMARY")
            g2 = QVBoxLayout(grp2)
            s = QLabel(summary)
            s.setWordWrap(True)
            s.setStyleSheet("font-size:8pt; color: #94a3b8;")
            g2.addWidget(s)
            self.lay.addWidget(grp2)

        # ── Images ──
        images = data.get("images_json", [])
        image_url = data.get("image_url", "")
        all_images = list(images or [])
        if image_url and image_url not in all_images:
            all_images.insert(0, image_url)

        if all_images:
            grp3 = QGroupBox("IMAGES")
            g3 = QHBoxLayout(grp3)
            g3.setSpacing(4)
            for url in all_images[:4]:
                img = QLabel()
                img.setFixedSize(180, 120)
                img.setStyleSheet("background:#0a0c12; border:1px solid #1a1e2e;")
                self._load_image(img, url)
                g3.addWidget(img)
            g3.addStretch()
            self.lay.addWidget(grp3)

        # ── Entities ──
        entities = data.get("entities")
        if entities and isinstance(entities, dict):
            grp4 = QGroupBox("ENTITIES")
            g4 = QGridLayout(grp4)
            g4.setSpacing(4)
            row = 0
            for etype, enames in entities.items():
                if enames and len(enames) > 0:
                    lbl = QLabel(f"<b>{etype.upper()}:</b> {', '.join(enames[:8])}")
                    lbl.setStyleSheet("font-size:8pt; color:#94a3b8;")
                    lbl.setWordWrap(True)
                    g4.addWidget(lbl, row, 0, 1, 1)
                    row += 1
            self.lay.addWidget(grp4)

        # ── Sources ──
        sources = data.get("sources", [])
        if sources:
            grp5 = QGroupBox("SOURCES")
            g5 = QVBoxLayout(grp5)
            g5.setSpacing(2)
            for src in sources[:8]:
                name = src.get("name", "")
                cred = src.get("credibility", "")
                cred_color = {"HIGH": "#22d3ee", "MEDIUM": "#f59e0b", "LOW": "#ef4444"}.get(cred, "#64748b")
                h = QHBoxLayout()
                n = QLabel(name)
                n.setStyleSheet("font-size:8pt; color:#cbd5e1;")
                c = QLabel(cred)
                c.setStyleSheet(f"font-size:7pt; color:{cred_color}; font-weight:600; letter-spacing:1px;")
                h.addWidget(n)
                h.addWidget(c)
                h.addStretch()
                g5.addLayout(h)
            self.lay.addWidget(grp5)

        # ── Related Events ──
        related = data.get("related", [])
        if related:
            grp6 = QGroupBox("RELATED EVENTS")
            g6 = QVBoxLayout(grp6)
            g6.setSpacing(2)
            for rel in related[:5]:
                rl = QLabel(f"  {rel.get('title', '')}")
                rl.setStyleSheet(f"font-size:8pt; color:{RISK_COLORS.get(rel.get('risk_level',''), '#64748b')};")
                g6.addWidget(rl)
            self.lay.addWidget(grp6)

        self.lay.addStretch()

    def _load_image(self, label, url):
        if not url or url == "null":
            label.setText("NO IMAGE")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color:#1e293b; font-size:7pt;")
            return
        nam = QNetworkAccessManager()
        req = QNetworkRequest(QUrl(url))
        reply = nam.get(req)
        reply.finished.connect(lambda: self._on_image_loaded(label, reply))

    def _on_image_loaded(self, label, reply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pix = QPixmap()
            if pix.loadFromData(data):
                label.setPixmap(pix.scaled(180, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            label.setText("IMG FAIL")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color:#ef4444; font-size:7pt;")
        reply.deleteLater()


class IntelEventsPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._current_page = 1
        self._total_pages = 1
        self._setup_ui()
        self._connect_signals()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Intelligence Events")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        filters = QHBoxLayout()
        filters.setSpacing(6)
        self.category_filter = QComboBox()
        self.category_filter.addItems(["All", "WAR", "MILITARY_MOVEMENT", "SANCTIONS", "COUP", "DIPLOMATIC_ESCALATION", "NUCLEAR_THREAT", "POLITICAL_INSTABILITY", "TERRORISM", "CYBER_ATTACK", "HUMANITARIAN"])
        self.risk_filter = QComboBox()
        self.risk_filter.addItems(["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search events...")
        self.refresh_btn = QPushButton("REFRESH")
        filters.addWidget(QLabel("Cat:"))
        filters.addWidget(self.category_filter)
        filters.addWidget(QLabel("Risk:"))
        filters.addWidget(self.risk_filter)
        filters.addWidget(self.search_input, 1)
        filters.addWidget(self.refresh_btn)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # ── Left: Table ──
        left = QWidget()
        lt = QVBoxLayout(left)
        lt.setContentsMargins(0, 0, 0, 0)
        lt.setSpacing(4)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Title", "Category", "Risk", "Location", "Country", "Time"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_select)
        lt.addWidget(self.table, 1)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀ PREV")
        self.prev_btn.clicked.connect(self._prev_page)
        self.page_label = QLabel("Page 1 / 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setStyleSheet("color:#475569; font-size:7pt;")
        self.next_btn = QPushButton("NEXT ▶")
        self.next_btn.clicked.connect(self._next_page)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.page_label, 1)
        nav.addWidget(self.next_btn)
        lt.addLayout(nav)

        splitter.addWidget(left)

        # ── Right: Detail ──
        self.detail = DetailWidget()
        splitter.addWidget(self.detail)

        splitter.setSizes([400, 500])
        layout.addWidget(splitter, 1)

    def _connect_signals(self):
        self.api_client.eventsDataReady.connect(self._on_events)
        self.api_client.eventDetailReady.connect(self._on_event_detail)
        self.refresh_btn.clicked.connect(self._refresh)
        self.category_filter.currentIndexChanged.connect(self._refresh)
        self.risk_filter.currentIndexChanged.connect(self._refresh)
        self.search_input.returnPressed.connect(self._refresh)

    def _on_event_detail(self, data):
        self.detail.show_event(data)

    def _refresh(self):
        cat = self.category_filter.currentText()
        risk = self.risk_filter.currentText()
        q = self.search_input.text().strip()

        if q:
            self._search_events(q, cat, risk)
        else:
            self.api_client.fetch_events(
                page=self._current_page,
                category=None if cat == "All" else cat,
                risk_level=None if risk == "All" else risk,
            )

    def _search_events(self, q, cat, risk):
        self.table.setRowCount(0)
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("Searching..."))
        from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        from PyQt6.QtCore import QUrl
        url = QUrl(f"{SERVER_URL}/api/events/search?q={q}")
        if cat != "All": url.setQuery(url.query() + f"&category={cat}")
        if risk != "All": url.setQuery(url.query() + f"&risk_level={risk}")
        req = QNetworkRequest(url)
        if self.api_client.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.api_client.token}".encode())
        nam = QNetworkAccessManager()
        reply = nam.get(req)
        reply.finished.connect(lambda: self._on_search_result(reply))

    def _on_search_result(self, reply):
        import json
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = json.loads(reply.readAll().data().decode())
            self._render_table(data.get("events", []))
            self.page_label.setText(f"Search: {data.get('count', 0)} results")
        reply.deleteLater()

    def _on_events(self, data):
        events = data.get("events", [])
        pagination = data.get("pagination", {})
        self._total_pages = pagination.get("pages", 1)
        self._render_table(events)
        total = pagination.get("total", 0)
        self.page_label.setText(f"Page {self._current_page} of {self._total_pages} ({total} events)")

    def _render_table(self, events):
        self.table.setRowCount(0)
        self.table.setRowCount(len(events))
        for row, ev in enumerate(events):
            risk = ev.get("risk_level", "")
            items = [
                QTableWidgetItem(ev.get("title", "")),
                QTableWidgetItem(ev.get("category", "")),
                QTableWidgetItem(risk),
                QTableWidgetItem(ev.get("location_name", "")),
                QTableWidgetItem(ev.get("country", "")),
                QTableWidgetItem(ev.get("created_at", "")[:19]),
            ]
            items[2].setForeground(QColor(RISK_COLORS.get(risk, "#64748b")))
            if ev.get("is_breaking"):
                f = QFont()
                f.setBold(True)
                items[0].setFont(f)
                items[0].setForeground(QColor("#ef4444"))
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, ev.get("id", ""))
                self.table.setItem(row, col, item)

    def _on_select(self):
        rows = self.table.selectedItems()
        if not rows:
            return
        event_id = rows[0].data(Qt.ItemDataRole.UserRole)
        if event_id:
            self.detail._loading()
            self.api_client.fetch_event_detail(event_id)

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._refresh()

    def _next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._refresh()

    def refresh(self):
        self._current_page = 1
        self._refresh()
