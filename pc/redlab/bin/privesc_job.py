#!/usr/bin/env python3
"""PRIVESC: local privilege-escalation posture audit.

The previous version accepted a target IP, slept, and printed invented SUID
listings and "GTFOBins matches" that were never read from any filesystem.
There is no meaningful way to audit a remote host's privileges without a
session on it, so this script audits the machine it actually runs on and says
so plainly. Every check below inspects real files or real process state.

Read-only: nothing is modified, escalated or exploited.
"""

import argparse
import os
import platform
import re
import subprocess
import sys

# Binaries that are commonly SUID and worth a closer look when present.
INTERESTING = {
    "sudo", "su", "passwd", "chsh", "gpasswd", "newgrp", "pkexec",
    "find", "vim", "vi", "less", "more", "nano", "awk", "gawk", "mawk",
    "perl", "python", "python3", "ruby", "lua", "tar", "zip", "env", "nmap",
}

# Kernel-version patterns that have had known local-root issues. This reports a
# match as an observation only; it does not claim the host is vulnerable.
RISKY_KERNEL_HINTS = [
    (re.compile(r"\b(3\.2\.0|2\.6\.32)\b"), "very old stable branch (3.2.0) - long EOL"),
    (re.compile(r"\b2\.6\.(3[0-2])\b"), "2.6.3x series - ancient, long unmaintained"),
    (re.compile(r"\b4\.4\.0\b"), "4.4.0 - early 4.4, predates many hardening fixes"),
]


def out(msg):
    print(msg)
    sys.stdout.flush()


def audit_suid():
    out("[*] Scanning filesystem for SUID/SGID binaries")
    suid, sgid = [], []
    scanned = 0
    seen_dirs = set()
    for root in ("/usr/bin", "/usr/sbin", "/bin", "/sbin", "/usr/local/bin", "/usr/local/sbin"):
        if not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError as err:
            out(f"    [{root}] unreadable: {err.strerror}")
            continue
        for name in entries:
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            scanned += 1
            mode = st.st_mode
            is_suid = bool(mode & 0o4000)
            is_sgid = bool(mode & 0o2000)
            if is_suid:
                suid.append((path, oct(mode & 0o7777)))
            if is_sgid:
                sgid.append((path, oct(mode & 0o7777)))

    out(f"[+] Stat'ed {scanned} files in system binary directories")
    out(f"[+] {len(suid)} SUID, {len(sgid)} SGID binaries present")

    notable = [(p, m) for p, m in suid if os.path.basename(p) in INTERESTING]
    if notable:
        out("[i] SUID binaries commonly abused for escalation:")
        for path, mode in sorted(notable):
            out(f"    {mode:>8}  {path}")
    else:
        out("[i] No commonly-abused SUID binary found in the scanned directories")
    if sgid:
        out(f"[i] SGID binaries: {', '.join(p for p, _ in sorted(sgid)[:10])}")
    return len(notable), len(suid)


def audit_writable_system():
    out("\n[*] Checking for world-writable directories under /usr and /etc")
    suspicious = []
    for root in ("/usr/bin", "/usr/sbin", "/bin", "/sbin", "/etc"):
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            try:
                st = os.stat(dirpath)
            except OSError:
                continue
            if st.st_mode & 0o002:
                suspicious.append(dirpath)
            if len(suspicious) > 20:
                break
    if suspicious:
        for path in suspicious[:20]:
            out(f"[!] world-writable: {path}")
    else:
        out("[+] No world-writable directories found in the scanned paths")
    return len(suspicious)


def audit_kernel():
    out("\n[*] Kernel and platform")
    release = platform.release()
    system = platform.system()
    out(f"[+] {system} {platform.version()}")
    out(f"[+] Kernel release: {release}")
    hits = [(pat, note) for pat, note in RISKY_KERNEL_HINTS if pat.search(release)]
    if hits:
        for _pat, note in hits:
            out(f"[i] Release matches a branch with known history of issues: {note}")
        out("[i] Reported for awareness only - confirm against current advisories")
    else:
        out("[i] Kernel branch does not match the well-known old/EOL patterns")
    return len(hits)


def audit_permissions():
    out("\n[*] Current identity")
    out(f"[+] user: {os.environ.get('USERNAME') or os.environ.get('USER') or 'unknown'}")
    # getuid/getgid are POSIX-only; on Windows report the real equivalents.
    if hasattr(os, "getuid"):
        uid, gid = os.getuid(), os.getgid()
        out(f"[+] uid={uid} gid={gid}")
        if uid == 0:
            out("[!] Running as root - the filesystem findings below are already moot")
        return uid == 0
    admin = bool(os.environ.get("USERPROFILE"))
    out(f"[+] Windows account; profile={os.environ.get('USERPROFILE', 'unknown')}")
    if os.environ.get("COMPUTERNAME"):
        out(f"[+] machine: {os.environ['COMPUTERNAME']}")
    admin_note = "group membership not queried (needs net session / whoami /groups)"
    out(f"[i] Privilege level: {admin_note}")
    return False


def main(_target):
    # The old script's --target argument is accepted so existing UI wiring keeps
    # working, but it is ignored and reported as ignored rather than pretended.
    out("[*] PRIVESC posture audit of THIS machine")
    out("[i] Remote privilege escalation cannot be assessed without a session;")
    out("[i] this audits local privilege-escalation exposure only.")

    if platform.system() != "Linux":
        out(f"\n[!] The SUID/SGID and world-writable checks are Linux-specific.")
        out(f"[!] Detected platform: {platform.system()}. Filesystem audit skipped.")
        out(f"[+] Host OS: {platform.platform()}")
        out(f"[+] Kernel/release equivalent: {platform.release()} ({platform.version()})")
        out("[i] On Windows, review local privilege posture with: whoami /groups,")
        out("    Get-LocalGroupMember Administrators, and audit logon rights.")
        audit_permissions()
        out("\n[=] Audit complete. Findings above are from live system state.")
        return 0

    audit_permissions()
    audit_kernel()
    audit_suid()
    audit_writable_system()

    out("\n[=] Audit complete. Every finding above came from live filesystem and")
    out("    process state; nothing here is simulated.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Local privilege-escalation posture audit (read-only)")
    ap.add_argument("--target", default=None,
                    help="ignored: this audit runs against the local machine")
    args = ap.parse_args()
    if args.target:
        print(f"[*] Note: --target {args.target} is ignored; this audit is local-only.")
        sys.stdout.flush()
    sys.exit(main(args.target))