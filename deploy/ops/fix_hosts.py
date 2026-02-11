"""Add CloudFront domain to hosts file to bypass AdGuard DNS blocking."""
import os

hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
domain = "d134s4kce49b9y.cloudfront.net"
ip = "3.166.57.87"
entry = f"\n{ip}\t{domain}\n"

# Read current hosts file
with open(hosts_path, "r") as f:
    content = f.read()

if domain in content:
    print(f"Entry already exists in hosts file")
else:
    with open(hosts_path, "a") as f:
        f.write(entry)
    print(f"Added: {ip} -> {domain}")

# Flush DNS
os.system("ipconfig /flushdns")
print("DNS cache flushed")
print(f"\nNow try: https://{domain}")
