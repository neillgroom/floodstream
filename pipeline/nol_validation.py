"""
AI validation for FloodStream NOL (Notice of Loss) extraction.
Tier 2: Haiku validates regex output against raw text.
Tier 3: Sonnet full re-extraction if confidence is low.

Mirrors the ai_validation.py pattern used for Final Report PDFs,
but with NOL-specific prompts and field mappings.
"""

import json
import os
import time
from dataclasses import asdict
from typing import Optional

from nol_parser import NOLData

# --- Configuration ---
def _load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
    return key

ANTHROPIC_API_KEY = _load_api_key()
HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-5-20241022"

SONNET_FALLBACKS = [
    "claude-sonnet-4-5-20241022",
    "claude-3-5-sonnet-20241022",
    "claude-sonnet-4-20250514",
]

CONFIDENCE_THRESHOLD = 0.85
MAX_CORRECTIONS_BEFORE_ESCALATION = 3

# Critical fields for NOL — different from Final Report
NOL_CRITICAL_FIELDS = [
    "insured_name", "policy_number", "date_of_loss",
    "building_coverage", "carrier",
]


# --- Prompt Templates ---

NOL_TIER2_PROMPT = """You are a flood insurance Notice of Loss (NOL) data validator. You are given:
1. Raw text extracted from an NOL document (XML text or PDF text)
2. A JSON object of values extracted by a regex parser

Your job: compare the regex output against the raw text and identify any ERRORS or MISSING values.

RULES:
- Only flag fields where the regex got the WRONG value or missed a value that IS in the text
- Do NOT flag fields that are legitimately empty/missing from the source document
- Pay special attention to: carrier name, date of loss, policy number, coverage amounts
- Dates can vary in format but must represent the same date
- Dollar amounts must match exactly
- The raw text is the SOURCE OF TRUTH

NOL documents contain:
- Carrier / insurance company name
- Insured name and contact info
- Property address
- Policy number and claim number
- Date of loss
- Coverage limits (building and contents)
- Building information (type, floors, zone, foundation)
- Deductibles

Return a JSON object with:
{{
  "confidence": 0.0-1.0,
  "corrections": [
    {{"field": "field_name", "regex_value": "what regex got", "correct_value": "what it should be", "reason": "why"}}
  ],
  "missing_fields": [
    {{"field": "field_name", "value": "value from text", "location": "where in text"}}
  ]
}}

If the regex extraction is perfect, return {{"confidence": 1.0, "corrections": [], "missing_fields": []}}.

--- RAW DOCUMENT TEXT ---
{raw_text}

--- REGEX EXTRACTION OUTPUT ---
{regex_json}
"""

NOL_TIER3_PROMPT = """You are an NFIP flood insurance Notice of Loss (NOL) data extractor. Extract ALL of the following fields from this document text.

This could be a Wright National XML, an ASI/Progressive PDF, a Claim Assignment Form, or another carrier format.

Return a JSON object with these fields:
- carrier: Insurance company / carrier name (e.g. "Wright National", "ASI", "Progressive", "Liberty Mutual", "Selective")
- insured_name: Full name of the insured (Last, First or Last First)
- insured_first_name: First name only
- insured_phone: Phone number
- insured_email: Email address
- insured_address: Mailing address
- property_address: Property/risk location address
- property_city: City
- property_state: State
- property_zip: ZIP code
- policy_number: Policy number
- claim_number: Claim or tracking number
- date_of_loss: Date of loss (M/D/YYYY format)
- date_assigned: Date assigned to adjuster (M/D/YYYY format)
- building_coverage: Building coverage limit (number only, no $ or commas)
- contents_coverage: Contents coverage limit (number only)
- building_deductible: Building deductible (number only)
- contents_deductible: Contents deductible (number only)
- building_type: Type of building
- occupancy: Occupancy type
- number_of_floors: Number of floors/stories
- foundation_type: Foundation type
- flood_zone: Flood zone (e.g. "AE", "X", "VE")
- year_built: Year built or date of construction
- elevated: Whether building is elevated (YES/NO)
- fg_file_number: FG file number or loss file number
- cat_code: CAT code / catastrophe number
- mortgagee_name: Mortgagee / lender name

For dollar amounts, return just the number (no $ or commas), e.g. "250000".
If a field is not found in the text, use empty string "".

--- RAW DOCUMENT TEXT ---
{raw_text}
"""


def call_anthropic(prompt: str, model: str, max_tokens: int = 2000, timeout: int = 30) -> Optional[str]:
    """Call the Anthropic API directly via HTTP (no SDK dependency)."""
    import urllib.request
    import urllib.error

    if not ANTHROPIC_API_KEY:
        return None

    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"]
    except urllib.error.URLError as e:
        print(f"  [NOL AI] API error: {e}")
    except Exception as e:
        print(f"  [NOL AI] Unexpected error: {e}")

    return None


def parse_json_response(text: str) -> Optional[dict]:
    """Parse JSON from an AI response, stripping markdown fences if present."""
    if not text:
        return None

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{[\s\S]*\}', cleaned)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


