"""Vulnerability Database — live NVD CVE + CISA KEV data.

This panel previously carried a hardcoded list of 15 invented CVEs
(CVE-2024-00001 "Apache Log4j 2.x", and so on) and displayed it on *any* failure
of the request. The endpoint it called, /api/intelligence/vulns, did not exist,
so the fallback fired on 100% of runs and the panel showed fabricated
vulnerabilities permanently. There is no local data set here now: every row
comes from the server, and when the feed is unavailable the panel says so.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QComboBox, QSplitter, QFrame, QTextEdit, QCheckBox)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from utils.api_client import SERVER_URL
import json

SEVERITY_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f59e0b",
    "MEDIUM": "#22d3ee",
    "LOW": "#475569",
    "UNKNOWN": "#64748b",
}

PAGE_SIZE = 100


class VulnDBPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._vulns = []
        self._stats = None
        self._page = 1
        self._total = 0
        self._pages = 1
        self._last_error = None
        self._nam = QNetworkAccessManager(self)
        self._nam.finished.connect(self._on_network_reply)
        self._setup_ui()
        self._connect_signals()
        self.refresh()

    # ── UI ────────────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("VULNERABILITY DATABASE")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("NVD CVE 2.0  ·  CISA KNOWN EXPLOITED VULNERABILITIES")
        subtitle.setStyleSheet("color:#475569; font-size:7pt; letter-spacing:2px;")
        layout.addWidget(subtitle)

        self.summary = QLabel("")
        self.summary.setStyleSheet("color:#22d3ee; font-size:8pt; letter-spacing:1px;")
        layout.addWidget(self.summary)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search CVE, vendor, product, CWE...")
        self.search_input.setStyleSheet("background:#0a0c12; border:1px solid #1a1e2e; color:#cbd5e1; padding:6px 12px; font-size:9pt;")

        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"])
        self.severity_filter.setStyleSheet("background:#0a0c12; border:1px solid #1a1e2e; color:#cbd5e1; padding:4px 8px; font-size:9pt;")

        self.kev_only = QCheckBox("KEV ONLY")
        self.kev_only.setStyleSheet("color:#ef4444; font-size:8pt; letter-spacing:1px; spacing:6px;")

        self.search_btn = QPushButton("SEARCH")
        self.search_btn.setStyleSheet("background:#1a1e2e; color:#f59e0b; border:1px solid #f59e0b; padding:6px 18px; font-weight:700; letter-spacing:1px;")

        self.sync_btn = QPushButton("SYNC NVD + KEV")
        self.sync_btn.setStyleSheet("background:#1a1e2e; color:#22d3ee; border:1px solid #22d3ee; padding:6px 18px; font-weight:700; letter-spacing:1px;")
        self.sync_btn.setToolTip("Fetch the live CISA KEV catalog and recent NVD CVEs now")

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.severity_filter)
        toolbar.addWidget(self.kev_only)
        toolbar.addWidget(self.search_btn)
        toolbar.addWidget(self.sync_btn)
        layout.addLayout(toolbar)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#64748b; font-size:8pt; letter-spacing:1px;")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        left = QWidget()
        lt = QVBoxLayout(left)
        lt.setContentsMargins(0, 0, 0, 0)
        lt.setSpacing(4)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["CVE ID", "Severity", "CVSS", "Affected Software", "Exploit", "Published"])
        for col, mode in ((0, QHeaderView.ResizeMode.ResizeToContents),
                          (1, QHeaderView.ResizeMode.ResizeToContents),
                          (2, QHeaderView.ResizeMode.ResizeToContents),
                          (3, QHeaderView.ResizeMode.Stretch),
                          (4, QHeaderView.ResizeMode.ResizeToContents),
                          (5, QHeaderView.ResizeMode.ResizeToContents)):
            self.table.horizontalHeader().setSectionResizeMode(col, mode)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget { background:#080a0e; border:1px solid #1a1e2e; color:#cbd5e1; font-size:8pt; }
            QTableWidget::item { padding:6px 8px; border-bottom:1px solid #1a1e2e; }
            QTableWidget::item:selected { background:#1a1e2e; color:#f59e0b; }
            QHeaderView::section { background:#0a0c12; color:#64748b; border:1px solid #1a1e2e; padding:6px 8px; font-size:7pt; font-weight:700; letter-spacing:1px; }
        """)
        self.table.itemSelectionChanged.connect(self._on_select)
        lt.addWidget(self.table, 1)

        pager = QHBoxLayout()
        self.prev_btn = QPushButton("◀ PREV")
        self.next_btn = QPushButton("NEXT ▶")
        for b in (self.prev_btn, self.next_btn):
            b.setStyleSheet("background:#0a0c12; color:#94a3b8; border:1px solid #1a1e2e; padding:4px 12px; font-size:7pt; letter-spacing:1px;")
        self.page_lbl = QLabel("")
        self.page_lbl.setStyleSheet("color:#475569; font-size:7pt; letter-spacing:1px;")
        pager.addWidget(self.prev_btn)
        pager.addWidget(self.page_lbl)
        pager.addWidget(self.next_btn)
        pager.addStretch()
        lt.addLayout(pager)

        splitter.addWidget(left)

        self.detail_panel = QWidget()
        self.detail_panel.setStyleSheet("background:#080a0e; border:1px solid #1a1e2e;")
        self._detail_layout = QVBoxLayout(self.detail_panel)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setSpacing(10)
        self._show_placeholder()
        splitter.addWidget(self.detail_panel)

        splitter.setSizes([560, 380])
        layout.addWidget(splitter, 1)

    def _connect_signals(self):
        self.search_btn.clicked.connect(self.refresh)
        self.search_input.returnPressed.connect(self.refresh)
        self.search_input.textChanged.connect(self._debounce_search)
        self.severity_filter.currentIndexChanged.connect(self.refresh)
        self.kev_only.stateChanged.connect(self.refresh)
        self.sync_btn.clicked.connect(self._run_sync)
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
        self._search_timer = None

    def _debounce_search(self):
        from PyQt6.QtCore import QTimer
        if self._search_timer is None:
            self._search_timer = QTimer(self)
            self._search_timer.setSingleShot(True)
            self._search_timer.setInterval(400)
            self._search_timer.timeout.connect(self.refresh)
        self._search_timer.start()

    # ── Detail panel ──────────────────────────────────────────────────
    def _show_placeholder(self):
        self._clear_detail()
        lbl = QLabel("SELECT A VULNERABILITY TO VIEW DETAILS")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#475569; font-size:9pt; letter-spacing:1px; padding:40px;")
        self._detail_layout.addWidget(lbl)

    def _clear_detail(self):
        for i in reversed(range(self._detail_layout.count())):
            w = self._detail_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _field(self, label, value, color="#cbd5e1"):
        lbl = QLabel(f"<b style='color:#64748b;'>{label}</b>  <span style='color:{color};'>{value}</span>")
        lbl.setStyleSheet("font-size:8pt;")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._detail_layout.addWidget(lbl)

    def _show_detail(self, v):
        self._clear_detail()

        cve = v.get("cve_id", "UNKNOWN")
        cve_lbl = QLabel(cve)
        cve_lbl.setStyleSheet("font-size:16pt; font-weight:700; color:#f59e0b; letter-spacing:2px;")
        self._detail_layout.addWidget(cve_lbl)

        sev = (v.get("severity") or "UNKNOWN").upper()
        sc = SEVERITY_COLORS.get(sev, "#64748b")
        score = v.get("cvss_score")
        score_txt = f"{score:.1f}" if isinstance(score, (int, float)) else "NOT RATED"

        badges = QHBoxLayout()
        badges.setSpacing(6)
        for text, colour in ((sev, sc), (score_txt, sc),
                             (v.get("exploit_status") or "No Known Exploit",
                              "#ef4444" if v.get("in_kev") else "#64748b")):
            b = QLabel(text)
            b.setStyleSheet(f"background:#1a1e2e; color:{colour}; border:1px solid {colour};"
                            "font-size:7pt; font-weight:700; letter-spacing:1px; padding:3px 8px;")
            badges.addWidget(b)
        badges.addStretch()
        self._detail_layout.addLayout(badges)

        desc = (v.get("description") or "").strip()
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color:#cbd5e1; font-size:8pt;")
            self._detail_layout.addWidget(desc_lbl)

        def separator():
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("border:1px solid #1a1e2e;")
            self._detail_layout.addWidget(sep)

        separator()

        vendor = v.get("vendor") or "—"
        product = v.get("product") or "—"
        self._field("VENDOR:", vendor)
        self._field("PRODUCT:", product)
        if v.get("affected_versions"):
            self._field("AFFECTED VERSIONS:", v["affected_versions"])
        if v.get("cvss_vector"):
            self._field("CVSS VECTOR:", v["cvss_vector"], "#94a3b8")
        if v.get("cwes"):
            self._field("WEAKNESSES:", v["cwes"], "#a78bfa")
        if v.get("published"):
            self._field("PUBLISHED:", str(v["published"])[:19].replace("T", " "), "#94a3b8")
        if v.get("vuln_status"):
            self._field("NVD STATUS:", v["vuln_status"], "#94a3b8")

        if v.get("in_kev"):
            separator()
            kev_title = QLabel("CISA KNOWN EXPLOITED VULNERABILITY")
            kev_title.setStyleSheet("color:#ef4444; font-size:7pt; font-weight:700; letter-spacing:2px;")
            self._detail_layout.addWidget(kev_title)
            if v.get("kev_date_added"):
                self._field("DATE ADDED:", v["kev_date_added"], "#ef4444")
            if v.get("kev_due_date"):
                self._field("REMEDIATION DUE:", v["kev_due_date"], "#ef4444")
            if v.get("ransomware_use"):
                colour = "#ef4444" if v["ransomware_use"] == "Known" else "#94a3b8"
                self._field("RANSOMWARE USE:", v["ransomware_use"], colour)
            if v.get("required_action"):
                self._field("REQUIRED ACTION:", v["required_action"], "#fbbf24")

        refs = []
        if v.get("references_json"):
            try:
                refs = json.loads(v["references_json"])
            except (json.JSONDecodeError, TypeError):
                refs = []
        if refs:
            separator()
            rtitle = QLabel("REFERENCES")
            rtitle.setStyleSheet("color:#22d3ee; font-size:7pt; font-weight:700; letter-spacing:2px;")
            self._detail_layout.addWidget(rtitle)
            box = QTextEdit()
            box.setReadOnly(True)
            box.setPlainText("\n".join(refs[:12]))
            box.setStyleSheet("background:#0a0c12; border:1px solid #1a1e2e; color:#94a3b8; font-size:7pt;")
            box.setFixedHeight(110)
            self._detail_layout.addWidget(box)

        self._detail_layout.addStretch()

    # ── Table ─────────────────────────────────────────────────────────
    def _on_select(self):
        rows = self.table.selectedItems()
        if not rows:
            self._show_placeholder()
            return
        idx = rows[0].data(Qt.ItemDataRole.UserRole)
        if idx is None or not (0 <= idx < len(self._vulns)):
            self._show_placeholder()
            return
        self._show_detail(self._vulns[idx])

    def _render_table(self, vulns):
        self.table.setRowCount(0)
        self.table.setRowCount(len(vulns))
        for row, v in enumerate(vulns):
            cve_id = v.get("cve_id", "UNKNOWN")
            sev = (v.get("severity") or "UNKNOWN").upper()
            score = v.get("cvss_score")
            score_txt = f"{score:.1f}" if isinstance(score, (int, float)) else "—"

            vendor = (v.get("vendor") or "").strip()
            product = (v.get("product") or "").strip()
            software = " — ".join(p for p in (vendor, product) if p) or "—"

            exploit = "KEV" if v.get("in_kev") else (v.get("exploit_status") or "—")
            published = (v.get("published") or "")[:10]

            cve_item = QTableWidgetItem(cve_id)
            cve_item.setData(Qt.ItemDataRole.UserRole, row)
            if v.get("in_kev"):
                cve_item.setForeground(QColor("#ef4444"))
                cve_item.setToolTip("Confirmed exploited in the wild (CISA KEV)")

            sev_item = QTableWidgetItem(sev)
            sev_item.setForeground(QColor(SEVERITY_COLORS.get(sev, "#64748b")))

            score_item = QTableWidgetItem(score_txt)

            sw_item = QTableWidgetItem(software)
            sw_item.setToolTip(software)

            exploit_item = QTableWidgetItem(exploit)
            exploit_item.setForeground(QColor("#ef4444" if v.get("in_kev") else "#64748b"))

            date_item = QTableWidgetItem(published)

            for col, item in enumerate([cve_item, sev_item, score_item, sw_item, exploit_item, date_item]):
                self.table.setItem(row, col, item)

    def _update_summary(self, stats):
        if not stats:
            self.summary.setText("")
            return
        if not stats.get("configured"):
            self.summary.setText("NO VULNERABILITY DATA — the server has not completed its first NVD/KEV sync")
            return
        sev = stats.get("by_severity") or {}
        parts = [
            f"{stats.get('total', 0):,} CVEs",
            f"{sev.get('CRITICAL', 0)} CRITICAL",
            f"{sev.get('HIGH', 0)} HIGH",
            f"{stats.get('kev_count', 0):,} EXPLOITED IN THE WILD",
            f"{stats.get('kev_ransomware', 0):,} RANSOMWARE",
        ]
        self.summary.setText("  ·  ".join(parts))
        last = stats.get("last_nvd_sync") or stats.get("last_kev_sync")
        if last:
            self.summary.setToolTip(f"Last upstream sync: {last}")

    # ── Paging ────────────────────────────────────────────────────────
    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self.refresh()

    def _next_page(self):
        if self._page < self._pages:
            self._page += 1
            self.refresh()

    def _update_pager(self, total, page, limit):
        self._total = total or 0
        self._pages = max(1, -(-self._total // limit)) if limit else 1
        self._page = max(1, min(page or 1, self._pages))
        self.page_lbl.setText(f"PAGE {self._page} / {self._pages}   ·   {self._total:,} MATCHING")
        self.prev_btn.setEnabled(self._page > 1)
        self.next_btn.setEnabled(self._page < self._pages)

    # ── Networking ────────────────────────────────────────────────────
    def _authed_request(self, url):
        req = QNetworkRequest(url)
        req.setRawHeader(b"Accept", b"application/json")
        token = getattr(self.api_client, "token", None)
        if token:
            req.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        return req

    def refresh(self):
        if self._search_timer is not None:
            self._search_timer.stop()
        params = [f"page={self._page}", f"limit={PAGE_SIZE}"]
        sev = self.severity_filter.currentText()
        if sev and sev != "All":
            params.append(f"severity={sev}")
        if self.kev_only.isChecked():
            params.append("kev=1")
        query = self.search_input.text().strip()
        if query:
            from urllib.parse import quote
            params.append(f"q={quote(query)}")
        url = QUrl(f"{SERVER_URL}/api/intelligence/vulns?{'&'.join(params)}")
        self._nam.get(self._authed_request(url))

    def _run_sync(self):
        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("SYNCING...")
        self._set_status(
            "Contacting CISA KEV and NVD... the anonymous NVD limit is 5 requests "
            "per 30s, so this takes up to a couple of minutes.")
        url = QUrl(f"{SERVER_URL}/api/intelligence/vulns/sync")
        self._nam.post(self._authed_request(url), b"")

    def _on_network_reply(self, reply):
        reply_url = reply.url().toString()
        is_sync = reply_url.rstrip("/").endswith("/vulns/sync")
        try:
            if is_sync:
                self.sync_btn.setEnabled(True)
                self.sync_btn.setText("SYNC NVD + KEV")

            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._fail(reply.errorString(), is_sync)
                reply.deleteLater()
                return

            raw = reply.readAll().data()
            try:
                data = json.loads(raw.decode("utf-8", errors="replace"))
            except (json.JSONDecodeError, UnicodeDecodeError) as err:
                self._fail(f"malformed response ({err})", is_sync)
                reply.deleteLater()
                return

            if not isinstance(data, dict):
                self._fail("unexpected response shape", is_sync)
                reply.deleteLater()
                return

            if is_sync:
                stats = data.get("stats") or {}
                self._set_status(
                    f"Synced {data.get('kev', 0):,} KEV entries and "
                    f"{data.get('nvd', 0):,} NVD CVEs; "
                    f"{data.get('backfilled', 0):,} KEV rows scored.")
                self._update_summary(stats)
                self._page = 1
                self.refresh()
                reply.deleteLater()
                return

            vulns = data.get("vulns")
            if not isinstance(vulns, list):
                self._fail("response contained no vulnerability list", False)
                reply.deleteLater()
                return

            self._vulns = vulns
            self._stats = data.get("stats")
            self._update_summary(self._stats)
            self._update_pager(data.get("total", len(vulns)), data.get("page", 1), data.get("limit", PAGE_SIZE))
            self._render_table(vulns)
            self._show_placeholder()

            if not vulns:
                self._last_error = None
                if self._total == 0 and not (self._stats or {}).get("configured"):
                    self._set_status(
                        "No vulnerability data yet. The server syncs CISA KEV and NVD on boot "
                        "and daily at 03:23 UTC — use SYNC NVD + KEV to fetch now.")
                else:
                    self._set_status("No vulnerabilities match the current filter.")
            else:
                self._last_error = None
                self._set_status("")
        except Exception as err:  # noqa: BLE001 - surface, never fabricate
            self._fail(f"{type(err).__name__}: {err}", is_sync)
        finally:
            reply.deleteLater()

    def _set_status(self, text, error=False):
        self.status.setStyleSheet(
            "color:#ef4444; font-size:8pt; letter-spacing:1px;" if error
            else "color:#64748b; font-size:8pt; letter-spacing:1px;")
        self.status.setText(text)

    def _fail(self, message, is_sync):
        """Report the failure. Never substitute invented vulnerability data."""
        self._last_error = message
        self._set_status(f"{'Sync failed' if is_sync else 'Load failed'}: {message}", error=True)
        if not is_sync:
            self._vulns = []
            self._render_table([])
            self._show_placeholder()
            if self._total == 0:
                self.page_lbl.setText("NO DATA")
                self.prev_btn.setEnabled(False)
                self.next_btn.setEnabled(False)
