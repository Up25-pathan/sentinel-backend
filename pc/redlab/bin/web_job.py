#!/usr/bin/env python3
"""WEB: real HTTP(S) inspection of a single URL.

The previous version slept and printed invented findings ("No directory
listing detected", made-up missing-header counts) without contacting the
server at all. This one performs genuine requests with urllib and reports
only what came back, including when a request fails.

Only the URL passed with --url is contacted.
"""

import argparse
import re
import ssl
import sys
import urllib.error
import urllib.request

TIMEOUT = 10
USER_AGENT = "SENTINEL-RECON/1.0 (authorized assessment)"

# Headers whose absence is a real, checkable observation.
NOTABLE_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "server",
    "set-cookie",
]


def out(msg):
    print(msg)
    sys.stdout.flush()


def fetch(url, method="GET"):
    """Return (status, headers, body_bytes, final_url, error_or_None)."""
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=ctx) as resp:
            body = resp.read(512 * 1024)
            return resp.status, dict(resp.headers), body, resp.geturl(), None
    except urllib.error.HTTPError as err:
        # An error response is still a real measurement of the server.
        body = err.read(64 * 1024) if hasattr(err, "read") else b""
        return err.code, dict(err.headers or {}), body, url, None
    except (urllib.error.URLError, ssl.SSLError, OSError, ValueError) as err:
        reason = getattr(err, "reason", err)
        return None, {}, b"", url, str(reason)


def main(target_url):
    url = target_url.strip()
    if not url:
        out("[!] no URL given")
        return 2
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
        out(f"[*] assuming scheme: {url}")

    out(f"[*] HTTP inspection of: {url}")

    status, headers, body, final_url, error = fetch(url)
    if error:
        out(f"[!] Request failed: {error}")
        out("[=] No response received. Nothing to report about this URL.")
        return 1

    out(f"[+] HTTP {status} from {final_url} ({len(body)} bytes read)")

    # ── Server banner ──────────────────────────────────────────────────
    server = headers.get("Server")
    out(f"[+] Server: {server}" if server else "[i] Server: header not sent")

    powered = headers.get("X-Powered-By")
    if powered:
        out(f"[+] X-Powered-By: {powered}")

    # ── Notable security headers: report present and absent, both real ──
    present, absent = [], []
    for name in NOTABLE_HEADERS:
        (present if name in {k.lower() for k in headers} else absent).append(name)
    if present:
        out(f"[+] Present: {', '.join(sorted(present))}")
    if absent:
        out(f"[i] Not sent: {', '.join(sorted(absent))}")

    # ── Cookies ────────────────────────────────────────────────────────
    cookie = headers.get("Set-Cookie")
    if cookie:
        flags = []
        low = cookie.lower()
        if "secure" not in low:
            flags.append("no Secure flag")
        if "httponly" not in low:
            flags.append("no HttpOnly flag")
        if "samesite" not in low:
            flags.append("no SameSite attribute")
        out(f"[+] Set-Cookie: {cookie[:100]}")
        if flags:
            out(f"[i] Cookie attributes - {', '.join(flags)}")
    else:
        out("[i] No Set-Cookie header")

    # ── Title from the actual body ─────────────────────────────────────
    if body and status and status < 400:
        match = re.search(rb"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).decode("utf-8", errors="replace").strip()
            out(f"[+] <title>: {title[:120]}")
        else:
            out("[i] No <title> element in the returned HTML")

    # ── robots.txt: fetched for real ───────────────────────────────────
    from urllib.parse import urljoin, urlparse
    robots = urljoin(url, "/robots.txt")
    r_status, _h, r_body, _u, r_err = fetch(robots)
    if r_err:
        out(f"[i] robots.txt unreachable: {r_err}")
    elif r_status == 200:
        rules = [ln.strip() for ln in r_body.decode("utf-8", "replace").splitlines()
                 if ln.strip() and not ln.startswith("#")]
        out(f"[+] robots.txt served ({len(rules)} directives)")
        for rule in rules[:20]:
            out(f"    {rule}")
        if len(rules) > 20:
            out(f"    ... {len(rules) - 20} more")
    else:
        out(f"[i] robots.txt returned HTTP {r_status}")

    out("[=] Inspection complete. All findings above are from live responses.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Real HTTP inspection of one URL")
    ap.add_argument("--url", required=True, help="URL to inspect")
    args = ap.parse_args()
    sys.exit(main(args.url))