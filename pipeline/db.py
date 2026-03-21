"""
FloodStream database client — pushes claims to Supabase.

When the Telegram bot generates an XML (final or prelim), it calls
push_claim() to insert into the claims table. The dashboard picks it up
from there for Betsy to review.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional


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
SUPABASE_URL = os.environ.get("SUPABASE_URL", _env.get("SUPABASE_URL", ""))
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", _env.get("SUPABASE_ANON_KEY", ""))


def push_claim(
    fg_number: str,
    insured_name: str,
    policy_number: str,
    date_of_loss: str,
    carrier: str,
    report_type: str,  # "prelim" or "final"
    confidence: float,
    xml_data: dict,
    xml_output: str,
    warnings: list[str] = None,
    source: str = "telegram",
) -> Optional[dict]:
    """
    Insert a claim into the Supabase claims table.
    Returns the inserted row dict, or None on failure.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("  [DB] SKIPPED — no SUPABASE_URL/KEY configured")
        return None

    payload = json.dumps({
        "fg_number": fg_number,
        "insured_name": insured_name,
        "policy_number": policy_number,
        "date_of_loss": date_of_loss,
        "carrier": carrier,
        "report_type": report_type,
        "confidence": confidence,
        "xml_data": xml_data,
        "xml_output": xml_output,
        "warnings": warnings or [],
        "source": source,
    }).encode("utf-8")

    url = f"{SUPABASE_URL}/rest/v1/claims"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "return=representation",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data:
                print(f"  [DB] Claim pushed: {data[0].get('id', '?')}")
                return data[0]
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"  [DB] HTTP {e.code}: {body[:200]}")
    except Exception as e:
        print(f"  [DB] Error: {e}")

    return None


def update_claim_status(
    claim_id: str,
    status: str,
    reviewed_by: str = "",
) -> Optional[dict]:
    """Update a claim's status (approve/reject)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None

    payload = json.dumps({
        "status": status,
        "reviewed_by": reviewed_by,
        "reviewed_at": "now()",
    }).encode("utf-8")

    url = f"{SUPABASE_URL}/rest/v1/claims?id=eq.{claim_id}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "return=representation",
        },
        method="PATCH",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data[0] if isinstance(data, list) and data else data
    except Exception as e:
        print(f"  [DB] Update error: {e}")
        return None


# --- Quick test ---
if __name__ == "__main__":
    result = push_claim(
        fg_number="FG_TEST",
        insured_name="TEST CLAIM",
        policy_number="0000000000",
        date_of_loss="01/01/2026",
        carrier="Test Carrier",
        report_type="final",
        confidence=0.99,
        xml_data={"test": True},
        xml_output="<test/>",
        warnings=["This is a test"],
        source="test",
    )
    print(f"\nResult: {result}")
