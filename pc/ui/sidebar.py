from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

NAV_ITEMS = [
    ("dashboard", "DASH"),
    ("intel",     "INTL"),
    ("osint",     "OSNT"),
    ("darkweb",   "DWEB"),
    ("alerts",    "ALRT"),
    ("map",       "MAP"),
    ("chat",      "CHAT"),
    ("export",    "RPRT"),
    ("redops",    "OPS"),
    ("campaign",  "CAMP"),
    ("audit",     "AUDT"),
]

class Sidebar(QWidget):
    navigationChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(80)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("SNTL")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.buttons = {}
        self._group = []
        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda checked, k=key: self._on_nav(k))
            layout.addWidget(btn)
            self.buttons[key] = btn
            self._group.append(btn)

        layout.addStretch()

        ver = QLabel("v2.0")
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
