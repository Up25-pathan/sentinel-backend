import json
import time
import os
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import QUrl

SERVER_URL = os.getenv("SENTINEL_SERVER", "https://sentinel-backend-oc7g.onrender.com")

class ApiClient(QObject):
    dashboardDataReady = pyqtSignal(dict)
    eventsDataReady = pyqtSignal(dict)
    osintDataReady = pyqtSignal(dict)
    darkwebDataReady = pyqtSignal(dict)
    alertsDataReady = pyqtSignal(list)
    breakingEventsReady = pyqtSignal(list)
    eventDetailReady = pyqtSignal(dict)
    loginResult = pyqtSignal(bool, str)
    errorOccurred = pyqtSignal(str)
    sseEvent = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        self.nam = QNetworkAccessManager()
        self.nam.finished.connect(self._on_reply)
        self.token = None
        self._pending = {}
        self._sse_buffer = ""
        self._sse_timer = QTimer(self)
        self._sse_timer.timeout.connect(self._connect_sse_internal)
        self._sse_active = False

    def login(self, username="admin", password="intel2024"):
        url = QUrl(f"{SERVER_URL}/api/auth/login")
        req = QNetworkRequest(url)
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        body = json.dumps({"username": username, "password": password}).encode()
        reply = self.nam.post(req, body)
        self._pending[id(reply)] = ("login", None)

    def connect_sse(self):
        if self._sse_active:
            return
        self._sse_active = True
        self._connect_sse_internal()

    def _connect_sse_internal(self):
        url = QUrl(f"{SERVER_URL}/api/events/stream")
        req = QNetworkRequest(url)
        if self.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.token}".encode())
        req.setRawHeader(b"Accept", b"text/event-stream")
        reply = self.nam.get(req)
        self._pending[id(reply)] = ("sse", None)
        reply.readyRead.connect(lambda: self._on_sse_data(reply))

    def _on_sse_data(self, reply):
        try:
            chunk = reply.readAll().data().decode("utf-8")
            self._sse_buffer += chunk
            while "\n\n" in self._sse_buffer:
                block, self._sse_buffer = self._sse_buffer.split("\n\n", 1)
                lines = block.strip().split("\n")
                event_type = "message"
                data_str = ""
                for line in lines:
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        data_str = line[6:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        self.sseEvent.emit(event_type, data)
                    except json.JSONDecodeError:
                        pass
        except RuntimeError:
            pass

    def fetch_dashboard(self):
        self._get("/api/intelligence/dashboard", "dashboard")

    def fetch_events(self, page=1, limit=20, category=None, risk_level=None):
        params = f"page={page}&limit={limit}"
        if category: params += f"&category={category}"
        if risk_level: params += f"&risk_level={risk_level}"
        self._get(f"/api/events?{params}", "events")

    def fetch_breaking_events(self):
        self._get("/api/events/breaking", "breaking")

    def fetch_osint(self, page=1, platform=None, limit=20):
        params = f"page={page}&limit={limit}"
        if platform: params += f"&platform={platform}"
        self._get(f"/api/osint?{params}", "osint")

    def fetch_darkweb(self, limit=50, category=None, threat_level=None):
        params = f"limit={limit}"
        if category: params += f"&category={category}"
        if threat_level: params += f"&threat_level={threat_level}"
        self._get(f"/api/darkweb?{params}", "darkweb")

    def fetch_alerts(self):
        self._get("/api/alerts?unread_only=1", "alerts")

    def fetch_event_detail(self, event_id):
        self._get(f"/api/events/{event_id}", f"event_detail:{event_id}")

    def fetch_map_markers(self):
        self._get("/api/map/markers", "map_markers")

    def fetch_intel_summary(self):
        self._get("/api/intelligence/summary", "intel_summary")

    def fetch_macro_briefing(self):
        self._get("/api/intelligence/macro", "macro_briefing")

    def seed_database(self):
        self._post("/api/seed", {}, "seed")

    def _get(self, path, tag):
        url = QUrl(f"{SERVER_URL}{path}")
        req = QNetworkRequest(url)
        if self.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.token}".encode())
        reply = self.nam.get(req)
        self._pending[id(reply)] = (tag, None)

    def _post(self, path, body_dict, tag):
        url = QUrl(f"{SERVER_URL}{path}")
        req = QNetworkRequest(url)
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        if self.token:
            req.setRawHeader(b"Authorization", f"Bearer {self.token}".encode())
        body = json.dumps(body_dict).encode()
        reply = self.nam.post(req, body)
        self._pending[id(reply)] = (tag, None)

    def _on_reply(self, reply):
        reply_id = id(reply)
        tag, extra = self._pending.pop(reply_id, (None, None))
        if tag is None:
            reply.deleteLater()
            return

        if tag == "sse":
            self._sse_active = False
            reply.deleteLater()
            QTimer.singleShot(5000, self.connect_sse)
            return

        if reply.error() != QNetworkReply.NetworkError.NoError:
            error_msg = reply.errorString()
            if tag not in ("login", "sse"):
                self.errorOccurred.emit(f"API error ({tag}): {error_msg}")
            elif tag == "login":
                self.loginResult.emit(False, error_msg)
            reply.deleteLater()
            return

        data = reply.readAll().data().decode("utf-8")
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            if tag != "sse":
                self.errorOccurred.emit(f"JSON parse error ({tag}): {e}")
            reply.deleteLater()
            return

        if tag == "login":
            if "token" in parsed:
                self.token = parsed["token"]
                self.loginResult.emit(True, "Authenticated")
            else:
                self.loginResult.emit(False, parsed.get("error", "Login failed"))
        elif tag == "dashboard":
            self.dashboardDataReady.emit(parsed)
        elif tag == "events":
            self.eventsDataReady.emit(parsed)
        elif tag == "breaking":
            self.breakingEventsReady.emit(parsed.get("events", []))
        elif tag == "osint":
            self.osintDataReady.emit(parsed)
        elif tag == "darkweb":
            self.darkwebDataReady.emit(parsed)
        elif tag == "alerts":
            alerts = parsed if isinstance(parsed, list) else parsed.get("alerts", [])
            self.alertsDataReady.emit(alerts)
        elif tag == "map_markers":
            self.dashboardDataReady.emit({"map_markers": parsed.get("markers", [])})
        elif tag and tag.startswith("event_detail:"):
            self.eventDetailReady.emit(parsed)
        elif tag == "seed":
            pass

        reply.deleteLater()

    def is_authenticated(self):
        return self.token is not None
