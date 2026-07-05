import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QProgressBar, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from ui.sidebar import Sidebar
from ui.panels.dashboard import DashboardPanel
from ui.panels.intel_events import IntelEventsPanel
from ui.panels.osint_feed import OSINTFeedPanel
from ui.panels.darkweb import DarkWebPanel
from ui.panels.alerts import AlertsPanel
from ui.panels.geopolitical_map import GeopoliticalMapPanel
from ui.panels.redops import RedOpsPanel
from ui.panels.campaigns import CampaignsPanel
from ui.panels.audit_log import AuditLogPanel
from utils import audit, system_monitor
from utils.api_client import ApiClient

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SENTINEL CIC — v2.0")
        self.setGeometry(80, 40, 1800, 960)
        self.setMinimumSize(1400, 800)
        self._load_stylesheet()
        audit.log_action("GUI_START", "Sentinel CIC v2.0 Initialized")

        self.api_client = ApiClient()
        self._setup_tray()
        self._setup_ui()
        self._setup_monitor()
        self._connect_signals()
        self._auto_login()
        self._start_notification_poller()

    def _load_stylesheet(self):
        try:
            with open("ui/style.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Warning: ui/style.qss not found")

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("SENTINEL CIC")
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self.show)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activate)
        # Fallback icon — a small colored pixmap since we have no .ico
        icon = QIcon()
        pix = icon.pixmap(16, 16)
        if pix.isNull():
            from PyQt6.QtGui import QPixmap, QPainter, QColor
            p = QPixmap(16, 16)
            p.fill(QColor(245, 158, 11))
            icon = QIcon(p)
        self.tray.setIcon(icon)
        self.tray.show()
        self._last_alert_count = 0

    def _on_tray_activate(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    def _start_notification_poller(self):
        self.notify_timer = QTimer(self)
        self.notify_timer.timeout.connect(self._check_new_alerts)
        self.notify_timer.start(15000)

    def _check_new_alerts(self):
        if not self.api_client.is_authenticated():
            return
        self.api_client.fetch_alerts()

    def _on_alerts_for_notify(self, alerts):
        if not isinstance(alerts, list):
            return
        count = len(alerts)
        if count > self._last_alert_count:
            diff = count - self._last_alert_count
            recent = alerts[:diff]
            for alert in recent:
                msg = alert.get("message", alert.get("title", "New alert"))
                self.tray.showMessage(
                    "SENTINEL ALERT",
                    msg,
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000
                )
                audit.log_action("NOTIFICATION", msg)
        self._last_alert_count = count

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self._build_header(main)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = Sidebar()
        body.addWidget(self.sidebar)

        self.content = QStackedWidget()
        self.content.setObjectName("ContentArea")
        self._build_panels()
        body.addWidget(self.content, 1)
        main.addLayout(body, 1)

        self._build_status(main)

    def _build_header(self, parent):
        h = QWidget()
        h.setObjectName("HeaderBar")
        h.setFixedHeight(36)
        l = QHBoxLayout(h)
        l.setContentsMargins(8, 0, 8, 0)
        l.setSpacing(12)

        title = QLabel("SENTINEL CIC")
        title.setObjectName("HeaderTitle")
        l.addWidget(title)

        sep = QLabel("|")
        sep.setStyleSheet("color: #1e293b;")
        l.addWidget(sep)

        from utils.api_client import SERVER_URL as SRV
        self.conn_label = QLabel(f"SRV: \u26AA {SRV.replace('https://','').replace('http://','')}")
        self.conn_label.setStyleSheet("color: #475569; font-size: 8pt; letter-spacing: 1px;")
        l.addWidget(self.conn_label)

        self.sse_label = QLabel("")
        self.sse_label.setStyleSheet("color: #475569; font-size: 7pt;")
        l.addWidget(self.sse_label)

        l.addStretch()

        cpu_l = QLabel("CPU")
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFixedWidth(80)
        self.cpu_bar.setStyleSheet("QProgressBar::chunk { background-color: #22d3ee; }")
        mem_l = QLabel("MEM")
        self.mem_bar = QProgressBar()
        self.mem_bar.setFixedWidth(80)
        self.mem_bar.setStyleSheet("QProgressBar::chunk { background-color: #f59e0b; }")

        l.addWidget(cpu_l)
        l.addWidget(self.cpu_bar)
        l.addWidget(mem_l)
        l.addWidget(self.mem_bar)

        self.clock_label = QLabel("")
        self.clock_label.setStyleSheet("color: #475569; font-size: 8pt; letter-spacing: 1px;")
        l.addWidget(self.clock_label)

        parent.addWidget(h)

        self._update_clock()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

    def _update_clock(self):
        from datetime import datetime
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S UTC"))

    def _build_panels(self):
        self.panels = {}
        self.panels["dashboard"] = DashboardPanel(self.api_client)
        self.panels["intel"] = IntelEventsPanel(self.api_client)
        self.panels["osint"] = OSINTFeedPanel(self.api_client)
        self.panels["darkweb"] = DarkWebPanel(self.api_client)
        self.panels["alerts"] = AlertsPanel(self.api_client)
        self.panels["map"] = GeopoliticalMapPanel(self.api_client)
        self.panels["redops"] = RedOpsPanel()
        self.panels["campaign"] = CampaignsPanel()
        self.panels["audit"] = AuditLogPanel()

        self.panel_keys = ["dashboard", "intel", "osint", "darkweb", "alerts", "map", "redops", "campaign", "audit"]
        for key in self.panel_keys:
            self.content.addWidget(self.panels[key])

    def _build_status(self, parent):
        s = QWidget()
        s.setFixedHeight(24)
        l = QHBoxLayout(s)
        l.setContentsMargins(8, 0, 8, 0)
        l.setSpacing(12)
        self.status_label = QLabel("STANDBY")
        self.status_label.setStyleSheet("color: #475569; font-size: 7pt; letter-spacing: 1px;")
        l.addWidget(self.status_label)
        l.addStretch()
        ver = QLabel("v2.0.0 — CIC BUILD")
        ver.setStyleSheet("color: #1e293b; font-size: 7pt;")
        l.addWidget(ver)
        parent.addWidget(s)

    def _setup_monitor(self):
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._update_stats)
        self.monitor_timer.start(3000)

    def _update_stats(self):
        try:
            cpu = system_monitor.get_cpu_usage()
            mem = system_monitor.get_memory_usage()
            self.cpu_bar.setValue(int(cpu))
            self.mem_bar.setValue(int(mem))
        except:
            pass

    def _connect_signals(self):
        self.sidebar.navigationChanged.connect(self._on_nav)
        self.api_client.loginResult.connect(self._on_login)
        self.api_client.errorOccurred.connect(self._on_err)
        self.api_client.alertsDataReady.connect(self._on_alerts_for_notify)
        self.api_client.sseEvent.connect(self._on_sse_event)

    def _on_nav(self, key):
        if key in self.panels:
            self.content.setCurrentWidget(self.panels[key])
            self.status_label.setText(f"SECTION: {key.upper()}")
            if hasattr(self.panels[key], 'refresh'):
                self.panels[key].refresh()

    def _on_login(self, ok, msg):
        from utils.api_client import SERVER_URL as SRV
        short = SRV.replace('https://','').replace('http://','')
        if ok:
            self.conn_label.setText(f"\u25CF {short}")
            self.conn_label.setStyleSheet("color: #22d3ee; font-size: 8pt; letter-spacing: 1px;")
            self.status_label.setText("ALL SYSTEMS ONLINE")
            QTimer.singleShot(1000, self._start_sse)
        else:
            self.conn_label.setText(f"\u25CF {short}")
            self.conn_label.setStyleSheet("color: #ef4444; font-size: 8pt; letter-spacing: 1px;")
            self.status_label.setText("LOCAL MODE — SERVER DISCONNECTED")

    def _on_err(self, msg):
        from utils.api_client import SERVER_URL as SRV
        short = SRV.replace('https://','').replace('http://','')
        if "Connection refused" in msg or "Host unreachable" in msg:
            self.conn_label.setText(f"\u25CF {short}")
            self.conn_label.setStyleSheet("color: #ef4444; font-size: 8pt; letter-spacing: 1px;")

    def _start_sse(self):
        self.api_client.connect_sse()
        self.sse_label.setText("SSE: CONNECTING")

    def _on_sse_event(self, event_type, data):
        if event_type == "connected":
            self.sse_label.setText("SSE: \u25CF LIVE")
            self.sse_label.setStyleSheet("color: #22d3ee; font-size: 7pt;")
        elif event_type == "new_event":
            title = data.get("title", "Unknown event")
            risk = data.get("risk_level", "")
            if risk in ("CRITICAL", "HIGH") or data.get("is_breaking"):
                self.tray.showMessage(
                    "NEW EVENT",
                    f"[{risk}] {title}",
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000
                )
                audit.log_action("SSE_EVENT", f"[{risk}] {title}")
        elif event_type == "new_alert":
            msg = data.get("message", data.get("event_title", "New alert"))
            self.tray.showMessage(
                "SENTINEL ALERT",
                msg,
                QSystemTrayIcon.MessageIcon.Critical,
                5000
            )
            audit.log_action("SSE_ALERT", msg)

    def _auto_login(self):
        QTimer.singleShot(500, lambda: self.api_client.login())

    def closeEvent(self, event):
        self.tray.hide()
        event.accept()


if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