def validate_nol_extraction(raw_text: str, nol: NOLData) -> NOLData:
    """
    Main entry point: run AI validation on NOL regex extraction.
    Tier 2 (Haiku validate) → Tier 3 (Sonnet if needed)
    """
    if not ANTHROPIC_API_KEY:
        print("  [NOL AI] SKIPPED — no ANTHROPIC_API_KEY")
        return nol

    return _run_nol_tier2(raw_text, nol)


def _run_nol_tier2(raw_text: str, nol: NOLData) -> NOLData:
    """Tier 2: Haiku validates regex extraction against raw text."""
    nol_dict = asdict(nol)
    # Remove non-essential fields to save tokens
    for key in ["warnings", "confidence", "has_prior_loss"]:
        nol_dict.pop(key, None)

    prompt = NOL_TIER2_PROMPT.format(
        raw_text=raw_text[:12000],  # Cap text — NOLs are short
        regex_json=json.dumps(nol_dict, indent=2),
    )

    print("  [NOL Tier 2] Calling Haiku for validation...")
    start = time.time()
    response = call_anthropic(prompt, HAIKU_MODEL, max_tokens=1500, timeout=15)
    elapsed = time.time() - start
    print(f"  [NOL Tier 2] Response in {elapsed:.1f}s")

    if not response:
        print("  [NOL Tier 2] No response — using regex output")
        return nol

    result = parse_json_response(response)
    if not result:
        print("  [NOL Tier 2] Could not parse response — using regex output")
        return nol

    tier2_confidence = result.get("confidence", 0)
    corrections = result.get("corrections", [])
    missing = result.get("missing_fields", [])

    print(f"  [NOL Tier 2] Haiku confidence: {tier2_confidence:.0%}, "
          f"corrections: {len(corrections)}, missing: {len(missing)}")

    # Apply corrections
    corrected_count = 0
    critical_corrected = False

    for c in corrections:
        field_name = c.get("field", "")
        correct_value = c.get("correct_value", "")
        if field_name and correct_value and hasattr(nol, field_name):
            old_val = getattr(nol, field_name)
            setattr(nol, field_name, correct_value)
            print(f"    CORRECTED {field_name}: '{old_val}' -> '{correct_value}' ({c.get('reason', '')})")
            corrected_count += 1
            if field_name in NOL_CRITICAL_FIELDS:
                critical_corrected = True

    for m in missing:
        field_name = m.get("field", "")
        value = m.get("value", "")
        if field_name and value and hasattr(nol, field_name):
            current = getattr(nol, field_name)
            if not current:  # Only fill if currently empty
                setattr(nol, field_name, value)
                print(f"    FILLED {field_name}: '{value}' ({m.get('location', '')})")
                corrected_count += 1
                if field_name in NOL_CRITICAL_FIELDS:
                    critical_corrected = True

    # Decide if we need Tier 3
    needs_escalation = (
        tier2_confidence < CONFIDENCE_THRESHOLD
        or corrected_count > MAX_CORRECTIONS_BEFORE_ESCALATION
        or critical_corrected
    )

    if needs_escalation:
        print(f"  [NOL Tier 2] ESCALATING to Tier 3 (confidence={tier2_confidence:.0%}, "
              f"corrections={corrected_count}, critical_corrected={critical_corrected})")
        return _run_nol_tier3(raw_text, nol)

    # Recalculate confidence with carrier included
    critical = [nol.insured_name, nol.policy_number, nol.date_of_loss,
                nol.building_coverage, nol.carrier]
    nol.confidence = sum(1 for f in critical if f) / len(critical)
    nol.confidence = max(nol.confidence, tier2_confidence)

    return nol


def _run_nol_tier3(raw_text: str, nol: NOLData) -> NOLData:
    """Tier 3: Sonnet full re-extraction of NOL data."""
    prompt = NOL_TIER3_PROMPT.format(raw_text=raw_text[:15000])

    print("  [NOL Tier 3] Calling Sonnet for full re-extraction...")
    start = time.time()
    response = None
    for model in [SONNET_MODEL] + SONNET_FALLBACKS:
        response = call_anthropic(prompt, model, max_tokens=3000, timeout=45)
        if response:
            print(f"  [NOL Tier 3] Got response using {model}")
            break
    elapsed = time.time() - start
    print(f"  [NOL Tier 3] Response in {elapsed:.1f}s")

    if not response:
        print("  [NOL Tier 3] No response — falling back to Tier 2 result")
        return nol

    result = parse_json_response(response)
    if not result:
        print("  [NOL Tier 3] Could not parse response — falling back to Tier 2 result")
        return nol

    # Apply Sonnet values — replace empty or corrected fields
    replaced = 0
    for field_name, value in result.items():
        if hasattr(nol, field_name) and value and str(value).strip():
            setattr(nol, field_name, str(value))
            replaced += 1

    print(f"  [NOL Tier 3] Sonnet replaced {replaced} fields")

    # Recalculate confidence — Sonnet extraction gets high confidence
    critical = [nol.insured_name, nol.policy_number, nol.date_of_loss,
                nol.building_coverage, nol.carrier]
    filled = sum(1 for f in critical if f)
    nol.confidence = max(0.90, filled / len(critical))  # Sonnet floor is 90%

    return nol
