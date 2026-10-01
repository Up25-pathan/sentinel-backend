# bin/osint_job.py
#
# Passive OSINT: WHOIS, DNS records and subdomain discovery.
#
# Written against the standard library on purpose. The previous version
# imported `whois` and `dns.resolver`, neither of which ships with Python,
# so the job died at import time with a bare ModuleNotFoundError before doing
# anything -- the panel showed a traceback instead of results. WHOIS is a
# line-based protocol on port 43 and the resolver we need is one line of
# socket.getaddrinfo, so there is no reason to depend on either package.

import argparse
import socket
import sys
import time

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    HAVE_REQUESTS = False


def print_flush(text):
    """Prints and immediately flushes the output buffer."""
    print(text)
    sys.stdout.flush()


# Registry WHOIS servers for the gTLDs most likely to be scanned. IANA itself
# only holds a referral stub, so querying it first loses the real record.
REGISTRY_SERVERS = {
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.publicinterestregistry.org",
    "info": "whois.afilias.net",
    "io": "whois.nic.io",
    "co": "whois.nic.co",
    "dev": "whois.nic.google",
    "app": "whois.nic.google",
}


def whois_lookup(domain):
    """Query a WHOIS server over TCP/43 and return the raw text."""
    tld = domain.rstrip(".").rsplit(".", 1)[-1].lower()
    order = [REGISTRY_SERVERS.get(tld), "whois.iana.org"]
    for server in [s for s in order if s]:
        try:
            with socket.create_connection((server, 43), timeout=10) as sock:
                sock.sendall(f"{domain}\r\n".encode("utf-8", errors="replace"))
                chunks = []
                sock.settimeout(5)
                while True:
                    try:
                        data = sock.recv(4096)
                    except socket.timeout:
                        break
                    if not data:
                        break
                    chunks.append(data)
            text = b"".join(chunks).decode("utf-8", errors="replace")
            if text.strip():
                return text
        except (socket.timeout, socket.gaierror, OSError) as err:
            print_flush(f"    [i] {server} unreachable ({err}); trying next.")
    return None


def whois_fields(text):
    """Pull the handful of registration fields worth showing out of raw WHOIS.

    Registries disagree on spacing ("Registrar:" vs "Registrar :") and on the
    exact wording, so the line is split on the first colon and the key is
    matched as a prefix rather than a literal.
    """
    wanted = (
        "creation date", "created", "updated date",
        "registry expiry date", "expiration date", "expiry date",
        "registrant organization", "registrant country", "registrant name",
    )
    # "Registrar WHOIS Server" would otherwise match "registrar" and report
    # a hostname as though it were the registrar's name.
    excluded = ("registrar whois server", "registrar url", "registrar abuse")
    found = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in "%#*>" or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if not value or "REDACTED" in value.upper():
            continue
        if any(key.startswith(bad) for bad in excluded):
            continue
        for wanted_key in wanted:
            if key.startswith(wanted_key) and wanted_key not in found:
                found[wanted_key] = value
                break
    return found


def perform_whois(domain):
    """Performs a WHOIS lookup for the given domain."""
    print_flush("[+] Performing WHOIS lookup...")
    text = whois_lookup(domain)
    if not text:
        print_flush("    [i] No WHOIS response. Nothing to report for this domain.")
        return
    # IANA often returns a thin referral record; in that case the real data
    # is held by the registrar WHOIS server. Verisign's whois is the common
    # registrar for .com and will give us the registration dates.
    if "registrar whois server" in text.lower():
        for line in text.splitlines():
            if "registrar whois server" in line.lower():
                server = line.split(":", 1)[1].strip()
                break
        else:
            server = None
        if server and server not in ("whois.iana.org",):
            try:
                with socket.create_connection((server, 43), timeout=10) as sock:
                    sock.sendall(f"{domain}\r\n".encode("utf-8", errors="replace"))
                    chunks = []
                    sock.settimeout(5)
                    while True:
                        try:
                            data = sock.recv(4096)
                        except socket.timeout:
                            break
                        if not data:
                            break
                        chunks.append(data)
                referral = b"".join(chunks).decode("utf-8", errors="replace")
                if referral.strip():
                    text = referral
            except (socket.timeout, socket.gaierror, OSError) as err:
                print_flush(f"    [i] Referral server {server} unreachable ({err})")
    fields = whois_fields(text)
    if not fields:
        print_flush("    - WHOIS record found but contains no easily readable fields.")
    else:
        for key, value in fields.items():
            print_flush(f"    - {key.title()}: {value}")
    time.sleep(1)  # Be respectful to services


