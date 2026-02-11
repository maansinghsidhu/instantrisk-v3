"""Check GitHub repos and find the correct one"""
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# List all repos
print("Listing all repos...")
resp = requests.get('https://api.github.com/user/repos?per_page=100', headers=headers)
if resp.status_code == 200:
    repos = resp.json()
    print(f"Found {len(repos)} repos:")
    for repo in repos:
        print(f"  - {repo['name']} ({repo['html_url']})")
else:
    print(f"Error: {resp.status_code} - {resp.text}")

# Check authenticated user
print("\nAuthenticated as:")
resp = requests.get('https://api.github.com/user', headers=headers)
if resp.status_code == 200:
    user = resp.json()
    print(f"  Username: {user['login']}")
    print(f"  Name: {user.get('name', 'N/A')}")
else:
    print(f"Error: {resp.status_code} - {resp.text}")
