"""SENTINEL REDLAB — offensive operations console.

A separate application from SENTINEL CIC. REDLAB owns the panels and
utilities that act against infrastructure rather than reporting on it:
reconnaissance, web inspection, privilege-escalation posture, wireless
inventory, asset tracking, attack-path campaigns and network scanning.

Everything REDLAB reports is measured. Where a check cannot run, the tool
says so rather than substituting a plausible value.

Run it with:  python -m redlab
"""

__version__ = "1.0.0"
__app_name__ = "SENTINEL REDLAB"
__nav_items__ = [
    ("__group", None, "ENGAGE", None),
    ("redops", "⚔", "OPS", "Red Ops — jobs, Docker and VM inventory"),
    ("scanner", "⬝", "SCAN", "Network Scanner — measured port and service probing"),
    ("__group", None, "PLAN", None),
    ("campaign", "⬜", "CAMP", "Campaigns — MITRE ATT&CK attack paths"),
    ("assets", "⚙", "ASST", "Assets — tracked infrastructure"),
]
__panel_keys__ = ["redops", "scanner", "campaign", "assets"]

__all__ = ["__nav_items__", "__panel_keys__", "__version__", "__app_name__"]
