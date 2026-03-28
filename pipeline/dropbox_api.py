"""
Dropbox API client for FloodStream.

Uses refresh token for permanent access — no desktop sync needed.
Searches and downloads files directly from Dropbox cloud.
"""

import os
import json
import tempfile
import httpx

# --- Load config ---
def _load_env():
    env = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

_env = _load_env()

DROPBOX_APP_KEY = os.environ.get("DROPBOX_APP_KEY", _env.get("DROPBOX_APP_KEY", ""))
DROPBOX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET", _env.get("DROPBOX_APP_SECRET", ""))
DROPBOX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN", _env.get("DROPBOX_REFRESH_TOKEN", ""))

# Cache access token in memory (expires every 4 hours)
_access_token = None
_token_expires = 0


def _get_access_token() -> str:
    """Get a fresh access token using the refresh token."""
    global _access_token, _token_expires
    import time

    if _access_token and time.time() < _token_expires - 60:
        return _access_token

    resp = httpx.post(
        "https://api.dropboxapi.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": DROPBOX_REFRESH_TOKEN,
            "client_id": DROPBOX_APP_KEY,
            "client_secret": DROPBOX_APP_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _access_token = data["access_token"]
    _token_expires = time.time() + data.get("expires_in", 14400)
    return _access_token


def is_configured() -> bool:
    """Check if Dropbox API credentials are set."""
    return bool(DROPBOX_APP_KEY and DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN)


def search_files(query: str, path: str = "/RT Claims", extensions: list[str] = None) -> list[dict]:
    """
    Search Dropbox for files matching a query.
    Returns list of {name, path, size} dicts.
    """
    if not is_configured():
        return []

    token = _get_access_token()

    # Use search_v2 for text search across filenames and paths
    resp = httpx.post(
        "https://api.dropboxapi.com/2/files/search_v2",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "options": {
                "path": path,
                "max_results": 20,
                "file_status": "active",
                "filename_only": False,
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for match in data.get("matches", []):
        metadata = match.get("metadata", {}).get("metadata", {})
        if metadata.get(".tag") != "file":
            continue
        name = metadata.get("name", "")
        file_path = metadata.get("path_display", "")

        # Filter by extensions if specified
        if extensions:
            if not any(name.lower().endswith(ext.lower()) for ext in extensions):
                continue

        results.append({
            "name": name,
            "path": file_path,
            "size": metadata.get("size", 0),
        })

    return results


def find_nol(query: str) -> list[dict]:
    """
    Search for NOL files matching an FG number or insured name.
    Returns list of {name, path, size} dicts.
    """
    # Search for NOL files matching the query
    results = search_files(query, path="/RT Claims/2025 OPEN CLAIMS JULIO")

    # Filter to only NOL files
    nol_results = []
    for r in results:
        name_lower = r["name"].lower()
        if "nol" in name_lower and (name_lower.endswith(".pdf") or name_lower.endswith(".xml")):
            nol_results.append(r)

    # If no NOL-specific results, also check broader search
    if not nol_results:
        results = search_files(query, path="/RT Claims")
        for r in results:
            name_lower = r["name"].lower()
            if "nol" in name_lower and (name_lower.endswith(".pdf") or name_lower.endswith(".xml")):
                nol_results.append(r)

    return nol_results


def download_file(dropbox_path: str, local_dir: str = None) -> str:
    """
    Download a file from Dropbox to a local temp path.
    Returns the local file path.
    """
    token = _get_access_token()

    if local_dir is None:
        local_dir = tempfile.mkdtemp(prefix="floodstream_")

    filename = os.path.basename(dropbox_path)
    local_path = os.path.join(local_dir, filename)

    resp = httpx.post(
        "https://content.dropboxapi.com/2/files/download",
        headers={
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps({"path": dropbox_path}),
        },
        timeout=30,
    )
    resp.raise_for_status()

    with open(local_path, "wb") as f:
        f.write(resp.content)

    return local_path


def find_pdf(query: str, search_path: str = "/RT Claims/2025 XACTIMATE FILES") -> list[dict]:
    """Search for PDF files matching a query (for /final and /search commands)."""
    results = search_files(query, path=search_path, extensions=[".pdf"])
    return results
