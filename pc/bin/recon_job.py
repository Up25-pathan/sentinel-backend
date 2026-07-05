import time
import argparse
import sys

def main(target_ip):
    print(f"[*] Starting reconnaissance scan on: {target_ip}")
    sys.stdout.flush()
    time.sleep(1)

    print("[+] Checking if host is alive (ICMP)...")
    sys.stdout.flush()
    time.sleep(2)
    print("    - Host is responding. TTL=64 (likely Linux)")
    sys.stdout.flush()
    time.sleep(1)

    print("[+] Performing port scan with Nmap...")
    sys.stdout.flush()
    time.sleep(3)
    print("    - 22/tcp   OPEN     SSH")
    print("    - 80/tcp   OPEN     HTTP")
    print("    - 443/tcp  OPEN     HTTPS")
    print("    - 3306/tcp OPEN     MySQL")
    sys.stdout.flush()
    time.sleep(1)

    print("[+] Enumerating service versions...")
    sys.stdout.flush()
    time.sleep(2)
    print("    - Apache 2.4.41 (Ubuntu)")
    print("    - OpenSSH 8.2p1")
    sys.stdout.flush()
    time.sleep(1)

    print("[*] Recon complete. 4 open ports found.")
    sys.stdout.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Reconnaissance Script")
    parser.add_argument("--target", required=True, help="Target IP address")
    args = parser.parse_args()
    main(args.target)
