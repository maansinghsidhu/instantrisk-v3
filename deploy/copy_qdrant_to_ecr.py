"""Copy qdrant/qdrant:v1.7.4 from Docker Hub to ECR without Docker."""
import requests
import boto3
import hashlib
import os
import sys

# Config
SOURCE_REPO = "qdrant/qdrant"
SOURCE_TAG = "v1.7.4"
ECR_REGISTRY = "995306061991.dkr.ecr.us-east-1.amazonaws.com"
ECR_REPO = "instantrisk-qdrant"
REGION = "us-east-1"

def get_dockerhub_token(repo):
    resp = requests.get(
        f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"
    )
    resp.raise_for_status()
    return resp.json()["token"]

def get_ecr_token():
    ecr = boto3.client("ecr", region_name=REGION)
    resp = ecr.get_authorization_token()
    auth = resp["authorizationData"][0]
    import base64
    decoded = base64.b64decode(auth["authorizationToken"]).decode()
    username, password = decoded.split(":", 1)
    return username, password, auth["proxyEndpoint"]

def dockerhub_get(path, token, accept=None):
    headers = {"Authorization": f"Bearer {token}"}
    if accept:
        headers["Accept"] = accept
    resp = requests.get(f"https://registry-1.docker.io/v2/{path}", headers=headers)
    return resp

def ecr_push_blob(ecr_auth, digest, blob_data):
    username, password, endpoint = ecr_auth
    # Check if layer exists
    resp = requests.head(
        f"https://{ECR_REGISTRY}/v2/{ECR_REPO}/blobs/{digest}",
        auth=(username, password),
    )
    if resp.status_code == 200:
        print(f"  Layer {digest[:20]}... already exists")
        return True

    # Start upload
    resp = requests.post(
        f"https://{ECR_REGISTRY}/v2/{ECR_REPO}/blobs/uploads/",
        auth=(username, password),
    )
    if resp.status_code not in (200, 202):
        print(f"  Failed to start upload: {resp.status_code} {resp.text[:200]}")
        return False

    upload_url = resp.headers.get("Location", "")
    if not upload_url.startswith("http"):
        upload_url = f"https://{ECR_REGISTRY}{upload_url}"

    # Upload blob in one shot
    sep = "&" if "?" in upload_url else "?"
    resp = requests.put(
        f"{upload_url}{sep}digest={digest}",
        auth=(username, password),
        headers={"Content-Type": "application/octet-stream"},
        data=blob_data,
    )
    if resp.status_code not in (200, 201, 202):
        print(f"  Failed to push blob: {resp.status_code} {resp.text[:200]}")
        return False

    print(f"  Pushed layer {digest[:20]}... ({len(blob_data)} bytes)")
    return True

def ecr_push_manifest(ecr_auth, tag, manifest_data, media_type):
    username, password, endpoint = ecr_auth
    resp = requests.put(
        f"https://{ECR_REGISTRY}/v2/{ECR_REPO}/manifests/{tag}",
        auth=(username, password),
        headers={"Content-Type": media_type},
        data=manifest_data,
    )
    if resp.status_code not in (200, 201, 202):
        print(f"  Failed to push manifest: {resp.status_code} {resp.text[:500]}")
        return False
    print(f"  Pushed manifest as {tag}")
    return True

def main():
    print("=== Copying qdrant/qdrant:v1.7.4 to ECR ===")

    # Step 1: Get tokens
    print("\n1. Getting auth tokens...")
    dh_token = get_dockerhub_token(SOURCE_REPO)
    ecr_auth = get_ecr_token()
    print("   Tokens obtained")

    # Step 2: Get manifest list
    print("\n2. Getting manifest list...")
    resp = dockerhub_get(
        f"{SOURCE_REPO}/manifests/{SOURCE_TAG}",
        dh_token,
        accept="application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json",
    )
    resp.raise_for_status()
    manifest_list = resp.json()

    # Find amd64/linux
    amd64_digest = None
    for m in manifest_list.get("manifests", []):
        p = m.get("platform", {})
        if p.get("architecture") == "amd64" and p.get("os") == "linux":
            amd64_digest = m["digest"]
            break

    if not amd64_digest:
        print("ERROR: No amd64/linux manifest found")
        sys.exit(1)

    print(f"   Found amd64/linux manifest: {amd64_digest[:30]}...")

    # Step 3: Get platform manifest
    print("\n3. Getting platform manifest...")
    resp = dockerhub_get(
        f"{SOURCE_REPO}/manifests/{amd64_digest}",
        dh_token,
        accept="application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json",
    )
    resp.raise_for_status()
    manifest = resp.json()
    manifest_bytes = resp.content
    manifest_media_type = resp.headers.get("Content-Type", manifest.get("mediaType", "application/vnd.oci.image.manifest.v1+json"))

    config = manifest["config"]
    layers = manifest["layers"]
    print(f"   Config: {config['digest'][:30]}...")
    print(f"   Layers: {len(layers)}")

    # Step 4: Push config blob
    print("\n4. Pushing config blob...")
    resp = dockerhub_get(f"{SOURCE_REPO}/blobs/{config['digest']}", dh_token)
    resp.raise_for_status()
    ecr_push_blob(ecr_auth, config["digest"], resp.content)

    # Step 5: Push layer blobs
    print(f"\n5. Pushing {len(layers)} layers...")
    for i, layer in enumerate(layers):
        print(f"   Layer {i+1}/{len(layers)}: {layer['digest'][:30]}... ({layer['size']} bytes)")
        resp = dockerhub_get(f"{SOURCE_REPO}/blobs/{layer['digest']}", dh_token)
        resp.raise_for_status()
        ecr_push_blob(ecr_auth, layer["digest"], resp.content)

    # Step 6: Push manifest
    print("\n6. Pushing manifest...")
    ecr_push_manifest(ecr_auth, SOURCE_TAG, manifest_bytes, manifest_media_type)
    ecr_push_manifest(ecr_auth, "latest", manifest_bytes, manifest_media_type)

    print("\n=== Done! Image available at:")
    print(f"    {ECR_REGISTRY}/{ECR_REPO}:{SOURCE_TAG}")
    print(f"    {ECR_REGISTRY}/{ECR_REPO}:latest")

if __name__ == "__main__":
    main()
