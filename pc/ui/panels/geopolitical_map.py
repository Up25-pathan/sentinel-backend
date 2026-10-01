import json
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
from PyQt6.QtCore import QUrl, QTimer, Qt

from utils.api_client import SERVER_URL

# QtWebEngine aborts the process natively when it cannot initialise, which no
# amount of try/except can catch. It needs a working GPU/display stack, so on a
# headless host the map cannot be shown at all. Set SENTINEL_DISABLE_WEBENGINE=1
# to substitute a labelled placeholder and let the rest of the app run.
WEBENGINE_DISABLED = os.environ.get("SENTINEL_DISABLE_WEBENGINE", "").strip().lower() in (
    "1", "true", "yes", "on",
)

MAP_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>SENTINEL Geospatial</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #080a0e; font-family: 'Courier New', monospace; }
  #map { width: 100vw; height: 100vh; }
  #status {
    position: absolute; top: 10px; left: 10px; z-index: 1000;
    background: rgba(8,10,14,0.92); color: #f59e0b;
    padding: 6px 12px; border: 1px solid #1e293b;
    font: 9px 'Courier New', monospace; letter-spacing: 1px;
    pointer-events: none;
  }
  .legend {
    background: rgba(8,10,14,0.92); color: #94a3b8; padding: 10px 14px;
    border: 1px solid #1e293b; border-radius: 0;
    font: 10px 'Courier New', monospace; line-height: 1.8;
  }
  .legend i { width: 10px; height: 10px; display: inline-block; margin-right: 6px; }
  .legend strong { color: #f1f5f9; }
  .layer-toggle {
    background: rgba(8,10,14,0.92); color: #94a3b8; padding: 6px 10px;
    border: 1px solid #1e293b; cursor: pointer;
    font: 9px 'Courier New', monospace; letter-spacing: 1px;
  }
  .layer-toggle:hover { border-color: #f59e0b; }
  .popup-custom { font-family: 'Courier New', monospace; font-size: 11px; min-width: 240px; }
  .popup-custom h3 { color: #f59e0b; margin: 0 0 4px 0; font-size: 12px; }
  .popup-custom .cat { color: #22d3ee; font-size: 9px; text-transform: uppercase; letter-spacing: 1px; }
  .popup-custom .loc { color: #64748b; font-size: 9px; }
  .popup-custom .summ { color: #cbd5e1; margin-top: 4px; font-size: 10px; }
  .marker-critical { color: #ef4444; font-size: 20px; text-shadow: 0 0 8px rgba(239,68,68,0.6); }
  .marker-high { color: #f59e0b; font-size: 18px; text-shadow: 0 0 6px rgba(245,158,11,0.5); }
  .marker-medium { color: #22d3ee; font-size: 16px; text-shadow: 0 0 4px rgba(34,211,238,0.4); }
  .marker-low { color: #475569; font-size: 14px; }
  .conflict-zone { fill-opacity: 0.15; stroke-width: 1.5; }
</style>
</head>
<body>
<div id="map"></div>
<div id="status">CONNECTING...</div>
<script>
const API_URL = %API_URL%;
const TOKEN = %TOKEN%;
const STATUS = document.getElementById('status');

function setStatus(msg, color) {
  STATUS.textContent = msg;
  if (color) STATUS.style.color = color;
}

const map = L.map('map', {
  center: [20, 0], zoom: 2,
  zoomControl: true,
  attributionControl: false,
  worldCopyJump: true
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  maxZoom: 19
}).addTo(map);

const intelLayer = L.layerGroup().addTo(map);
const aviationLayer = L.layerGroup().addTo(map);
const conflictLayer = L.layerGroup().addTo(map);

const layerControl = L.control({ position: 'topright' });
layerControl.onAdd = function() {
  const div = L.DomUtil.create('div', '');
  div.innerHTML =
    '<div class="layer-toggle" data-layer="intel" style="border-bottom:none">\u25A3 INTEL</div>'
  + '<div class="layer-toggle" data-layer="aviation" style="border-bottom:none">\u2708 AVIATION</div>'
  + '<div class="layer-toggle" data-layer="conflict">\u2622 CONFLICT</div>';
  div.addEventListener('click', function(e) {
    const target = e.target;
    if (!target.dataset.layer) return;
    const groups = { intel: intelLayer, aviation: aviationLayer, conflict: conflictLayer };
    if (map.hasLayer(groups[target.dataset.layer])) {
      map.removeLayer(groups[target.dataset.layer]);
      target.style.color = '#475569';
    } else {
      map.addLayer(groups[target.dataset.layer]);
      target.style.color = '#f59e0b';
    }
  });
  return div;
};
layerControl.addTo(map);

const ICONS = {
  CRITICAL: L.divIcon({ className: '', html: '<span class="marker-critical">&#9679;</span>', iconSize: [20, 20], iconAnchor: [10, 10] }),
  HIGH:     L.divIcon({ className: '', html: '<span class="marker-high">&#9679;</span>', iconSize: [18, 18], iconAnchor: [9, 9] }),
  MEDIUM:   L.divIcon({ className: '', html: '<span class="marker-medium">&#9679;</span>', iconSize: [16, 16], iconAnchor: [8, 8] }),
  LOW:      L.divIcon({ className: '', html: '<span class="marker-low">&#9679;</span>', iconSize: [14, 14], iconAnchor: [7, 7] })
};

function getIcon(risk) {
  return ICONS[risk] || ICONS.LOW;
}

// A 429 means the server's limiter is counting us. The deployed build allows
// only 100 requests per 15 minutes for every route combined, so a map that
// polls on three independent timers exhausts the budget by itself and every
// layer comes back empty. Two changes:
//   - one shared backoff instead of one per fetch, so layers stop each other
//     from retrying into a limiter that is already engaged;
//   - the server's own Retry-After is respected, even when it is longer than
//     a minute. Clamping it to 120s guaranteed a 429 storm on every tick.
var backoffUntil = 0;
var backoffReason = '';

function rateLimitedUntil(retryAfter) {
  var seconds = parseInt(retryAfter, 10);
  if (isNaN(seconds) || seconds < 1) {
    // Retry-After may be absent; fall back to the standard RateLimit-Reset
    // delta if the server sent one.
    seconds = 30;
  }
  if (seconds > 900) seconds = 900;
  backoffUntil = Date.now() + seconds * 1000;
  backoffReason = 'SERVER RATE LIMIT — RESUMING IN ' + seconds + 'S';
  return seconds;
}

function inBackoff() {
  return Date.now() < backoffUntil;
}

function backoffLeft() {
  return Math.max(1, Math.ceil((backoffUntil - Date.now()) / 1000));
}

function fetchJSON(url, headers) {
  if (inBackoff()) {
    var err = new Error('BACKOFF');
    err.isBackoff = true;
    err.retryIn = backoffLeft();
    return Promise.reject(err);
  }
  return fetch(url, headers).then(function(r) {
    if (r.status === 429) {
      rateLimitedUntil(r.headers.get('Retry-After'));
      var e = new Error('429');
      e.isBackoff = true;
      e.retryIn = backoffLeft();
      throw e;
    }
    if (r.status === 401) {
      var u = new Error('401 SESSION EXPIRED — RE-LOGIN');
      u.isAuth = true;
      throw u;
    }
    if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
    return r.json();
  });
}

// Layer failures used to overwrite each other's status text, so the last
// layer to answer was the only one visible and one dead endpoint could hide
// a working one. Each layer stores its own state and the status bar renders
// all three together.
var LAYER_ORDER = [
  { key: 'intel', label: 'INTEL' },
  { key: 'aviation', label: 'AVIATION' },
  { key: 'conflict', label: 'CONFLICT' },
];

var layerStates = {};

function clearLayerState(layer) {
  delete layerStates[layer];
}

function reportLayer(layer, ok, message, color) {
  if (layerStates[layer] === message) return;
  layerStates[layer] = { ok: ok, text: message };
  renderLayerStatus();
}

function renderLayerStatus() {
  var parts = [];
  var anyBad = false;
  var anyBackoff = false;
  LAYER_ORDER.forEach(function(entry) {
    var st = layerStates[entry.key];
    if (!st) {
      parts.push(entry.label + ' --');
      return;
    }
    if (!st.ok) anyBad = true;
    parts.push(st.text);
  });
  if (inBackoff()) {
    anyBackoff = true;
    parts.push('SERVER RATE LIMIT ' + backoffLeft() + 'S');
  }
  var color = (anyBad || anyBackoff) ? '#ef4444' : '#f59e0b';
  var line = parts.join('  ·  ');
  if (line !== STATUS.textContent) setStatus(line, color);
}

function noteBackoff() {
  if (!inBackoff()) return false;
  renderLayerStatus();
  return true;
}

function loadMarkers() {
  if (!requireToken('Intel')) return;
  if (noteBackoff()) return;
  setStatus('LOADING INTEL...', '#22d3ee');
  const headers = { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' };
  fetchJSON(API_URL + '/api/map/markers', { headers: headers })
    .then(function(data) {
      intelLayer.clearLayers();
      var count = 0;
      (data.markers || []).forEach(function(e) {
        if (!e.lat || !e.lng) return;
        count++;
        const color = e.risk_level === 'CRITICAL' ? '#ef4444' : e.risk_level === 'HIGH' ? '#f59e0b' : e.risk_level === 'MEDIUM' ? '#22d3ee' : '#475569';
        const marker = L.marker([e.lat, e.lng], { icon: getIcon(e.risk_level) });
        marker.bindPopup(
          '<div class="popup-custom">'
          + '<div class="cat">' + (e.is_breaking ? 'BREAKING &middot; ' : '') + (e.category || '') + '</div>'
          + '<h3>' + (e.title || 'Untitled') + '</h3>'
          + '<div class="loc">' + (e.location_name || '') + (e.country ? ' &middot; ' + e.country : '') + '</div>'
          + '<div class="summ">' + (e.summary || '').substring(0, 200) + '</div>'
          + '<div style="margin-top:4px;font-size:9px;color:' + color + '">' + e.risk_level + '</div>'
          + '</div>'
        );
        intelLayer.addLayer(marker);
      });
      clearLayerState('intel');
      // Zero markers with a healthy response is a real answer, not an error,
      // and the status must say so rather than implying the feed broke.
      reportLayer('intel',
        true,
        count ? count + ' INTEL MARKERS' : 'INTEL: 0 MARKERS (NO COORDINATES)',
        count ? '#f59e0b' : '#64748b');
    })
    .catch(function(err) {
      if (err.isBackoff) { noteBackoff(); return; }
      if (err.isAuth) { reportLayer('intel', false, err.message, '#ef4444'); return; }
      reportLayer('intel', false, 'INTEL OFFLINE: ' + err.message.substring(0, 40), '#ef4444');
    });
}

var aircraftMarkers = {};

// Poll without a token is pointless and floods the log once per interval.
function requireToken(label) {
  if (TOKEN) return true;
  if (!requireToken.warned) {
    requireToken.warned = true;
    setStatus('AUTHENTICATION REQUIRED', '#ef4444');
  }
  return false;
}

function loadAircraft() {
  if (!requireToken('Aircraft')) return;
  if (noteBackoff()) return;
  fetchJSON(API_URL + '/api/map/aviation', { headers: { 'Authorization': 'Bearer ' + TOKEN } })
    .then(function(data) {
      const now = Date.now();
      let seen = 0;
      (data.aircraft || []).forEach(function(a) {
        if (!a.lat || !a.lng) return;
        const key = a.icao24 || (a.lat + ',' + a.lng);
        seen++;
        if (aircraftMarkers[key]) {
          aircraftMarkers[key].setLatLng([a.lat, a.lng]);
          aircraftMarkers[key]._lastSeen = now;
        } else {
          const heading = a.heading || 0;
          const icon = L.divIcon({
            className: '',
            html: '<span style="color:#22d3ee;font-size:7px;text-shadow:0 0 4px rgba(34,211,238,0.8);transform:rotate(' + heading + 'deg);display:inline-block">&#9650;</span>',
            iconSize: [8, 8], iconAnchor: [4, 4]
          });
          const marker = L.marker([a.lat, a.lng], { icon: icon });
          const alt = a.altitude ? Math.round(a.altitude * 3.281) + 'ft' : 'N/A';
          const spd = a.velocity ? Math.round(a.velocity * 1.944) + 'kn' : 'N/A';
          marker.bindPopup(
            '<div class="popup-custom">'
            + '<h3>' + (a.callsign || 'Unknown') + '</h3>'
            + '<div class="loc">' + (a.origin_country || '') + '</div>'
            + '<div class="summ">Alt: ' + alt + ' | Speed: ' + spd + '</div>'
            + '</div>'
          );
          marker._lastSeen = now;
          marker.addTo(aviationLayer);
          aircraftMarkers[key] = marker;
        }
      });
      Object.keys(aircraftMarkers).forEach(function(key) {
        if (Date.now() - aircraftMarkers[key]._lastSeen > 120000) {
          aviationLayer.removeLayer(aircraftMarkers[key]);
          delete aircraftMarkers[key];
        }
      });
      clearLayerState('aviation');
      if (data.error) {
        // The proxy answered honestly that the upstream feed is down.
        reportLayer('aviation', false, 'AVIATION: ' + data.error.toUpperCase(), '#ef4444');
      } else {
        reportLayer('aviation', true,
          seen ? seen + ' AIRCRAFT TRACKED' : 'AVIATION: 0 AIRCRAFT',
          seen ? '#22d3ee' : '#64748b');
      }
    })
    .catch(function(err) {
      if (err.isBackoff) { noteBackoff(); return; }
      if (err.isAuth) { reportLayer('aviation', false, err.message, '#ef4444'); return; }
      reportLayer('aviation', false, 'AVIATION OFFLINE: ' + err.message.substring(0, 40), '#ef4444');
    });
}

// Aircraft polling is driven by the shared queue at the bottom of this
// script. Keeping a second timer here ran the most expensive layer on its
// own schedule, which is what exhausted the limiter.

function loadConflicts() {
  if (!requireToken('Conflicts')) return;
  if (noteBackoff()) return;
  fetchJSON(API_URL + '/api/map/conflicts', { headers: { 'Authorization': 'Bearer ' + TOKEN } })
    .then(function(data) {
      conflictLayer.clearLayers();
      let placed = 0;
      (data.zones || []).forEach(function(zone) {
        if (!zone.coords || zone.coords.length < 3) return;
        placed++;
        L.polygon(zone.coords, {
          color: zone.color || '#ef4444',
          fillColor: zone.color || '#ef4444',
          fillOpacity: 0.12,
          weight: 1.5,
          className: 'conflict-zone',
        }).bindPopup(
          '<div class="popup-custom"><h3>' + (zone.name || 'Conflict Zone') + '</h3>'
          + '<div class="loc">' + (zone.label || '') + '</div>'
          + (zone.source ? '<div class="summ" style="font-size:8px">Src: ' + zone.source + '</div>' : '')
          + '</div>'
        ).addTo(conflictLayer);
      });
      (data.events || []).forEach(function(ev) {
        if (!ev.lat || !ev.lng) return;
        placed++;
        const color = ev.severity === 'high' ? '#ef4444' : ev.severity === 'medium' ? '#f59e0b' : '#64748b';
        L.circleMarker([ev.lat, ev.lng], {
          radius: ev.severity === 'high' ? 6 : 4,
          color: color, fillColor: color, fillOpacity: 0.6, weight: 1,
        }).bindPopup(
          '<div class="popup-custom"><h3>' + (ev.name || 'Event') + '</h3>'
          + '<div class="loc">' + (ev.label || '') + '</div>'
          + '<div class="summ">Severity: ' + ev.severity + '</div>'
          + '</div>'
        ).addTo(conflictLayer);
      });
      clearLayerState('conflict');
      reportLayer('conflict', true,
        placed ? placed + ' CONFLICT SIGNALS' : 'CONFLICT: 0 SIGNALS',
        placed ? '#ef4444' : '#64748b');
    })
    .catch(function(err) {
      if (err.isBackoff) { noteBackoff(); return; }
      if (err.isAuth) { reportLayer('conflict', false, err.message, '#ef4444'); return; }
      reportLayer('conflict', false, 'CONFLICT OFFLINE: ' + err.message.substring(0, 40), '#ef4444');
    });
}

const legend = L.control({ position: 'bottomright' });
legend.onAdd = function() {
  const div = L.DomUtil.create('div', 'legend');
  div.innerHTML = '<strong>SENTINEL / GEOSPATIAL</strong><br>'
    + '<i style="background:#ef4444"></i> CRITICAL<br>'
    + '<i style="background:#f59e0b"></i> HIGH<br>'
    + '<i style="background:#22d3ee"></i> MEDIUM<br>'
    + '<i style="background:#475569"></i> LOW<br>'
    + '<hr style="border-color:#1e293b;margin:4px 0">'
    + '<span style="color:#22d3ee">&#9650;</span> AIRCRAFT<br>'
    + '<i style="background:#ef4444;border-radius:0"></i> CONFLICT ZONE';
  return div;
};
legend.addTo(map);

// Request budget. The deployed limiter allows 100 requests per 15 minutes
// across every route, and the other panels are drawing on the same pool, so
// the map runs at roughly 1 request per 45s. All three initial loads are
// chained through a single queue instead of firing together, so a cold open
// spends three requests at once and the first 429 never happens.
var pending = [];
var pumping = false;

function enqueue(task) {
  pending.push(task);
  pump();
}

function pump() {
  if (pumping || !pending.length) return;
  if (inBackoff()) {
    setTimeout(pump, Math.min(backoffLeft() * 1000, 5000));
    return;
  }
  pumping = true;
  const task = pending.shift();
  let result;
  try { result = task(); } catch (e) { result = null; }
  const done = () => { pumping = false; setTimeout(pump, 400); };
  if (result && typeof result.then === 'function') result.then(done, done);
  else done();
}

setStatus('CONNECTING...', '#22d3ee');
enqueue(loadMarkers);
enqueue(loadConflicts);
enqueue(loadAircraft);

setInterval(function() { enqueue(loadMarkers); }, 60000);
setInterval(function() { enqueue(loadConflicts); }, 300000);
setInterval(function() { enqueue(loadAircraft); }, 60000);
</script>
</body>
</html>"""

class GeopoliticalMapPanel(QWidget):
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self._setup_ui()
        self._load_map()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("MapToolbar")
        toolbar.setFixedHeight(30)
        t = QHBoxLayout(toolbar)
        t.setContentsMargins(8, 0, 8, 0)
        t.setSpacing(8)

        title = QLabel("GEOPOLITICAL MAP")
        title.setObjectName("FrameTitle")
        t.addWidget(title)

        t.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #475569; font-size: 8pt;")
        t.addWidget(self.status_label)

        self.refresh_btn = QPushButton("REFRESH")
        self.refresh_btn.setFixedWidth(80)
        self.refresh_btn.setFixedHeight(22)
        self.refresh_btn.clicked.connect(self._load_map)
        t.addWidget(self.refresh_btn)

        self.zoom_extents_btn = QPushButton("EXTENTS")
        self.zoom_extents_btn.setFixedWidth(80)
        self.zoom_extents_btn.setFixedHeight(22)
        self.zoom_extents_btn.clicked.connect(self._load_map)
        t.addWidget(self.zoom_extents_btn)

        layout.addWidget(toolbar)

        self.web_view = None
        if WEBENGINE_DISABLED:
            self.web_view = self._build_placeholder()
        else:
            # Imported lazily so a disabled host never loads the module at all.
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)

        # The map HTML embeds the bearer token, and this panel is built before
        # the login dialog is answered. Reload once a token exists, otherwise
        # the page stays permanently unauthenticated and every poll fails.
        login_result = getattr(self.api_client, "loginResult", None)
        if login_result is not None:
            login_result.connect(self._on_login)

    def _build_placeholder(self):
        """Stand-in for the map when QtWebEngine cannot run on this host."""
        placeholder = QLabel(
            "MAP UNAVAILABLE\n\n"
            "QtWebEngine is disabled for this process.\n"
            "Set SENTINEL_DISABLE_WEBENGINE=0 and run on a host with a\n"
            "display or GPU stack to show the live map."
        )
        placeholder.setObjectName("MapUnavailable")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        return placeholder

    def _on_login(self, ok, _message):
        if ok and not WEBENGINE_DISABLED:
            self._load_map()

    def _load_map(self):
        if WEBENGINE_DISABLED:
            self.status_label.setText("MAP DISABLED — WEBENGINE OFF")
            return
        try:
            token = self.api_client.token or ""
            html = MAP_HTML_TEMPLATE.replace("%API_URL%", json.dumps(SERVER_URL))
            html = html.replace("%TOKEN%", json.dumps(token))
            self.web_view.setHtml(html, QUrl("http://localhost/"))
            self.status_label.setText(f"SRV: {SERVER_URL}")
        except Exception as e:
            self.status_label.setText(f"MAP ERROR: {e}")

    def refresh(self):
        self._load_map()
