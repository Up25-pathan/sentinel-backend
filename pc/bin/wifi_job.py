#!/usr/bin/env python3
"""WIFI: local wireless adapter and nearby-network inventory.

This file was previously empty (0 bytes), so the WIFI button in the RedOps
jobs tab launched a subprocess that printed nothing at all. It now queries the
local machine's actual radio state and nearby networks through the platform's
own tooling, and reports plainly when the host has no wireless capability or
the tools are missing.

Read-only: it lists and inspects. It never associates, deauthenticates,
captures handshakes or touches stored credentials.

The --interface argument is a hint used to pick a device where the platform
supports selecting one; it is not a remote target.
"""

import argparse
import platform
import re
import shutil
import subprocess
import sys

TIMEOUT = 20


def out(msg):
    print(msg)
    sys.stdout.flush()


def run(cmd):
    """Run a command and return (rc, stdout, stderr); never raise."""
    exe = shutil.which(cmd[0])
    if not exe:
        return None, "", f"{cmd[0]} not found on PATH"
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT,
            encoding="utf-8", errors="replace",
        )
        return proc.returncode, proc.stdout or "", (proc.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return None, "", f"{cmd[0]} timed out after {TIMEOUT}s"
    except OSError as err:
        return None, "", str(err)


def section(title):
    out("")
    out(f"=== {title} ===")


def scan_windows(interface_hint):
    out(f"[*] Host: {platform.node()} ({platform.release()})")

    section("Wireless interfaces")
    rc, text, err = run(["netsh", "wlan", "show", "interfaces"])
    if rc is None:
        out(f"[!] Cannot query wireless state: {err}")
        out("[=] No wireless data available on this host.")
        return 1
    if rc != 0 or not text.strip():
        out(f"[i] netsh reported no wireless interfaces (rc={rc})")
        out(f"    {err}" if err else "    This host has no active Wi-Fi adapter.")
        out("[=] Nothing to report.")
        return 0

    blocks = re.split(r"\r?\n\r?\n", text.strip())
    parsed = []
    for block in blocks:
        name = re.search(r"Name\s*:\s*(.+)", block)
        state = re.search(r"State\s*:\s*(.+)", block)
        ssid = re.search(r"SSID\s*:\s*(.+)", block)
        bssid = re.search(r"BSSID\s*:\s*(.+)", block)
        channel = re.search(r"Channel\s*:\s*(.+)", block)
        signal = re.search(r"Signal\s*:\s*(.+)", block)
        radio = re.search(r"Radio type\s*:\s*(.+)", block)
        auth = re.search(r"Authentication\s*:\s*(.+)", block)
        if name:
            parsed.append(dict(
                name=name.group(1).strip(),
                state=state.group(1).strip() if state else "unknown",
                ssid=ssid.group(1).strip() if ssid else "",
                bssid=bssid.group(1).strip() if bssid else "",
                channel=channel.group(1).strip() if channel else "",
                signal=signal.group(1).strip() if signal else "",
                radio=radio.group(1).strip() if radio else "",
                auth=auth.group(1).strip() if auth else "",
            ))

    out(f"[+] {len(parsed)} wireless interface(s) reported")
    for idx, dev in enumerate(parsed):
        out(f"  [{idx}] {dev['name']}")
        out(f"      state    : {dev['state']}")
        out(f"      ssid     : {dev['ssid'] or '(not associated)'}")
        out(f"      bssid    : {dev['bssid'] or '-'}")
        out(f"      channel  : {dev['channel'] or '-'}   radio: {dev['radio'] or '-'}")
        out(f"      signal   : {dev['signal'] or '-'}")
        out(f"      auth     : {dev['auth'] or '-'}")
    if interface_hint:
        matched = [d for d in parsed if d["name"].lower() == interface_hint.lower()]
        if matched:
            out(f"[+] Requested interface '{interface_hint}' is present and listed above")
        else:
            out(f"[i] Requested interface '{interface_hint}' was not found; "
                f"available: {', '.join(d['name'] for d in parsed)}")

    section("Stored profiles")
    rc, text, err = run(["netsh", "wlan", "show", "profiles"])
    if rc != 0:
        out(f"[i] Profile list unavailable: {err or 'netsh returned ' + str(rc)}")
    else:
        names = re.findall(r"All User Profile\s*:\s*(.+)", text)
        if names:
            out(f"[+] {len(names)} stored profile(s):")
            for name in names:
                out(f"    {name.strip()}")
        else:
            out("[i] No stored profiles found")

    section("Nearby networks")
    rc, text, err = run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    if rc != 0 or not text.strip():
        out(f"[i] Scan unavailable: {err or 'no scan output'} "
            f"(a connected adapter and location permission are usually required)")
    else:
        out(text.strip()[:4000])
        out("[i] Output truncated at 4000 characters")
    out("")
    out("[=] Inventory complete. Read-only: nothing was associated or captured.")
    return 0


def scan_linux(interface_hint):
    out(f"[*] Host: {platform.node()} ({platform.release()})")

    section("Wireless interfaces")
    tools = [("iw", ["iw", "dev"]), ("iwconfig", ["iwconfig"]), ("nmcli", ["nmcli", "device", "status"])]
    any_tool = False
    for name, cmd in tools:
        rc, text, err = run(cmd)
        if rc is None:
            out(f"[i] {name}: unavailable ({err})")
            continue
        any_tool = True
        out(f"[+] {name}:")
        for line in text.strip().splitlines()[:40]:
            out(f"    {line}")
    if not any_tool:
        out("[!] No wireless tooling (iw/iwconfig/nmcli) on this host")
        out("[=] No wireless data available.")
        return 1

    if interface_hint:
        rc, text, err = run(["iw", "dev", interface_hint, "info"])
        if rc == 0:
            section(f"Interface {interface_hint}")
            for line in text.strip().splitlines():
                out(f"    {line}")
        else:
            out(f"[i] Interface '{interface_hint}': {err or 'iw could not describe it'}")

    section("Access points in range")
    rc, text, err = run(["nmcli", "device", "wifi", "list"])
    if rc != 0 or not text.strip():
        out(f"[i] No AP list: {err or 'nmcli wifi list failed or radio is off'}")
    else:
        for line in text.strip().splitlines()[:60]:
            out(f"    {line}")
    out("")
    out("[=] Inventory complete. Read-only: nothing was associated or captured.")
    return 0


def main(interface):
    system = platform.system()
    if system == "Windows":
        return scan_windows(interface)
    if system == "Linux":
        return scan_linux(interface)
    out(f"[!] Unsupported platform: {system}")
    out("[=] No wireless data available.")
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Read-only local wireless adapter and nearby-AP inventory")
    ap.add_argument("--interface", default=None,
                    help="optional interface name to inspect in detail")
    args = ap.parse_args()
    sys.exit(main(args.interface))