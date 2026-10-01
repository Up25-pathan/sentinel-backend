"""SENTINEL — one application covering intelligence and offensive operations.

The rail is grouped so the two halves stay legible inside a single window.
INTEL, ANALYSIS and ASSURANCE observe and report; ENGAGE, OPERATE and PLAN act
against targets you are authorised to assess, and run locally as job scripts.

Run it with:  python sentinel_ui.py
"""

__version__ = "3.0.0"
__app_name__ = "SENTINEL"
# The second field is a glyph prefix and is now empty on purpose. The rail used
# to prefix each label with a symbol (▶, ♁, ☢, ⚔ …), which rendered at wildly
# different sizes and weights depending on the font and read as decoration
# rather than information. Labels are plain text and the rail is wide enough to
# spell them out.
__nav_items__ = [
    ("__group", None, "INTEL", None),
    ("dashboard", "", "Dashboard", "Live posture and risk"),
    ("intel", "", "Intel Events", "Tracked events and campaigns"),
    ("osint_feed", "", "OSINT Feeds", "Open-source intelligence feeds"),
    ("darkweb", "", "Dark Web", "Stored dark web signals"),
    ("alerts", "", "Alerts", "Active alerts"),
    ("__group", None, "ANALYSIS", None),
    ("map", "", "Geo Map", "Geopolitical map, conflicts and aviation"),
    ("chat", "", "AI Chat", "Groq-backed analyst chat"),
    ("feeds", "", "Threat Feeds", "Upstream feed health"),
    ("timeline", "", "Timeline", "Event timeline"),
    ("__group", None, "ASSURANCE", None),
    ("vulndb", "", "Vuln Database", "NVD and CISA KEV"),
    ("export", "", "Reports", "Export and reports"),
    ("audit", "", "Audit Log", "Action audit log"),
    ("__group", None, "ENGAGE", None),
    ("recon", "", "Recon", "Hosts, DNS and open ports"),
    ("web", "", "Web Inspect", "HTTP, headers and TLS"),
    ("privesc", "", "Priv Esc", "Local privilege escalation audit"),
    ("osint", "", "OSINT Scan", "WHOIS, DNS and subdomains"),
    ("wifi", "", "Wireless", "Local adapter inventory"),
    ("exploit", "", "Exploitability", "Read-only CVE assessment"),
    ("__group", None, "OPERATE", None),
    ("redops", "", "Red Ops", "Jobs, Docker and VM inventory"),
    ("scanner", "", "Network Scan", "Measured port probing"),
    ("campaign", "", "Campaigns", "MITRE ATT&CK attack paths"),
    ("assets", "", "Assets", "Tracked infrastructure"),
]
__panel_keys__ = [
    # intel and reporting
    "dashboard", "intel", "osint_feed", "darkweb", "alerts", "map",
    "chat", "feeds", "timeline", "vulndb", "export", "audit",
    # offensive tooling, each a first-class rail entry
    "recon", "web", "privesc", "osint", "wifi", "exploit",
    "redops", "scanner", "campaign", "assets",
]

__all__ = ["__nav_items__", "__panel_keys__", "__version__", "__app_name__"]
