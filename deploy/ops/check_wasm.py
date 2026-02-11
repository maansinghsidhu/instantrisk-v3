import requests

# Check if WASM files load from CloudFront
cf_url = "https://d2f065h47nuk0c.cloudfront.net"

wasm_files = [
    "canvaskit/canvaskit.wasm",
    "canvaskit/skwasm.wasm",
]

print("Checking WASM files on CloudFront...")
for f in wasm_files:
    url = f"{cf_url}/{f}"
    try:
        resp = requests.head(url, timeout=10)
        size = resp.headers.get('content-length', 'unknown')
        print(f"  {f}: {resp.status_code} ({size} bytes)")
    except Exception as e:
        print(f"  {f}: ERROR - {e}")

# Check if app loads
print("\nChecking main app...")
resp = requests.get(cf_url, timeout=10)
print(f"  index.html: {resp.status_code}")
if "InstantRisk" in resp.text:
    print("  ✅ Correct frontend loaded!")
