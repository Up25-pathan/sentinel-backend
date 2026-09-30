"""REDLAB application window and entry point.

REDLAB is a standalone app: python -m redlab. It shares only the shell chrome
and the audit log with SENTINEL CIC, and never opens the CIC panels.
"""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog

import redlab
from redlab.panels.assets import AssetsPanel
from redlab.panels.campaigns import CampaignsPanel
from redlab.panels.network_scanner import NetworkScannerPanel
from redlab.panels.redops import RedOpsPanel
from shell import ShellWindow, excepthook
from utils import audit
from utils.api_client import ApiClient, SERVER_URL


class RedLabWindow(ShellWindow):
    def __init__(self):
        super().__init__(
            title=redlab.__app_name__,
            version=redlab.__version__,
            nav_items=redlab.__nav_items__,
            nav_title="REDLAB",
            subtitle="OFFENSIVE OPS",
            client_factory=ApiClient,
        )
        audit.log_action("REDLAB_START", f"{redlab.__app_name__} v{redlab.__version__}")
        self.api_client.loginResult.connect(self._on_login)
        self._health_nam = None
        self._health_reply = None
        self.on_startup()

    def build_panels(self):
        self.panels = {
            "redops": RedOpsPanel(),
            "scanner": NetworkScannerPanel(),
            "campaign": CampaignsPanel(),
            "assets": AssetsPanel(),
        }
        self.panel_keys = list(redlab.__panel_keys__)
        for key in self.panel_keys:
            self.content.addWidget(self.panels[key])

    def on_startup(self):
        # REDLAB works against targets directly, so it does not require an
        # authenticated CIC session to be useful. It still reports backend
        # reachability so an operator knows whether audit events will persist.
        self.set_connection(False, "checking")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, self._check_server)

    def _on_login(self, ok, message):
        host = SERVER_URL.replace("https://", "").replace("http://", "")
        self.set_connection(ok, "" if ok else message)
        if ok:
            self._set_status("REDLAB ONLINE — AUDIT LOGGING ACTIVE")
        elif "connection" in message.lower() or "refused" in message.lower():
            self._set_status("BACKEND OFFLINE — LOCAL OPS UNAFFECTED", error=True)
        else:
            self._set_status(f"BACKEND AUTH: {message[:50]}", error=True)

    def _check_server(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
        if self._health_nam is None:
            self._health_nam = QNetworkAccessManager(self)
        self._health_timer = getattr(self, "_health_timer", None)
        request = QNetworkRequest(QUrl(f"{SERVER_URL}/api/health"))
        self._health_reply = self._health_nam.get(request)

        def done():
            reply = self._health_reply
            self._health_reply = None
            if reply is None:
                return
            try:
                if reply.error() == QNetworkReply.NetworkError.NoError:
                    self.set_connection(True)
                    self._set_status("REDLAB ONLINE — AUDIT LOGGING ACTIVE")
                else:
                    self.set_connection(False, reply.errorString()[:28])
                    self._set_status("BACKEND OFFLINE — LOCAL OPS UNAFFECTED", error=True)
            finally:
                reply.deleteLater()

        self._health_reply.finished.connect(done)

    def closeEvent(self, event):
        audit.log_action("REDLAB_STOP", "Red Lab closed")
        super().closeEvent(event)


def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    sys.excepthook = excepthook
    window = RedLabWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
