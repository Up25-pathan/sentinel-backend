from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve

NAV_ITEMS = [
    ("dashboard", "\u25B6", "DASH", "Dashboard"),
    ("intel",     "\u2691", "INTL", "Intel Events"),
    ("osint",     "\u2606", "OSNT", "OSINT Feeds"),
    ("darkweb",   "\u2622", "DWEB", "Dark Web"),
    ("alerts",    "\u26A0", "ALRT", "Alerts"),
    ("map",       "\u2630", "MAP",  "Geo Map"),
    ("chat",      "\u2709", "CHAT", "AI Chat"),
    ("feeds",     "\u2690", "THRT", "Threat Feeds"),
    ("timeline",  "\u29D6", "TIME", "Timeline"),
    ("scanner",   "\u26ED", "SCAN", "Scanner"),
    ("vulndb",    "\u269B", "VULN", "Vuln DB"),
    ("assets",    "\u2699", "ASST", "Assets"),
    ("export",    "\u21E9", "RPRT", "Export"),
    ("redops",    "\u2694", "OPS",  "Red Ops"),
    ("campaign",  "\u269C", "CAMP", "Campaigns"),
    ("audit",     "\u2693", "AUDT", "Audit"),
]

class Sidebar(QWidget):
    navigationChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(76)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("SNTL")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.buttons = {}
        self._group = []
        for key, icon, label, tooltip in NAV_ITEMS:
            btn = QPushButton(f"{icon}  {label}")
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda checked, k=key: self._on_nav(k))
            layout.addWidget(btn)
            self.buttons[key] = btn
            self._group.append(btn)

        layout.addStretch()

        ver = QLabel("v2.1")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color: #1e293b; font-size: 7pt; padding: 8px 0px;")
        layout.addWidget(ver)

    def _on_nav(self, key):
        for k, btn in self.buttons.items():
            btn.setChecked(k == key)
        self.navigationChanged.emit(key)

    def select(self, key):
        if key in self.buttons:
            self._on_nav(key)
