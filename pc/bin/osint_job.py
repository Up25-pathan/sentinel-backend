# bin/osint_job.py

import argparse
import sys
import time
import requests
import whois
import dns.resolver

def print_flush(text):
    """Prints and immediately flushes the output buffer."""
    print(text)
    sys.stdout.flush()

def perform_whois(domain):
    """Performs a WHOIS lookup for the given domain."""
    print_flush("[+] Performing WHOIS lookup...")
    try:
        w = whois.whois(domain)
        if w.domain_name:
            print_flush(f"    - Domain: {w.domain_name}")
            print_flush(f"    - Registrar: {w.registrar}")
            print_flush(f"    - Creation Date: {w.creation_date}")
            print_flush(f"    - Expiration Date: {w.expiration_date}")
            # The 'name_servers' can be a list or a single string
            if isinstance(w.name_servers, list):
                print_flush(f"    - Name Servers: {', '.join(w.name_servers)}")
            else:
                print_flush(f"    - Name Servers: {w.name_servers}")
        else:
            print_flush("    - WHOIS lookup failed or domain not found.")
    except Exception as e:
        print_flush(f"    [ERROR] An error occurred during WHOIS lookup: {e}")
    time.sleep(1) # Be respectful to services

def find_dns_records(domain):
    """Finds common DNS records for the domain."""
    print_flush("\n[+] Querying for common DNS records...")
    record_types = ['A', 'AAAA', 'MX', 'TXT', 'NS']
    for rtype in record_types:
        try:
            answers = dns.resolver.resolve(domain, rtype)
            print_flush(f"    - Found {rtype} records:")
            for record in answers:
                print_flush(f"      - {record.to_text()}")
        except dns.resolver.NoAnswer:
            print_flush(f"    - No {rtype} records found.")
        except Exception as e:
            print_flush(f"    [ERROR] Could not resolve {rtype} records: {e}")
        time.sleep(1) # Be respectful to services

def find_subdomains(domain):
    """Uses a public API to find subdomains passively."""
    print_flush("\n[+] Querying HackerTarget API for subdomains...")
    # Note: This uses a public, rate-limited API. For professional use,
    # you might use a service with an API key.
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
                    subdomain, ip = line.split(',')
                    print_flush(f"      - {subdomain} ({ip})")
        else:
            print_flush(f"    [ERROR] API returned status code: {response.status_code}")
    except requests.RequestException as e:
        print_flush(f"    [ERROR] An error occurred while querying the API: {e}")

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