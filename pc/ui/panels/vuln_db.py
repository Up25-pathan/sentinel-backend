from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QComboBox, QSplitter, QFrame, QTextEdit)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import QUrl
from utils.api_client import SERVER_URL
import json, random

SEVERITY_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f59e0b",
    "MEDIUM": "#22d3ee",
    "LOW": "#475569",
}

MOCK_VULNS = [
    {"cve_id": "CVE-2024-00001", "severity": "CRITICAL", "score": 9.8, "software": "Apache Log4j 2.x", "status": "Active", "date": "2024-01-15", "description": "Remote code execution in Log4j JNDI lookup feature. Unauthenticated attackers can execute arbitrary code by sending crafted log messages.", "affected_versions": "2.0 - 2.17.0", "exploit_status": "Weaponized", "related_intel": ["APT-42 activity spike detected", "Multiple ransomware groups adopting exploit"]},
    {"cve_id": "CVE-2024-00002", "severity": "CRITICAL", "score": 9.1, "software": "Windows Kerberos", "status": "Active", "date": "2024-02-03", "description": "Privilege escalation in Kerberos authentication protocol allowing domain admin compromise.", "affected_versions": "Windows Server 2019-2022", "exploit_status": "Active", "related_intel": ["State-sponsored actors exploiting in wild"]},
    {"cve_id": "CVE-2024-00003", "severity": "HIGH", "score": 8.7, "software": "OpenSSH 9.x", "status": "Active", "date": "2024-02-20", "description": "Pre-authentication double-free vulnerability in sshd allowing remote code execution.", "affected_versions": "9.0 - 9.6", "exploit_status": "Proof of Concept", "related_intel": []},
    {"cve_id": "CVE-2024-00004", "severity": "HIGH", "score": 8.3, "software": "Kubernetes kubelet", "status": "Patched", "date": "2024-03-01", "description": "Privilege escalation via kubelet API allowing node takeover.", "affected_versions": "1.24 - 1.28", "exploit_status": "Proof of Concept", "related_intel": ["Cloud security advisory published"]},
    {"cve_id": "CVE-2024-00005", "severity": "MEDIUM", "score": 6.5, "software": "PostgreSQL 16", "status": "Patched", "date": "2024-03-12", "description": "SQL injection via pg_catalog functions in specific configurations.", "affected_versions": "16.0 - 16.2", "exploit_status": "None", "related_intel": []},
    {"cve_id": "CVE-2024-00006", "severity": "CRITICAL", "score": 9.4, "software": "Fortinet FortiOS", "status": "Active", "date": "2024-03-28", "description": "Authentication bypass in SSL VPN portal allowing full device compromise.", "affected_versions": "7.0 - 7.4", "exploit_status": "Weaponized", "related_intel": ["Ransomware group actively exploiting Fortinet appliances"]},
    {"cve_id": "CVE-2024-00007", "severity": "HIGH", "score": 8.0, "software": "Linux Kernel 6.x", "status": "Active", "date": "2024-04-05", "description": "Use-after-free in netfilter subsystem allowing local privilege escalation.", "affected_versions": "6.0 - 6.8", "exploit_status": "Proof of Concept", "related_intel": []},
    {"cve_id": "CVE-2024-00008", "severity": "LOW", "score": 3.5, "software": "Node.js 20.x", "status": "Patched", "date": "2024-04-18", "description": "Denial of service via malformed HTTP/2 frames.", "affected_versions": "20.0 - 20.11", "exploit_status": "None", "related_intel": []},
    {"cve_id": "CVE-2024-00009", "severity": "HIGH", "score": 7.8, "software": "VMware ESXi 8.0", "status": "Active", "date": "2024-05-02", "description": "Heap overflow in virtual USB controller allowing guest-to-host escape.", "affected_versions": "8.0 U1 - U2", "exploit_status": "Weaponized", "related_intel": ["Vulnerability chained with VMSA-2024-0012 in targeted attacks"]},
    {"cve_id": "CVE-2024-00010", "severity": "MEDIUM", "score": 5.5, "software": "Redis 7.x", "status": "Patched", "date": "2024-05-14", "description": "Information disclosure via race condition in ACL parser.", "affected_versions": "7.0 - 7.2.4", "exploit_status": "None", "related_intel": []},
    {"cve_id": "CVE-2024-00011", "severity": "CRITICAL", "score": 9.9, "software": "Splunk Enterprise 9.x", "status": "Active", "date": "2024-05-30", "description": "Pre-auth remote code execution via Python code injection in search parser.", "affected_versions": "9.0 - 9.2.1", "exploit_status": "Active", "related_intel": ["Nation-state actors targeting SIEM platforms", "CISA adds to KEV catalog"]},
    {"cve_id": "CVE-2024-00012", "severity": "HIGH", "score": 7.5, "software": "Atlassian Confluence", "status": "Active", "date": "2024-06-10", "description": "Server-side template injection leading to remote code execution.", "affected_versions": "8.0 - 8.5.2", "exploit_status": "Proof of Concept", "related_intel": []},
    {"cve_id": "CVE-2024-00013", "severity": "MEDIUM", "score": 6.1, "software": "Docker Engine 24.x", "status": "Patched", "date": "2024-06-22", "description": "Container escape via malicious overlayfs mount.", "affected_versions": "24.0 - 24.0.7", "exploit_status": "Proof of Concept", "related_intel": []},
    {"cve_id": "CVE-2024-00014", "severity": "HIGH", "score": 8.8, "software": "Palo Alto PAN-OS", "status": "Active", "date": "2024-07-04", "description": "Command injection in management interface allowing firewall takeover.", "affected_versions": "10.0 - 11.1", "exploit_status": "Weaponized", "related_intel": ["Multiple APT groups scanning for vulnerable firewalls"]},
    {"cve_id": "CVE-2024-00015", "severity": "LOW", "score": 2.8, "software": "MySQL 8.x", "status": "Patched", "date": "2024-07-15", "description": "Minor information disclosure via timing side-channel in authentication.", "affected_versions": "8.0 - 8.3", "exploit_status": "None", "related_intel": []},
]


class VulnDBPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._vulns = []
        self._nam = QNetworkAccessManager(self)
        self._nam.finished.connect(self._on_network_reply)
        self._setup_ui()
        self._connect_signals()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("VULNERABILITY DATABASE")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search CVE, keyword...")
        self.search_input.setStyleSheet("background:#0a0c12; border:1px solid #1a1e2e; color:#cbd5e1; padding:6px 12px; font-size:9pt;")

        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        self.severity_filter.setStyleSheet("background:#0a0c12; border:1px solid #1a1e2e; color:#cbd5e1; padding:4px 8px; font-size:9pt;")

        self.search_btn = QPushButton("SEARCH")
        self.search_btn.setStyleSheet("background:#1a1e2e; color:#f59e0b; border:1px solid #f59e0b; padding:6px 18px; font-weight:700; letter-spacing:1px;")

        self.sync_btn = QPushButton("SYNC")
        self.sync_btn.setStyleSheet("background:#1a1e2e; color:#22d3ee; border:1px solid #22d3ee; padding:6px 18px; font-weight:700; letter-spacing:1px;")

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.severity_filter)
        toolbar.addWidget(self.search_btn)
        toolbar.addWidget(self.sync_btn)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        left = QWidget()
        lt = QVBoxLayout(left)
        lt.setContentsMargins(0, 0, 0, 0)
        lt.setSpacing(4)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["CVE ID", "Severity", "Score", "Affected Software", "Status", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setStyleSheet("""
            QTableWidget { background:#080a0e; border:1px solid #1a1e2e; color:#cbd5e1; font-size:8pt; }
            QTableWidget::item { padding:6px 8px; border-bottom:1px solid #1a1e2e; }
            QTableWidget::item:selected { background:#1a1e2e; color:#f59e0b; }
            QHeaderView::section { background:#0a0c12; color:#64748b; border:1px solid #1a1e2e; padding:6px 8px; font-size:7pt; font-weight:700; letter-spacing:1px; }
        """)
        self.table.itemSelectionChanged.connect(self._on_select)
        lt.addWidget(self.table, 1)

        splitter.addWidget(left)

        self.detail_panel = QWidget()
        self.detail_panel.setStyleSheet("background:#080a0e; border:1px solid #1a1e2e;")
        self._detail_layout = QVBoxLayout(self.detail_panel)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setSpacing(10)
        self._show_placeholder()
        splitter.addWidget(self.detail_panel)

        splitter.setSizes([450, 350])
        layout.addWidget(splitter, 1)

    def _connect_signals(self):
        self.search_btn.clicked.connect(self._filter)
        self.search_input.returnPressed.connect(self._filter)
        self.severity_filter.currentIndexChanged.connect(self._filter)
        self.sync_btn.clicked.connect(self._sync_from_server)

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

    def _filter(self):
        query = self.search_input.text().strip().lower()
        severity = self.severity_filter.currentText()
        filtered = []
        for v in self._vulns:
            if severity != "All" and v["severity"] != severity:
                continue
            if query:
                searchable = f"{v['cve_id']} {v['software']} {v['description']} {v.get('affected_versions', '')}".lower()
                if query not in searchable:
                    continue
            filtered.append(v)
        self._render_table(filtered)

    def _render_table(self, vulns):
        self.table.setRowCount(0)
        self.table.setRowCount(len(vulns))
        for row, v in enumerate(vulns):
            cve_item = QTableWidgetItem(v["cve_id"])
            cve_item.setData(Qt.ItemDataRole.UserRole, row)

            sev_item = QTableWidgetItem(v["severity"])
            sev_item.setForeground(QColor(SEVERITY_COLORS.get(v["severity"], "#64748b")))

            score_item = QTableWidgetItem(str(v["score"]))

            sw_item = QTableWidgetItem(v["software"])

            status_item = QTableWidgetItem(v["status"])
            if v["status"] == "Active":
                status_item.setForeground(QColor("#ef4444"))
            else:
                status_item.setForeground(QColor("#22d3ee"))

            date_item = QTableWidgetItem(v["date"])

            items = [cve_item, sev_item, score_item, sw_item, status_item, date_item]
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

    def _on_select(self):
        rows = self.table.selectedItems()
        if not rows:
            self._show_placeholder()
            return
        row_idx = rows[0].row()
        row_data = rows[0].data(Qt.ItemDataRole.UserRole)
        if row_data is None:
            return
        self._show_detail(self._vulns[row_data])

    def _show_detail(self, v):
        self._clear_detail()

        cve_lbl = QLabel(v["cve_id"])
        cve_lbl.setStyleSheet("font-size:16pt; font-weight:700; color:#f59e0b; letter-spacing:2px;")
        self._detail_layout.addWidget(cve_lbl)

        sev_lbl = QLabel(v["severity"])
        sc = SEVERITY_COLORS.get(v["severity"], "#64748b")
        sev_lbl.setStyleSheet(f"background:#1a1e2e; color:{sc}; padding:4px 12px; font-size:8pt; font-weight:700; letter-spacing:2px; border:1px solid {sc};")
        self._detail_layout.addWidget(sev_lbl)

        score_lbl = QLabel(f"CVSS Score: {v['score']}")
        score_lbl.setStyleSheet("color:#94a3b8; font-size:9pt; font-weight:600;")
        self._detail_layout.addWidget(score_lbl)

        desc_lbl = QLabel(v["description"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color:#cbd5e1; font-size:8pt; line-height:1.5;")
        self._detail_layout.addWidget(desc_lbl)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("border:1px solid #1a1e2e;")
        self._detail_layout.addWidget(sep1)

        aff_lbl = QLabel(f"<b style='color:#64748b;'>AFFECTED SOFTWARE:</b>  <span style='color:#cbd5e1;'>{v['software']}</span>")
        aff_lbl.setStyleSheet("font-size:8pt;")
        aff_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._detail_layout.addWidget(aff_lbl)

        vers_lbl = QLabel(f"<b style='color:#64748b;'>AFFECTED VERSIONS:</b>  <span style='color:#cbd5e1;'>{v.get('affected_versions', 'N/A')}</span>")
        vers_lbl.setStyleSheet("font-size:8pt;")
        vers_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._detail_layout.addWidget(vers_lbl)

        exploit_status = v.get("exploit_status", "None")
        esc = {"None": "#475569", "Proof of Concept": "#f59e0b", "Weaponized": "#ef4444", "Active": "#ef4444"}.get(exploit_status, "#64748b")
        expl_lbl = QLabel(f"<b style='color:#64748b;'>EXPLOIT STATUS:</b>  <span style='color:{esc};font-weight:700;'>{exploit_status}</span>")
        expl_lbl.setStyleSheet("font-size:8pt;")
        expl_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._detail_layout.addWidget(expl_lbl)

        related = v.get("related_intel", [])
        if related:
            sep2 = QFrame()
            sep2.setFrameShape(QFrame.Shape.HLine)
            sep2.setStyleSheet("border:1px solid #1a1e2e;")
            self._detail_layout.addWidget(sep2)

            rel_title = QLabel("RELATED INTEL EVENTS")
            rel_title.setStyleSheet("color:#22d3ee; font-size:7pt; font-weight:700; letter-spacing:2px;")
            self._detail_layout.addWidget(rel_title)

            for item in related:
                rel_item = QLabel(f"  \u25b8  {item}")
                rel_item.setStyleSheet("color:#94a3b8; font-size:8pt; padding-left:8px;")
                self._detail_layout.addWidget(rel_item)

        self._detail_layout.addStretch()

    def _sync_from_server(self):
        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("SYNCING...")
        url = QUrl(f"{SERVER_URL}/api/intelligence/vulns")
        req = QNetworkRequest(url)
        if self.api_client.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.api_client.token}".encode())
        self._nam.get(req)

    def _on_network_reply(self, reply):
        self.sync_btn.setEnabled(True)
        self.sync_btn.setText("SYNC")
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                data = json.loads(reply.readAll().data().decode())
                if isinstance(data, list):
                    self._vulns = data
                else:
                    self._vulns = data.get("vulns", data.get("results", []))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._load_mock()
        else:
            self._load_mock()
        self._filter()
        reply.deleteLater()

    def _load_mock(self):
        self._vulns = MOCK_VULNS[:]

    def refresh(self):
        self._sync_from_server()
