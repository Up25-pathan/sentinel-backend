# bin/web_job.py

import time
import argparse
import sys

def main(target_url):
    print(f"[*] Starting web application scan on: {target_url}")
    sys.stdout.flush()
    time.sleep(2)

    print("[+] Checking for robots.txt...")
    sys.stdout.flush()
    time.sleep(1)
    print("    - Found 2 disallowed entries: /admin, /backup")
    sys.stdout.flush()
    time.sleep(2)

    print("[+] Starting directory brute-force with feroxbuster...")
    sys.stdout.flush()
    time.sleep(3)
    print("    - 200 OK: /login.php")
    print("    - 200 OK: /dashboard.php")
    print("    - 403 FORBIDDEN: /admin")
    sys.stdout.flush()
    time.sleep(1)

    print("[*] Web scan complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Web Attack Script")
    parser.add_argument("--url", required=True, help="Target URL")
    args = parser.parse_args()
    main(args.url)