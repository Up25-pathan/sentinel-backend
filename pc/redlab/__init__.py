"""SENTINEL offensive tooling.

The panels and utilities that act against infrastructure rather than reporting
on it: reconnaissance, web inspection, privilege-escalation posture, wireless
inventory, asset tracking, attack-path campaigns, network scanning and
exploitability assessment.

These live in the ENGAGE and OPERATE sections of the single SENTINEL rail
rather than in a second application. This module keeps the tool definitions the
rail and the unified window both read, so there is one source of truth for each
tool's name, script and expected flag.

Everything reported here is measured. Where a check cannot run, the tool says
so rather than substituting a plausible value.
"""

__version__ = "1.0.0"
__app_name__ = "SENTINEL REDLAB"
__nav_items__ = [
    ("__group", None, "ENGAGE", None),
    ("recon", "◎", "RECON", "Reconnaissance — hosts, DNS and service discovery"),
    ("web", "⚯", "WEB", "Web inspection — HTTP headers, TLS and exposed content"),
    ("privesc", "⇧", "PRIVESC", "Privilege escalation — local posture audit"),
    ("osint", "◉", "OSINT", "OSINT — WHOIS, DNS and subdomain discovery"),
    ("wifi", "≋", "WIFI", "Wireless — local adapter inventory"),
    ("exploit", "⚠", "EXPLOIT", "Exploitability — read-only CVE assessment"),
    ("__group", None, "ENGAGE MORE", None),
    ("redops", "⚔", "OPS", "Red Ops — jobs, Docker and VM inventory"),
    ("scanner", "⬝", "SCAN", "Network Scanner — measured port and service probing"),
    ("__group", None, "PLAN", None),
    ("campaign", "⬜", "CAMP", "Campaigns — MITRE ATT&CK attack paths"),
    ("assets", "⚙", "ASST", "Assets — tracked infrastructure"),
]
# Every key needs a panel. Tools are ordered as the rail lists them.
__panel_keys__ = [
    "recon", "web", "privesc", "osint", "wifi", "exploit",
    "redops", "scanner", "campaign", "assets",
]

# Rail key -> (job name, prompt title, prompt label, job script). Each tool gets
# its own panel built from this table so the sidebar entry and the OPS button
# run exactly the same job.
__tool_defs__ = {
    "recon": ("RECON", "Recon Target", "Enter Target IP/Domain:", "recon_job.py", "--target"),
    "web": ("WEB", "Web Target", "Enter Target URL:", "web_job.py", "--url"),
    "privesc": ("PRIVESC", "Privesc Target", "Enter Target IP:", "privesc_job.py", "--target"),
    "osint": ("OSINT", "OSINT Target", "Enter Target Domain:", "osint_job.py", "--domain"),
    "wifi": ("WIFI", "Wi-Fi Interface", "Enter interface name (e.g., wlan0):",
             "wifi_job.py", "--interface"),
    "exploit": ("EXPLOIT", "Exploit Assessment Target",
                "Target IP or hostname (authorised targets only):",
                "exploit_job.py", "--target"),
}

__all__ = ["__nav_items__", "__panel_keys__", "__tool_defs__", "__version__", "__app_name__"]
