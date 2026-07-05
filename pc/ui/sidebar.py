from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QScrollArea
from PyQt6.QtCore import Qt, pyqtSignal

NAV_ITEMS = [
    ("__group", None, "INTEL"),
    ("dashboard", "\u25B6", "DASH"),
    ("intel",     "\u2691", "INTL"),
    ("osint",     "\u2606", "OSNT"),
    ("darkweb",   "\u2622", "DWEB"),
    ("alerts",    "\u26A0", "ALRT"),
    ("__group", None, "ANALYSIS"),
    ("map",       "\u2630", "MAP"),
    ("chat",      "\u2709", "CHAT"),
    ("feeds",     "\u2690", "THRT"),
    ("timeline",  "\u29D6", "TIME"),
    ("__group", None, "OPS"),
    ("scanner",   "\u26ED", "SCAN"),
    ("vulndb",    "\u269B", "VULN"),
    ("assets",    "\u2699", "ASST"),
    ("export",    "\u21E9", "RPRT"),
    ("__group", None, "CMD"),
    ("redops",    "\u2694", "OPS"),
    ("campaign",  "\u269C", "CAMP"),
    ("audit",     "\u2693", "AUDT"),
]

TOOLTIPS = {
    "dashboard": "Dashboard",
    "intel": "Intel Events",
    "osint": "OSINT Feeds",
    "darkweb": "Dark Web",
    "alerts": "Alerts",
    "map": "Geo Map",
    "chat": "AI Chat",
    "feeds": "Threat Feeds",
    "timeline": "Timeline",
    "scanner": "Network Scanner",
    "vulndb": "Vuln Database",
    "assets": "Assets Tracker",
    "export": "Export / Reports",
    "redops": "Red Ops",
    "campaign": "Campaigns",
    "audit": "Audit Log",
}

class Sidebar(QWidget):
    navigationChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(68)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar:vertical { width: 0px; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("SNTL")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.buttons = {}
        self._group = []
        for key, icon, label in NAV_ITEMS:
            if key == "__group":
                sep = QLabel(label)
                sep.setObjectName("SidebarGroup")
                sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(sep)
                continue
            btn = QPushButton(f"{icon}{label}")
            btn.setToolTip(TOOLTIPS.get(key, ""))
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked, k=key: self._on_nav(k))
            layout.addWidget(btn)
            self.buttons[key] = btn
            self._group.append(btn)

        layout.addStretch()

        ver = QLabel("v2.1")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color: #1e293b; font-size: 6pt; padding: 6px 0px;")
        layout.addWidget(ver)

        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

    def _on_nav(self, key):
        for k, btn in self.buttons.items():
            btn.setChecked(k == key)
        self.navigationChanged.emit(key)

    def select(self, key):
        if key in self.buttons:
            self._on_nav(key)
