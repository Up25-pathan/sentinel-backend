import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QApplication
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from utils.api_client import SERVER_URL


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.token = None
        self._nam = QNetworkAccessManager(self)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("SENTINEL — Authentication Required")
        self.setFixedSize(400, 300)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        outer = QWidget()
        outer.setStyleSheet("""
            QDialog { background: #0f172a; }
            QLabel#title { color: #f59e0b; font-size: 18px; font-weight: bold; letter-spacing: 3px; }
            QLabel#subtitle { color: #475569; font-size: 9px; letter-spacing: 2px; }
            QLabel#server { color: #22d3ee; font-size: 8px; }
            QLineEdit {
                background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
                padding: 8px 12px; font-size: 12px; border-radius: 4px;
            }
            QLineEdit:focus { border-color: #f59e0b; }
            QPushButton {
                background: #f59e0b; color: #0f172a; font-weight: bold;
                padding: 8px; font-size: 12px; border-radius: 4px; letter-spacing: 2px;
            }
            QPushButton:hover { background: #d97706; }
            QPushButton:disabled { background: #334155; color: #64748b; }
            QLabel#error { color: #ef4444; font-size: 10px; }
        """)

        layout = QVBoxLayout(outer)
        layout.setContentsMargins(30, 30, 30, 20)
        layout.setSpacing(12)

        title = QLabel("SENTINEL CIC")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("COMMAND & CONTROL")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        server_lbl = QLabel(f"Server: {SERVER_URL.replace('https://','')}")
        server_lbl.setObjectName("server")
        server_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(server_lbl)

        layout.addSpacing(8)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.returnPressed.connect(lambda: self.password.setFocus())
        layout.addWidget(self.username)

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self._do_login)
        layout.addWidget(self.password)

        self.login_btn = QPushButton("AUTHENTICATE")
        self.login_btn.clicked.connect(self._do_login)
        layout.addWidget(self.login_btn)

        self.error_lbl = QLabel("")
        self.error_lbl.setObjectName("error")
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_lbl)

        layout.addStretch()

        ver = QLabel("v2.1.0 — STANDALONE BUILD")
        ver.setStyleSheet("color: #1e293b; font-size: 7px;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(outer)

        self.username.setFocus()

    def _do_login(self):
        user = self.username.text().strip()
        pw = self.password.text()
        if not user or not pw:
            self.error_lbl.setText("Enter username and password")
            return

        self.error_lbl.setText("Authenticating...")
        self.error_lbl.setStyleSheet("color: #22d3ee; font-size: 10px;")
        self.login_btn.setEnabled(False)

        url = QUrl(f"{SERVER_URL}/api/auth/login")
        req = QNetworkRequest(url)
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        body = json.dumps({"username": user, "password": pw}).encode()
        reply = self._nam.post(req, body)
        reply.finished.connect(lambda: self._on_login_reply(reply))

    def _on_login_reply(self, reply):
        self.login_btn.setEnabled(True)
        if reply.error() != QNetworkReply.NetworkError.NoError:
            err = reply.errorString()
            if "refused" in err.lower() or "unreachable" in err.lower() or "connection" in err.lower():
                self.error_lbl.setStyleSheet("color: #ef4444; font-size: 10px;")
                self.error_lbl.setText("Server unreachable")
            else:
                self.error_lbl.setStyleSheet("color: #ef4444; font-size: 10px;")
                self.error_lbl.setText(f"Connection error: {err[:50]}")
            reply.deleteLater()
            return

        try:
            data = json.loads(reply.readAll().data().decode("utf-8"))
        except json.JSONDecodeError:
            self.error_lbl.setStyleSheet("color: #ef4444; font-size: 10px;")
            self.error_lbl.setText("Invalid server response")
            reply.deleteLater()
            return

        if "token" in data and data["token"]:
            self.token = data["token"]
            reply.deleteLater()
            self.accept()
        else:
            self.error_lbl.setStyleSheet("color: #ef4444; font-size: 10px;")
            self.error_lbl.setText(data.get("error", "Authentication failed"))
            reply.deleteLater()
