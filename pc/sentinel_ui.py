"""SENTINEL — single application for intelligence and offensive operations.

One window, one rail, one process. The intelligence panels and the offensive
tooling used to be two applications behind two entrypoints, which meant the
tooling looked absent whenever the wrong one was launched. They are now one
shell with a single grouped rail:

    INTEL / ANALYSIS / ASSURANCE   observe and report
    ENGAGE / OPERATE / PLAN        act against authorised targets, locally

The offensive panels run their job scripts as local subprocesses. Nothing in
this app executes against the server.

Run it with:

    python sentinel_ui.py
"""

import os
import sys

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QApplication, QDialog

import app_meta
import redlab
from redlab.panels.assets import AssetsPanel
from redlab.panels.campaigns import CampaignsPanel
from redlab.panels.network_scanner import NetworkScannerPanel
from redlab.panels.redops import RedOpsPanel
from redlab.panels.tools import ToolPanel
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

TOOL_BLURBS = {
    "recon": "Discovers live hosts, resolves DNS and probes open ports on a "
             "target you are authorised to assess.",
    "web": "Fetches a target over HTTP and reports the response, headers, TLS "
           "certificate and anything the page exposes.",
    "privesc": "Audits the local host for misconfiguration that would allow "
               "privilege escalation. Read-only: nothing is modified.",
    "osint": "Looks up WHOIS registration, DNS records and discoverable "
             "subdomains for a domain using public sources.",
    "wifi": "Inventories local wireless interfaces and the networks in range, "
            "as reported by the OS.",
    "exploit": "Identifies service banners and matches them against a CVE "
               "corpus to report exploitability. Authorised targets only. "
               "Assessment only — no payload is delivered or executed.",
}

TOOL_COLORS = {
    "recon": "#22d3ee", "web": "#f59e0b", "privesc": "#ef4444",
    "osint": "#22d3ee", "wifi": "#f59e0b", "exploit": "#ef4444",
}


class SentinelWindow(ShellWindow):
    def __init__(self):
        super().__init__(
            title=app_meta.__app_name__,
            version=app_meta.__version__,
            nav_items=app_meta.__nav_items__,
            nav_title="SNTL",
            subtitle="INTEL + OPS",
            client_factory=ApiClient,
        )
        audit.log_action("GUI_START", f"{app_meta.__app_name__} v{app_meta.__version__}")
        self._health_nam = None
        self._health_reply = None
        self._wire_client()
        self.on_startup()

    # ── panels ──────────────────────────────────────────────────────
    def build_panels(self):
        client = self.api_client

        panels = {
            # intelligence
            "dashboard": DashboardPanel(client),
            "intel": IntelEventsPanel(client),
            "osint_feed": OSINTFeedPanel(client),
            "darkweb": DarkWebPanel(client),
            "alerts": AlertsPanel(client),
            "chat": AIChatPanel(client),
            "feeds": ThreatFeedsPanel(client),
            "timeline": TimelinePanel(client),
            "vulndb": VulnDBPanel(client),
            "export": ReportsPanel(client),
            "audit": AuditLogPanel(),
        }

        map_panel = self._build_map(client)
        if map_panel is not None:
            panels["map"] = map_panel

        # Offensive tooling. Same definitions REDLAB used, so a tool behaves
        # identically whether it is reached from here or from python -m redlab.
        for key, (name, title, prompt, script, flag) in redlab.__tool_defs__.items():
            panels[key] = ToolPanel(
                key=key, name=name, title=title, prompt_label=prompt,
                script_name=script, accent=TOOL_COLORS[key],
                blurb=TOOL_BLURBS[key], value_flag=flag,
            )

        panels.update({
            "redops": RedOpsPanel(),
            "scanner": NetworkScannerPanel(),
            "campaign": CampaignsPanel(),
            "assets": AssetsPanel(),
        })

        self.panels = panels
        self.panel_keys = list(app_meta.__panel_keys__)
        missing = [key for key in self.panel_keys if key not in self.panels]
        if missing:
            raise RuntimeError(f"Rail lists panels that were never built: {missing}")
        for key in self.panel_keys:
            self.content.addWidget(self.panels[key])

    def _build_map(self, client):
        try:
            from ui.panels.geopolitical_map import GeopoliticalMapPanel
            return GeopoliticalMapPanel(client)
        except Exception as exc:  # noqa: BLE001
            print(f"Map panel unavailable: {exc}")
            return None

    def _wire_client(self):
        self.api_client.loginResult.connect(self._on_login)
        self.api_client.errorOccurred.connect(self._on_err)
        self.api_client.sseEvent.connect(self._on_sse_event)
        self.api_client.sseStatusChanged.connect(self._on_sse_status)

    # ── lifecycle ───────────────────────────────────────────────────
    def on_startup(self):
        self.set_connection(False, "checking")
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_server)
        self._health_timer.start(30000)
        QTimer.singleShot(300, self._check_server)
        QTimer.singleShot(500, self._show_login)

    def on_login(self, ok, message):
        pass

    def _on_login(self, ok, msg):
        self.set_connection(ok, "" if ok else msg)
        if ok:
            self._set_status("ALL SYSTEMS ONLINE")
            QTimer.singleShot(1000, self._start_sse)
            # Panels are built before the login dialog is answered, so their
            # first request went out unauthenticated and failed. Re-issue them
            # now that a token exists.
            QTimer.singleShot(400, self._refresh_panels)
        else:
            low = msg.lower()
            if any(w in low for w in ("refused", "unreachable", "timed out", "connection")):
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
        # Capture the reply in a local. Reading self._health_reply inside the
        # callback meant an overlapping tick could hand the callback a different
        # reply, or None, and leak the original as an unparented object.
        reply = self._health_nam.get(QNetworkRequest(QUrl(f"{SERVER_URL}/api/health")))
        self._health_reply = reply

        def done():
            if self._health_reply is reply:
                self._health_reply = None
            try:
                if reply.error() == QNetworkReply.NetworkError.NoError:
                    self.set_connection(True)
                    if self.api_client.is_authenticated():
                        self._set_status("ALL SYSTEMS ONLINE")
                elif reply.attribute(
                    QNetworkRequest.Attribute.HttpStatusCodeAttribute
                ) == 429:
                    self.set_connection(True)
                    self._set_status("RATE LIMITED — BACKING OFF", error=True)
                else:
                    self.set_connection(False, reply.errorString()[:28])
                    self._set_status(f"SRV OFFLINE — {reply.errorString()[:40]}", error=True)
            finally:
                reply.deleteLater()

        reply.finished.connect(done)

    def _show_login(self):
        from ui.login_dialog import LoginDialog
        dialog = LoginDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.api_client.token = dialog.token
            self._on_login(True, "Authenticated")
        else:
            QApplication.quit()

    def _refresh_panels(self):
        """Re-fetch every token-dependent panel once a token exists."""
        for panel in self.panels.values():
            if panel is None:
                continue
            refresh = getattr(panel, "refresh", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception as exc:  # noqa: BLE001
                    print(f"Panel refresh failed ({panel.__class__.__name__}): {exc}")

    def closeEvent(self, event):
        audit.log_action("GUI_STOP", f"{app_meta.__app_name__} closed")
        super().closeEvent(event)


def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    sys.excepthook = excepthook
    window = SentinelWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())