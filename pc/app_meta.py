"""SENTINEL — one application covering intelligence and offensive operations.

The rail is grouped so the two halves stay legible inside a single window.
INTEL, ANALYSIS and ASSURANCE observe and report; ENGAGE, OPERATE and PLAN act
against targets you are authorised to assess, and run locally as job scripts.

Run it with:  python sentinel_ui.py
"""

__version__ = "3.0.0"
__app_name__ = "SENTINEL"
__nav_items__ = [
    ("__group", None, "INTEL", None),
    ("dashboard", "▶", "DASH", "Dashboard — live posture and risk"),
    ("intel", "♁", "INTL", "Intel Events"),
    ("osint_feed", "☆", "OSNT", "OSINT Feeds"),
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
    ("__group", None, "ENGAGE", None),
    ("recon", "◎", "RCON", "Reconnaissance — hosts, DNS and ports"),
    ("web", "⚯", "WEB", "Web inspection — HTTP, headers and TLS"),
    ("privesc", "⇧", "PRIV", "Privilege escalation — local posture audit"),
    ("osint", "◉", "OSIG", "OSINT — WHOIS, DNS and subdomains"),
    ("wifi", "≋", "WIFI", "Wireless — local adapter inventory"),
    ("exploit", "⚠", "EXPL", "Exploitability — read-only CVE assessment"),
    ("__group", None, "OPERATE", None),
    ("redops", "⚔", "OPS", "Red Ops — jobs, Docker and VM inventory"),
    ("scanner", "⬝", "SCAN", "Network Scanner — measured port probing"),
    ("campaign", "⬜", "CAMP", "Campaigns — MITRE ATT&CK attack paths"),
    ("assets", "⚙", "ASST", "Assets — tracked infrastructure"),
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
