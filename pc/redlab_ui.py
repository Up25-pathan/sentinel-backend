"""SENTINEL CIC — intelligence and reporting console.

The reporting half of SENTINEL. CIC observes feeds, events and infrastructure
state and renders what the backend actually returns; it does not act against
targets. Offensive tooling lives in the separate REDLAB app.

Run it with:  python redlab_ui.py
"""

import os
import sys

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout, QWidget

import app_meta
from shell import ShellWindow, excepthook
from ui.panels.ai_chat import AIChatPanel
from ui.panels.alerts import AlertsPanel
from ui.panels.audit_log import AuditLogPanel
from ui.panels.dashboard import DashboardPanel
from ui.panels.darkweb import DarkWebPanel
from ui.panels.intel_events import IntelEventsPanel
from ui.panels.osint_feed import OSINTFeedPanel
from ui.panels.reports import ReportsPanel
from ui.panels.threat_feeds import ThreatFeedsPanel
from ui.panels.timeline_view import TimelinePanel
from ui.panels.vuln_db import VulnDBPanel
from utils import audit
from utils.api_client import ApiClient, SERVER_URL


class CicWindow(ShellWindow):
    def __init__(self):
        super().__init__(
            title=app_meta.__app_name__,
            version=app_meta.__version__,
            nav_items=app_meta.__nav_items__,
            nav_title="CIC",
            subtitle="INTEL",
            client_factory=ApiClient,
        )
        audit.log_action("GUI_START", f"{app_meta.__app_name__} v{app_meta.__version__}")
        self._health_nam = None
        self._health_reply = None
        self._wire_client()
        self.on_startup()

    def build_panels(self):
        client = self.api_client
        self.panels = {
            "dashboard": DashboardPanel(client),
            "intel": IntelEventsPanel(client),
            "osint": OSINTFeedPanel(client),
            "darkweb": DarkWebPanel(client),
            "alerts": AlertsPanel(client),
            "chat": AIChatPanel(client),
            "feeds": ThreatFeedsPanel(client),
            "timeline": TimelinePanel(client),
            "vulndb": VulnDBPanel(client),
            "export": ReportsPanel(client),
            "audit": AuditLogPanel(),
        }
        # The map is WebEngine-backed. On a host without a usable GPU or
        # display it can abort the process, so a failure here must degrade to a
        # placeholder rather than take the app down with it.
        self.panels["map"] = self._build_map(client)
        self.panel_keys = list(app_meta.__panel_keys__)
        for key in self.panel_keys:
            self.content.addWidget(self.panels[key])

    def _build_map(self, client):
        # QtWebEngine aborts the process on hosts with no usable GPU/display, and
        # a native abort cannot be caught by try/except. SENTINEL_DISABLE_WEBENGINE
        # lets a headless host (CI, a container, a remote shell) run the rest of
        # the app instead of dying at startup.
        if os.environ.get("SENTINEL_DISABLE_WEBENGINE"):
            return self._map_placeholder("disabled by SENTINEL_DISABLE_WEBENGINE")
        try:
            from ui.panels.geopolitical_map import GeopoliticalMapPanel
            return GeopoliticalMapPanel(client)
        except Exception as exc:  # noqa: BLE001
            print(f"Map panel unavailable: {exc}")
            return self._map_placeholder(str(exc))

    @staticmethod
    def _map_placeholder(reason):
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(24, 24, 24, 24)
        heading = QLabel("MAP UNAVAILABLE")
        heading.setStyleSheet("color: #f59e0b; font-size: 11pt; font-weight: 700;")
        detail = QLabel(
            "The map view needs QtWebEngine, which could not start on this host.\n"
            "Every other section is unaffected.\n\n"
            f"Reason: {reason}")
        detail.setStyleSheet("color: #475569; font-size: 9pt;")
        detail.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(detail)
        layout.addStretch()
        return placeholder

    def _wire_client(self):
        self.api_client.loginResult.connect(self._on_login)
        self.api_client.errorOccurred.connect(self._on_err)
        self.api_client.sseEvent.connect(self._on_sse_event)
        self.api_client.sseStatusChanged.connect(self._on_sse_status)

    def on_startup(self):
        self.set_connection(False, "checking")
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_server)
        self._health_timer.start(30000)
        QTimer.singleShot(300, self._check_server)
        QTimer.singleShot(500, self._show_login)

    def on_login(self, ok, message):
        pass

    # ── connection state ────────────────────────────────────────────
    def _on_login(self, ok, msg):
        self.set_connection(ok, "" if ok else msg)
        if ok:
            self._set_status("ALL SYSTEMS ONLINE")
            QTimer.singleShot(1000, self._start_sse)
        else:
            low = msg.lower()
            if any(word in low for word in ("refused", "unreachable", "timed out", "connection")):
                self._set_status("SERVER OFFLINE — CHECK DEPLOY", error=True)
                self.sse_label.setText("")
            else:
                self._set_status(f"AUTH FAILED — {msg[:40]}", error=True)
                self.sse_label.setText("CHECK SERVER LOGS")

    def _on_err(self, msg):
        if "Connection refused" in msg or "Host unreachable" in msg:
            self.set_connection(False, "unreachable")

    def _start_sse(self):
        try:
            self.api_client.connect_sse()
            self.sse_label.setText("SSE: CONNECTING")
        except Exception as exc:  # noqa: BLE001
            print(f"SSE start error: {exc}")

    def _on_sse_status(self, live):
        self.sse_label.setText("SSE: ● LIVE" if live else "SSE: ○ RECONNECT")
        self.sse_label.setStyleSheet(
            f"color: {'#22d3ee' if live else '#f59e0b'}; font-size: 7pt;")

    def _on_sse_event(self, event_type, data):
        if event_type != "connected":
            self._set_status(f"EVENT: {event_type}")

    def _check_server(self):
        if self._health_nam is None:
            self._health_nam = QNetworkAccessManager(self)
        self._health_reply = self._health_nam.get(QNetworkRequest(QUrl(f"{SERVER_URL}/api/health")))

        def done():
            reply = self._health_reply
            self._health_reply = None
            if reply is None:
                return
            try:
                if reply.error() == QNetworkReply.NetworkError.NoError:
                    self.set_connection(True)
                    if self.api_client.is_authenticated():
                        self._set_status("ALL SYSTEMS ONLINE")
                else:
                    self.set_connection(False, reply.errorString()[:28])
                    self._set_status(f"SRV OFFLINE — {reply.errorString()[:40]}", error=True)
            finally:
                reply.deleteLater()

        self._health_reply.finished.connect(done)

    def _show_login(self):
        from ui.login_dialog import LoginDialog
        dialog = LoginDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.api_client.token = dialog.token
            self._on_login(True, "Authenticated")
        else:
            QApplication.quit()

    def closeEvent(self, event):
        audit.log_action("GUI_STOP", "Sentinel CIC closed")
        super().closeEvent(event)


def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    sys.excepthook = excepthook
    window = CicWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
