"""SENTINEL CIC — intelligence and reporting console.

The reporting half of SENTINEL. CIC observes feeds, events and infrastructure
state and renders what the backend actually returns; it does not act against
targets. Offensive tooling lives in the separate REDLAB app.

Run it with:  python cic_ui.py
"""

__version__ = "2.2.0"
__app_name__ = "SENTINEL CIC"
__nav_items__ = [
    ("__group", None, "INTEL", None),
    ("dashboard", "▶", "DASH", "Dashboard — live posture and risk"),
    ("intel", "♁", "INTL", "Intel Events"),
    ("osint", "☆", "OSNT", "OSINT Feeds"),
    ("darkweb", "☢", "DWEB", "Dark Web"),
    ("alerts", "⚠", "ALRT", "Alerts"),
    ("__group", None, "ANALYSIS", None),
    ("map", "☰", "MAP", "Geo Map"),
    ("chat", "✉", "CHAT", "AI Chat"),
    ("feeds", "⚐", "THRT", "Threat Feeds"),
    ("timeline", "⧖", "TIME", "Timeline"),
    ("__group", None, "ASSURANCE", None),
    ("vulndb", "⚛", "VULN", "Vuln Database — NVD and CISA KEV"),
    ("export", "⇩", "RPRT", "Export / Reports"),
    ("audit", "✓", "AUDT", "Audit Log"),
]
__panel_keys__ = [
    "dashboard", "intel", "osint", "darkweb", "alerts", "map",
    "chat", "feeds", "timeline", "vulndb", "export", "audit",
]

__all__ = ["__nav_items__", "__panel_keys__", "__version__", "__app_name__"]
