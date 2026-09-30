#!/usr/bin/env python3
"""RECON: passive and active host reconnaissance.

Every line printed here is measured against the target. The previous version
of this script slept for a few seconds and then printed invented findings
("TTL=64 (likely Linux)", made-up open ports) regardless of what the target
actually was. It now resolves, pings and probes for real, and reports
"no response" when that is the truth.

Only the single target passed with --target is contacted.
"""

import argparse
import socket
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.net_scanner import (  # noqa: E402
    FULL_SCAN_PORTS, PORT_SERVICES, grab_banner, identify_service, ping, resolve, scan_port,
)

TIMEOUT = 1.5


def out(msg):
    print(msg)
    sys.stdout.flush()


def main(target):
    out(f"[*] Reconnaissance against: {target}")

    # ── Name resolution ────────────────────────────────────────────────
    try:
        ip, hostname = resolve(target)
    except Exception as err:  # noqa: BLE001 - report, never fabricate
        out(f"[!] {err}")
        return 2

    out(f"[+] Resolved: {target} -> {ip}")
    if hostname and hostname != ip:
        out(f"[+] Reverse DNS: {hostname}")
        try:
            aliases = socket.gethostbyname_ex(hostname)[2]
            for alias in aliases:
                out(f"    alias: {alias}")
        except OSError:
            out("    no additional A records")
    else:
        out("[i] No reverse DNS record (this is a real negative result)")

    # ── Reachability ───────────────────────────────────────────────────
    alive, rtt = ping(ip, timeout_ms=2000)
    if alive:
        out(f"[+] ICMP echo: ALIVE (rtt {rtt if rtt is not None else 'unreported'}ms)")
    else:
        out("[i] ICMP echo: no reply (host may be firewalled or down)")

    # ── TCP reachability ───────────────────────────────────────────────
    out(f"[*] Probing {len(FULL_SCAN_PORTS)} TCP ports (timeout {TIMEOUT}s)...")
    open_ports = []
    filtered = 0
    for port in FULL_SCAN_PORTS:
        status, prtt, perr = scan_port(ip, port, timeout=TIMEOUT)
        if status == "OPEN":
            open_ports.append((port, prtt))
            service = PORT_SERVICES.get(port, "unknown")
            out(f"    [OPEN]     {port:>5}/tcp  {service:<14} {prtt}ms")
        elif status == "FILTERED":
            filtered += 1
            out(f"    [FILTERED] {port:>5}/tcp  {perr}")
        # CLOSED ports are the expected majority; list them compactly.
    closed = len(FULL_SCAN_PORTS) - len(open_ports) - filtered
    out(f"[+] {len(open_ports)} open, {closed} closed, {filtered} filtered of "
        f"{len(FULL_SCAN_PORTS)} probed")

    # ── Banner grab on what actually answered ──────────────────────────
    for port, _rtt in open_ports:
        banner = grab_banner(ip, port, timeout=TIMEOUT)
        if banner:
            out(f"[+] Banner {port}/tcp: {identify_service(port, banner)} - {banner[:120]}")
        else:
            out(f"[i] Banner {port}/tcp: service did not send a greeting")

    # ── Verdict ────────────────────────────────────────────────────────
    if not alive and not open_ports:
        out("[=] No evidence the host is reachable. Nothing further to report.")
    elif not open_ports:
        out(f"[=] Host responds to ICMP but no probed port is open.")
    else:
        out(f"[=] {len(open_ports)} reachable service(s): "
            f"{', '.join(str(p) for p, _ in open_ports)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Host reconnaissance (real measurements only)")
    ap.add_argument("--target", required=True, help="hostname or IP to assess")
    ap.add_argument("--timeout", type=float, default=TIMEOUT,
                    help="per-port TCP timeout in seconds (default: %(default)s)")
    args = ap.parse_args()
    globals()["TIMEOUT"] = max(0.1, args.timeout)
    sys.exit(main(args.target))