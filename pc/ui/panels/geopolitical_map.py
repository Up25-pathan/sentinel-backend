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
  .flight-path { stroke: #22d3ee; stroke-width: 1; stroke-opacity: 0.25; stroke-dasharray: 4 4; }
  .flight-path:hover { stroke-opacity: 0.7; stroke-width: 2; }
  .flight-dot { color: #22d3ee; font-size: 6px; text-shadow: 0 0 4px rgba(34,211,238,0.8); }
  .conflict-zone { fill-opacity: 0.15; stroke-width: 1.5; }
</style>
</head>
<body>
<div id="map"></div>
<script>
const API_URL = %API_URL%;
const TOKEN = %TOKEN%;

const map = L.map('map', {
  center: [20, 0], zoom: 2,
  zoomControl: true,
  attributionControl: false,
  worldCopyJump: true
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  maxZoom: 19
}).addTo(map);

// ─── Layer Groups ──────────────────────────────────────────────
const intelLayer = L.layerGroup().addTo(map);
const aviationLayer = L.layerGroup().addTo(map);
const conflictLayer = L.layerGroup().addTo(map);

// ─── Layer Toggle Control ──────────────────────────────────────
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
    const layer = target.dataset.layer;
    const groups = { intel: intelLayer, aviation: aviationLayer, conflict: conflictLayer };
    if (map.hasLayer(groups[layer])) {
      map.removeLayer(groups[layer]);
      target.style.color = '#475569';
    } else {
      map.addLayer(groups[layer]);
      target.style.color = '#f59e0b';
    }
  });
  return div;
};
layerControl.addTo(map);

// ─── Intel Markers ─────────────────────────────────────────────
const ICONS = {
  CRITICAL: L.divIcon({ className: '', html: '<span class="marker-critical">&#9679;</span>', iconSize: [20, 20], iconAnchor: [10, 10] }),
  HIGH:     L.divIcon({ className: '', html: '<span class="marker-high">&#9679;</span>', iconSize: [18, 18], iconAnchor: [9, 9] }),
  MEDIUM:   L.divIcon({ className: '', html: '<span class="marker-medium">&#9679;</span>', iconSize: [16, 16], iconAnchor: [8, 8] }),
  LOW:      L.divIcon({ className: '', html: '<span class="marker-low">&#9679;</span>', iconSize: [14, 14], iconAnchor: [7, 7] })
};

function getIcon(risk) {
  return ICONS[risk] || ICONS.LOW;
}

