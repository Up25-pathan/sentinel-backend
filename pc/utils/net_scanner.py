# utils/net_scanner.py

"""Real network probing. Every value this module returns is measured.

The scanner panel used to fabricate its entire output: port states came from
random.choices() and response times from random.uniform(), so the table showed
invented reconnaissance dressed up as a real scan. Nothing here guesses. A
result is reported only when a socket, a ping or a banner actually answered,
and anything inconclusive is labelled as such.

Scope: these helpers talk to the single host the operator typed into the panel.
No subnet sweeps, no host lists, no third-party targets.

Classification vocabulary used in the UI:
    OPEN      TCP connect completed
    CLOSED    the host actively refused or reported the network unreachable
    FILTERED  no answer before the timeout (firewall drop, or host down)
"""

import errno
import platform
import re
import socket
import subprocess
import time

# Ports probed by the "Port Scan" preset.
WEB_AND_SSH_PORTS = [22, 80, 443, 8080, 8443]

# Ports probed by "Full Scan": the common remote-access, mail and database set.
FULL_SCAN_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445,
    993, 995, 1433, 1521, 2049, 3306, 3389, 5432, 5900, 6379,
    8080, 8443, 27017,
]

# Ports probed by "Service Scan": banner-collectable text protocols.
SERVICE_SCAN_PORTS = [21, 22, 25, 80, 110, 143, 443, 993, 995, 3389]

# Well-known port -> service, used only when a banner is unavailable. The
# banner, when present, always wins.
PORT_SERVICES = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 135: "MSRPC", 139: "NetBIOS", 143: "IMAP", 389: "LDAP",
    443: "HTTPS", 445: "SMB", 587: "SMTP-TLS", 993: "IMAPS", 995: "POP3S",
    1433: "MSSQL", 1521: "Oracle", 2049: "NFS", 3306: "MySQL", 3389: "RDP",
    5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-Proxy",
    8443: "HTTPS-Alt", 27017: "MongoDB",
}

# Connect timeout. Short enough to keep a full 25-port sweep responsive,
# long enough not to label a slow host as filtered.
DEFAULT_TIMEOUT = 1.5


class ScanError(Exception):
    """Raised for input that cannot be scanned at all (bad host, no route)."""


def resolve(target):
    """Resolve a hostname or literal IP. Returns (ip, hostname_or_None)."""
    target = (target or "").strip()
    if not target:
        raise ScanError("no target given")

    # Bracketed IPv6 literal, e.g. [::1]
    literal = target[1:-1] if target.startswith("[") and target.endswith("]") else target

    try:
        ip = socket.gethostbyname(literal)
    except socket.gaierror as err:
        raise ScanError(f"cannot resolve '{target}': {err.strerror or err}") from err
    except UnicodeError as err:
        raise ScanError(f"invalid target '{target}': {err}") from err

    # Recover the name for display when the user supplied a hostname.
    name = None
    try:
        name, _aliases, _addrs = socket.gethostbyaddr(ip)
    except (socket.herror, socket.gaierror, OSError):
        name = None
    return ip, name or (None if literal == ip else literal)


def ping(target, timeout_ms=2000):
    """Measure reachability with a real ICMP echo.

    Returns (alive, rtt_ms_or_None). Uses the platform ping binary, which is
    the only ICMP path available to an unprivileged desktop process; a failure
    to launch it reports alive=False with rtt None rather than inventing one.
    """
    system = platform.system()
    if system == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), target]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), target]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_ms / 1000.0 + 5
        )
    except FileNotFoundError:
        raise ScanError("ping utility not available on this system")
    except subprocess.TimeoutExpired:
        return False, None

    out = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    # Windows: "time=12ms"  |  POSIX: "time=12.3 ms"
    match = re.search(r"time[=<]\s*([\d.]+)\s*ms", out, re.IGNORECASE)
    if proc.returncode == 0:
        return True, round(float(match.group(1)), 1) if match else None
    return False, None


