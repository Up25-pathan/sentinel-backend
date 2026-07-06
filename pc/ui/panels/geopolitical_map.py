import json
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
from PyQt6.QtCore import QUrl, QTimer, Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView

from utils.api_client import SERVER_URL

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

function fetchJSON(url, headers) {
  return fetch(url, headers).then(function(r) {
    if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
    return r.json();
  });
}

function loadMarkers() {
  if (!TOKEN) { setStatus('NO AUTH TOKEN', '#ef4444'); return; }
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
          + '<div class="cat">' + (e.is_breaking ? '&#9888; BREAKING &middot; ' : '') + (e.category || '') + '</div>'
          + '<h3>' + (e.title || 'Untitled') + '</h3>'
          + '<div class="loc">' + (e.location_name || '') + (e.country ? ' &middot; ' + e.country : '') + '</div>'
          + '<div class="summ">' + (e.summary || '').substring(0, 200) + '</div>'
          + '<div style="margin-top:4px;font-size:9px;color:' + color + '">' + e.risk_level + '</div>'
          + '</div>'
        );
        intelLayer.addLayer(marker);
      });
      setStatus(count + ' INTEL MARKERS', '#f59e0b');
    })
    .catch(function(err) {
      console.error('Intel markers error:', err);
      setStatus('INTEL OFFLINE: ' + err.message.substring(0, 40), '#ef4444');
    });
}

var aircraftMarkers = {};
var aircraftTimer = null;

function loadAircraft() {
  fetchJSON(API_URL + '/api/map/aviation')
    .then(function(data) {
      const now = Date.now();
      (data.aircraft || []).forEach(function(a) {
        if (!a.lat || !a.lng) return;
        const key = a.icao24 || (a.lat + ',' + a.lng);
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
            + '<div class="loc">' + a.origin_country + '</div>'
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
    })
    .catch(function(err) { console.error('Aircraft load error:', err); });
}

function startAircraftUpdates() {
  loadAircraft();
  aircraftTimer = setInterval(loadAircraft, 30000);
}

function loadConflicts() {
  fetchJSON(API_URL + '/api/map/conflicts')
    .then(function(data) {
      conflictLayer.clearLayers();
      (data.zones || []).forEach(function(zone) {
        if (!zone.coords || zone.coords.length < 3) return;
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
    })
    .catch(function(err) { console.error('Conflict zones error:', err); });
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

setStatus('CONNECTING...', '#22d3ee');
loadMarkers();
loadConflicts();
startAircraftUpdates();
setInterval(loadMarkers, 30000);
setInterval(loadConflicts, 300000);
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

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)

    def _load_map(self):
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