function loadMarkers() {
  const headers = { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' };
  fetch(API_URL + '/api/map/markers', { headers })
    .then(r => r.json())
    .then(data => {
      intelLayer.clearLayers();
      const items = data.markers || [];
      items.forEach(function(e) {
        if (!e.lat || !e.lng) return;
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
    })
    .catch(function(err) { console.error('Intel markers error:', err); });
}

// ─── Aviation: Flight Routes ──────────────────────────────────
const FLIGHT_ROUTES = [
  { from: [40.6413, -73.7781], to: [51.4700, -0.4543], code: 'JFK-LHR' },
  { from: [33.9416, -118.4085], to: [35.6762, 139.6503], code: 'LAX-NRT' },
  { from: [25.2532, 55.3657], to: [51.4700, -0.4543], code: 'DXB-LHR' },
  { from: [1.3592, 103.9894], to: [49.0097, 2.5479], code: 'SIN-CDG' },
  { from: [40.6413, -73.7781], to: [48.8566, 2.3522], code: 'JFK-CDG' },
  { from: [25.2532, 55.3657], to: [1.3592, 103.9894], code: 'DXB-SIN' },
  { from: [35.6762, 139.6503], to: [49.0097, 2.5479], code: 'NRT-CDG' },
  { from: [51.4700, -0.4543], to: [55.7558, 37.6173], code: 'LHR-SVO' },
  { from: [1.3592, 103.9894], to: [33.9416, -118.4085], code: 'SIN-LAX' },
  { from: [40.6413, -73.7781], to: [25.2532, 55.3657], code: 'JFK-DXB' },
  { from: [55.7558, 37.6173], to: [39.9042, 116.4074], code: 'SVO-PEK' },
  { from: [40.6413, -73.7781], to: [19.4361, -99.0719], code: 'JFK-MEX' },
];

let flightDots = [];

function gcInterpolate(p1, p2, frac) {
  const lat1 = p1[0] * Math.PI / 180, lon1 = p1[1] * Math.PI / 180;
  const lat2 = p2[0] * Math.PI / 180, lon2 = p2[1] * Math.PI / 180;
  const d = 2 * Math.asin(Math.sqrt(Math.pow(Math.sin((lat1-lat2)/2),2) + Math.cos(lat1)*Math.cos(lat2)*Math.pow(Math.sin((lon1-lon2)/2),2)));
  const a = Math.sin((1-frac)*d) / Math.sin(d);
  const b = Math.sin(frac*d) / Math.sin(d);
  const x = a*Math.cos(lat1)*Math.cos(lon1) + b*Math.cos(lat2)*Math.cos(lon2);
  const y = a*Math.cos(lat1)*Math.sin(lon1) + b*Math.cos(lat2)*Math.sin(lon2);
  const z = a*Math.sin(lat1) + b*Math.sin(lat2);
  return [Math.atan2(z, Math.sqrt(x*x+y*y)) * 180 / Math.PI, Math.atan2(y, x) * 180 / Math.PI];
}

function buildFlightRoutes() {
  FLIGHT_ROUTES.forEach(function(route) {
    const points = [];
    const steps = 40;
    for (let i = 0; i <= steps; i++) {
      points.push(gcInterpolate(route.from, route.to, i / steps));
    }
    L.polyline(points, {
      className: 'flight-path',
      weight: 1,
      opacity: 0.25,
      dashArray: '4 4',
    }).bindPopup('<div class="popup-custom"><h3>' + route.code + '</h3><div class="loc">' + route.from.join(',') + ' &rarr; ' + route.to.join(',') + '</div></div>').addTo(aviationLayer);

    const dot = L.circleMarker(route.from, {
      radius: 3, color: '#22d3ee', fillColor: '#22d3ee', fillOpacity: 0.9,
      className: 'flight-dot'
    }).addTo(aviationLayer);
    flightDots.push({ dot: dot, route: route, progress: Math.random(), speed: 0.002 + Math.random() * 0.006 });
  });
}

function animateFlights() {
  flightDots.forEach(function(fd) {
    fd.progress += fd.speed;
    if (fd.progress > 1) fd.progress = 0;
    const pos = gcInterpolate(fd.route.from, fd.route.to, fd.progress);
    fd.dot.setLatLng(pos);
  });
  requestAnimationFrame(animateFlights);
}

// ─── Conflict Zones ─────────────────────────────────────────────
const CONFLICT_ZONES = [
  { name: 'Ukraine War', coords: [[52.0, 22.0], [52.5, 40.0], [46.0, 40.0], [44.0, 33.0], [46.0, 30.0], [47.5, 26.0], [49.0, 22.5]], color: '#ef4444', label: 'ACTIVE WAR' },
  { name: 'Gaza Strip', coords: [[31.6, 34.2], [31.6, 34.6], [31.3, 34.6], [31.3, 34.2]], color: '#ef4444', label: 'CONFLICT ZONE' },
  { name: 'Myanmar', coords: [[28.5, 92.0], [28.5, 102.0], [10.0, 102.0], [10.0, 92.0]], color: '#f59e0b', label: 'CIVIL WAR' },
  { name: 'Sudan', coords: [[22.0, 22.0], [22.0, 38.0], [8.0, 38.0], [8.0, 22.0]], color: '#f59e0b', label: 'CONFLICT' },
  { name: 'Yemen', coords: [[19.0, 42.0], [19.0, 54.0], [12.5, 54.0], [12.5, 42.0]], color: '#ef4444', label: 'CIVIL WAR' },
  { name: 'South China Sea', coords: [[22.0, 111.0], [22.0, 122.0], [10.0, 122.0], [10.0, 111.0]], color: '#f59e0b', label: 'DISPUTED WATERS' },
  { name: 'Sahel Region', coords: [[20.0, -17.0], [20.0, 30.0], [12.0, 30.0], [12.0, -17.0]], color: '#f59e0b', label: 'INSURGENCY' },
  { name: 'Taiwan Strait', coords: [[27.0, 118.0], [27.0, 124.0], [22.0, 124.0], [22.0, 118.0]], color: '#f59e0b', label: 'HEIGHTENED TENSION' },
];

function buildConflictZones() {
  CONFLICT_ZONES.forEach(function(zone) {
    const polygon = L.polygon(zone.coords, {
      color: zone.color,
      fillColor: zone.color,
      fillOpacity: 0.12,
      weight: 1.5,
      className: 'conflict-zone',
    }).bindPopup('<div class="popup-custom"><h3>' + zone.name + '</h3><div class="loc">' + zone.label + '</div></div>').addTo(conflictLayer);
  });
}

// ─── Legend ─────────────────────────────────────────────────────
const legend = L.control({ position: 'bottomright' });
legend.onAdd = function() {
  const div = L.DomUtil.create('div', 'legend');
  div.innerHTML = '<strong>SENTINEL / GEOSPATIAL</strong><br>'
    + '<i style="background:#ef4444"></i> CRITICAL<br>'
    + '<i style="background:#f59e0b"></i> HIGH<br>'
    + '<i style="background:#22d3ee"></i> MEDIUM<br>'
    + '<i style="background:#475569"></i> LOW<br>'
    + '<hr style="border-color:#1e293b;margin:4px 0">'
    + '<span style="color:#22d3ee">&#x2708;</span> FLIGHT ROUTE<br>'
    + '<i style="background:#ef4444"></i> CONFLICT ZONE<br>'
    + '<i style="background:#f59e0b"></i> TENSION';
  return div;
};
legend.addTo(map);

// ─── Init ──────────────────────────────────────────────────────
loadMarkers();
buildFlightRoutes();
buildConflictZones();
setInterval(loadMarkers, 30000);
animateFlights();
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