def scan_port(host, port, timeout=DEFAULT_TIMEOUT):
    """Connect to one TCP port and classify what actually happened.

    Returns (status, rtt_ms_or_None, error_or_None).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    started = time.perf_counter()
    try:
        sock.connect((host, port))
    except socket.timeout:
        return "FILTERED", None, "no response before timeout"
    except ConnectionRefusedError:
        return "CLOSED", None, "connection refused"
    except socket.gaierror as err:
        raise ScanError(f"cannot resolve '{host}': {err}") from err
    except OSError as err:
        code = err.errno
        if code in (errno.EHOSTUNREACH, errno.ENETUNREACH, errno.EHOSTDOWN):
            return "CLOSED", None, err.strerror or "host unreachable"
        if code == errno.ETIMEDOUT:
            return "FILTERED", None, "timed out"
        return "FILTERED", None, err.strerror or str(err)
    else:
        elapsed = round((time.perf_counter() - started) * 1000.0, 1)
        return "OPEN", elapsed, None
    finally:
        try:
            sock.close()
        except OSError:
            pass


def grab_banner(host, port, timeout=DEFAULT_TIMEOUT):
    """Read a real service banner.

    SMTP, POP3, IMAP and FTP greet a client unprompted, so a short read works
    without sending anything. SSH and HTTP require one minimal request first.
    Returns the banner text, or None when the service stays silent.
    """
    probes = {
        21: None,
        25: None,
        110: None,
        143: None,
        587: None,
        993: None,
        22: b"SSH-2.0-probe\r\n",
        80: b"HEAD / HTTP/1.0\r\n\r\n",
        443: None,
        3389: b"\x03\x00\x00\x0f\x02\xf0\x80",
    }
    payload = probes.get(port)
    if port == 443:
        # A bare TLS ClientHello is the polite way to make an HTTPS port speak.
        try:
            import ssl
            raw = socket.create_connection((host, port), timeout=timeout)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                tls.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
                return _clean(tls.recv(512))
        except Exception:  # noqa: BLE001 - a silent banner is a valid outcome
            return None

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            if payload:
                sock.sendall(payload)
            sock.settimeout(timeout)
            return _clean(sock.recv(512))
    except OSError:
        return None


def _clean(raw):
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\r\n\t")
    text = " ".join(text.split())
    return text[:200] if text else None


def identify_service(port, banner):
    """Name a service from a real banner, falling back to the port registry."""
    if banner:
        blob = banner.lower()
        if blob.startswith("ssh-"):
            return banner.split()[0]
        for needle, name in (
            ("http/", "HTTP"), ("smtp", "SMTP"), ("ftp", "FTP"),
            ("+tls", "SMTP-TLS"), ("imap", "IMAP"), ("pop3", "POP3"),
            ("microsoft terminal services", "RDP"),
        ):
            if needle in blob:
                return name
    return PORT_SERVICES.get(port, "unknown")


def resolve_and_ping(target):
    """Convenience: resolve, then measure reachability. Used by the Ping preset."""
    ip, hostname = resolve(target)
    alive, rtt = ping(ip)
    return ip, hostname, alive, rtt


def run_scan(target, scan_type, timeout=DEFAULT_TIMEOUT, progress=None):
    """Perform a real scan and yield result rows.

    progress((done, total)) is invoked as results become available so the panel
    can fill in incrementally instead of blocking until the whole sweep ends.

    Returns a list of dicts with the keys the panel table expects.
    """
    ip, hostname = resolve(target)
    label = hostname or ip
    rows = []

    if scan_type == "Ping":
        alive, rtt = ping(ip)
        rows.append({
            "target": label, "type": "Ping", "port": "---", "service": "---",
            "status": "ALIVE" if alive else "NO REPLY",
            "rtt": f"{rtt}ms" if rtt is not None else "---",
        })
        if progress:
            progress((1, 1))
        return rows

    if scan_type == "Port Scan":
        ports = WEB_AND_SSH_PORTS
        want_banner = False
    elif scan_type == "Service Scan":
        ports = SERVICE_SCAN_PORTS
        want_banner = True
    else:
        ports = FULL_SCAN_PORTS
        want_banner = False

    total = len(ports)
    for index, port in enumerate(ports, start=1):
        status, rtt, _err = scan_port(ip, port, timeout)
        service = "---"
        if status == "OPEN":
            banner = grab_banner(ip, port, timeout) if want_banner else None
            service = identify_service(port, banner)
        rows.append({
            "target": label, "type": scan_type, "port": str(port),
            "service": service, "status": status,
            "rtt": f"{rtt}ms" if rtt is not None else "---",
        })
        if progress:
            progress((index, total))

    # Keep the host's open ports at the top, then port order, so the table is
    # readable. This is a real sort over measured results, not a shuffle.
    rows.sort(key=lambda r: (0 if r["status"] == "OPEN" else 1,
                             int(r["port"]) if r["port"].isdigit() else 0))
    return rows