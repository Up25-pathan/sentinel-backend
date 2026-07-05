from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import QUrl
from utils.api_client import SERVER_URL
import json

class ChatBubble(QFrame):
    def __init__(self, role, text):
        super().__init__()
        self.setObjectName("ChatBubble")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        role_color = "#22d3ee" if role == "AI" else "#f59e0b"
        role_label = QLabel(role)
        role_label.setStyleSheet(f"font-size:7pt; font-weight:700; color:{role_color}; letter-spacing:1px;")
        layout.addWidget(role_label)

        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size:9pt; color:#cbd5e1;")
        layout.addWidget(msg)


class AIChatPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._nam = QNetworkAccessManager(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("AI Intelligence Chat")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel("Ask questions about global geopolitical events, threats, and intelligence")
        subtitle.setStyleSheet("color:#475569; font-size:8pt;")
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("ChatScroll")
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(6)
        self.chat_layout.addStretch()
        scroll.setWidget(self.chat_container)
        layout.addWidget(scroll, 1)

        input_area = QHBoxLayout()
        input_area.setSpacing(6)
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Ask about events, predictions, threats...")
        self.input_field.setMaximumHeight(60)
        self.input_field.setMinimumHeight(40)
        self.send_btn = QPushButton("SEND")
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._send_message)
        input_area.addWidget(self.input_field, 1)
        input_area.addWidget(self.send_btn)
        layout.addLayout(input_area)

        self._add_message("AI", "Connected. Ask me about geopolitical intelligence.")

    def _add_message(self, role, text):
        bubble = ChatBubble(role, text)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        parent = self.chat_container.parent()
        if isinstance(parent, QScrollArea):
            parent.verticalScrollBar().setValue(parent.verticalScrollBar().maximum())

    def _send_message(self):
        question = self.input_field.toPlainText().strip()
        if not question:
            return

        self._add_message("YOU", question)
        self.input_field.clear()
        self.send_btn.setEnabled(False)
        self.send_btn.setText("...")

        try:
            url = QUrl(f"{SERVER_URL}/api/intelligence/chat")
            req = QNetworkRequest(url)
            req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
            if self.api_client.token:
                req.setRawHeader(b"Authorization", f"Bearer {self.api_client.token}".encode())
            body = json.dumps({"question": question}).encode()
            reply = self._nam.post(req, body)
            reply.finished.connect(lambda r=reply: self._on_response(r))
        except Exception as e:
            self._add_message("AI", f"Error: {e}")
            self.send_btn.setEnabled(True)
            self.send_btn.setText("SEND")

    def _on_response(self, reply):
        self.send_btn.setEnabled(True)
        self.send_btn.setText("SEND")

        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = json.loads(reply.readAll().data().decode())
            answer = data.get("response") or data.get("answer") or data.get("text") or json.dumps(data)
            self._add_message("AI", answer)
        else:
            self._add_message("AI", f"API error: {reply.errorString()}")

        reply.deleteLater()

    def refresh(self):
        pass