def resolve_all(domain, family):
    """Resolve a domain using the stdlib resolver."""
    try:
        infos = socket.getaddrinfo(domain, None, family)
    except socket.gaierror:
        return []
    out = []
    for info in infos:
        address = info[4][0]
        if address not in out:
            out.append(address)
    return out


def find_dns_records(domain):
    """Resolves the given domain using the platform resolver."""
    print_flush("\n[+] Resolving DNS records...")
    ipv4 = resolve_all(domain, socket.AF_INET)
    if ipv4:
        print_flush("    - Found A records:")
        for address in ipv4:
            print_flush(f"      - {address}")
    else:
        print_flush("    - No A records found.")

    ipv6 = resolve_all(domain, socket.AF_INET6)
    if ipv6:
        print_flush("    - Found AAAA records:")
        for address in ipv6:
            print_flush(f"      - {address}")
    else:
        print_flush("    - No AAAA records found.")

    # MX and NS need a DNS query, which the stdlib resolver does not expose.
    # Say so plainly rather than leaving the user to wonder why they are absent.
    print_flush("    [i] MX/NS/TXT records need dnspython, which is not installed.")
    print_flush("        pip install dnspython  — A and AAAA above are real.")
    time.sleep(1)


def find_subdomains(domain):
    """Uses a public API to find subdomains passively."""
    print_flush("\n[+] Querying HackerTarget API for subdomains...")
    if not HAVE_REQUESTS:
        print_flush("    [i] 'requests' is not installed; using urllib instead.")
        return http_hostsearch(domain)

    url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            results = response.text.splitlines()
            if not results or "error" in results[0]:
                print_flush("    - No subdomains found or API error.")
            else:
                print_flush("    - Found subdomains:")
                for line in results:
                    if "," not in line:
                        continue
                    subdomain, ip = line.split(",", 1)
                    print_flush(f"      - {subdomain} ({ip})")
        else:
            print_flush(f"    [ERROR] API returned status code: {response.status_code}")
    except Exception as err:  # noqa: BLE001
        print_flush(f"    [ERROR] An error occurred while querying the API: {err}")


def http_hostsearch(domain):
    """stdlib fallback for the same endpoint."""
    import urllib.request
    import urllib.error

    url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
    try:
        with urllib.request.urlopen(url, timeout=15) as handle:
            body = handle.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as err:
        print_flush(f"    [ERROR] An error occurred while querying the API: {err}")
        return
    results = body.splitlines()
    if not results or "error" in results[0]:
        print_flush("    - No subdomains found or API error.")
        return
    print_flush("    - Found subdomains:")
    for line in results:
        if "," in line:
            subdomain, ip = line.split(",", 1)
            print_flush(f"      - {subdomain} ({ip})")


def main(domain):
    """Main function to run all OSINT tasks."""
    print_flush(f"[*] Starting passive OSINT scan for domain: {domain}\n")

    perform_whois(domain)
    find_dns_records(domain)
    find_subdomains(domain)

    print_flush("\n[*] OSINT scan complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Functional OSINT Script")
    parser.add_argument("--domain", required=True, help="Target domain name")
    args = parser.parse_args()
    main(args.domain)