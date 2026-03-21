"""
AI validation for FloodStream PDF extraction.
Tier 2: Haiku validates regex output against raw text.
Tier 3: Sonnet full re-extraction if confidence is low.

Adapted from tax-scanner-api/ai_oversight.py pattern.
Cost: ~$0.007 per claim (Haiku), ~$0.05 if Sonnet escalation needed.
"""

import json
import os
import time
from dataclasses import asdict, fields
from typing import Optional

from pdf_extractor import ClaimMetadata

# --- Configuration ---
# Load from .env if not in environment
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

# Fallback model IDs if primary returns 404
SONNET_FALLBACKS = [
    "claude-sonnet-4-5-20241022",
    "claude-3-5-sonnet-20241022",
    "claude-sonnet-4-20250514",
]

# Escalation thresholds
CONFIDENCE_THRESHOLD = 0.85
MAX_CORRECTIONS_BEFORE_ESCALATION = 5
CRITICAL_FIELDS = [
    "insured_name", "policy_number", "date_of_loss",
    "bldg_rcv_loss", "bldg_acv_loss", "bldg_claim_payable",
    "bldg_deductible", "cont_deductible",
    "prop_val_bldg_rcv",
]


# --- Prompt Templates ---

TIER2_PROMPT = """You are a flood insurance claim data validator. You are given:
1. Raw text extracted from an NFIP Final Report PDF
2. A JSON object of values extracted by a regex parser

Your job: compare the regex output against the raw text and identify any ERRORS or MISSING values.

RULES:
- Only flag fields where the regex got the WRONG value or missed a value that IS in the text
- Do NOT flag fields that are legitimately empty/missing from the source PDF
- Dollar amounts must match exactly (to the cent)
- Dates can vary in format but must represent the same date
- The PDF text is the SOURCE OF TRUTH — if regex and text disagree, the text wins

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

--- RAW PDF TEXT (first 20 pages) ---
{raw_text}

--- REGEX EXTRACTION OUTPUT ---
{regex_json}
"""

TIER3_PROMPT = """You are an NFIP flood insurance claim data extractor. Extract ALL of the following fields from this Final Report PDF text.

Return a JSON object with these fields:
- insured_name: Full name of the insured (as shown on cover page)
- insured_first_name: First name only
- policy_number: 10-digit policy number
- claim_number: Claim/file number
- adjuster_file_number: FG file number (e.g. FG151429)
- date_of_loss: Date of loss (M/D/YYYY format)
- risk_construction_date: When the building was constructed (M/D/YYYY or just year)
- ins_at_premises: When insured started at premises (M/D/YYYY or just year)
- building_type: Type of building (e.g. "2-floor, split level")
- flood_zone: Flood zone (e.g. "AE", "X", "VE")
- pre_firm: true/false — is the building pre-FIRM?
- square_footage: Building square footage
- bldg_policy_limit: Building coverage limit (dollar amount)
- cont_policy_limit: Contents coverage limit (dollar amount)
- bldg_deductible: Building deductible (dollar amount)
- cont_deductible: Contents deductible (dollar amount)
- qualifies_for_rc: true/false — does insured qualify for Replacement Cost coverage?
- bldg_rcv_loss: Building RCV loss (dollar amount from Claim Totals)
- bldg_depreciation: Building depreciation (dollar amount)
- bldg_acv_loss: Building ACV loss (dollar amount)
- bldg_claim_payable: Building claim payable (dollar amount)
- bldg_rc_claim: Building RC claim payable (dollar amount)
- cont_rcv_loss: Contents RCV loss (dollar amount)
- cont_non_recoverable_depreciation: Contents non-recoverable depreciation
- cont_acv_loss: Contents ACV loss (dollar amount)
- cont_claim_payable: Contents claim payable (dollar amount)
- prop_val_bldg_rcv: Pre-loss property value RCV for building (from Proof of Loss)
- prop_val_bldg_acv: Pre-loss property value ACV for building
- prop_val_cont_rcv: Pre-loss property value RCV for contents
- prop_val_cont_acv: Pre-loss property value ACV for contents
- has_prior_losses: true/false

For dollar amounts, return just the number (no $ or commas), e.g. "48602.93".
If a field is not found in the text, use empty string "".

--- RAW PDF TEXT ---
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
            # Extract text from response
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"]
    except urllib.error.URLError as e:
        print(f"  API error: {e}")
    except Exception as e:
        print(f"  Unexpected error: {e}")

    return None


def parse_json_response(text: str) -> Optional[dict]:
    """Parse JSON from an AI response, stripping markdown fences if present."""
    if not text:
        return None

    # Strip markdown code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (fences)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        import re
        m = re.search(r'\{[\s\S]*\}', cleaned)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


def run_tier2(raw_text: str, meta: ClaimMetadata) -> ClaimMetadata:
    """
    Tier 2: Haiku validates regex extraction.
    Returns a corrected ClaimMetadata (or original if API unavailable).
    """
    if not ANTHROPIC_API_KEY:
        print("  [Tier 2] SKIPPED — no ANTHROPIC_API_KEY")
        return meta

    # Prepare regex output as JSON
    meta_dict = asdict(meta)
    # Remove non-essential fields to save tokens
    for key in ["warnings", "confidence", "prior_loss_details"]:
        meta_dict.pop(key, None)

    prompt = TIER2_PROMPT.format(
        raw_text=raw_text[:15000],  # Cap text to ~4K tokens
        regex_json=json.dumps(meta_dict, indent=2),
    )

    print("  [Tier 2] Calling Haiku for validation...")
    start = time.time()
    response = call_anthropic(prompt, HAIKU_MODEL, max_tokens=1500, timeout=15)
    elapsed = time.time() - start
    print(f"  [Tier 2] Response in {elapsed:.1f}s")

    if not response:
        print("  [Tier 2] No response — using regex output")
        return meta

    result = parse_json_response(response)
    if not result:
        print("  [Tier 2] Could not parse response — using regex output")
        return meta

    tier2_confidence = result.get("confidence", 0)
    corrections = result.get("corrections", [])
    missing = result.get("missing_fields", [])

    print(f"  [Tier 2] Haiku confidence: {tier2_confidence:.0%}, "
          f"corrections: {len(corrections)}, missing: {len(missing)}")

    # Apply corrections
    corrected_count = 0
    critical_corrected = False

    for c in corrections:
        field_name = c.get("field", "")
        correct_value = c.get("correct_value", "")
        if field_name and correct_value and hasattr(meta, field_name):
            old_val = getattr(meta, field_name)
            setattr(meta, field_name, correct_value)
            print(f"    CORRECTED {field_name}: '{old_val}' -> '{correct_value}' ({c.get('reason', '')})")
            corrected_count += 1
            if field_name in CRITICAL_FIELDS:
                critical_corrected = True

    for m in missing:
        field_name = m.get("field", "")
        value = m.get("value", "")
        if field_name and value and hasattr(meta, field_name):
            current = getattr(meta, field_name)
            if not current:  # Only fill if currently empty
                setattr(meta, field_name, value)
                print(f"    FILLED {field_name}: '{value}' ({m.get('location', '')})")
                corrected_count += 1
                if field_name in CRITICAL_FIELDS:
                    critical_corrected = True

    # Decide if we need Tier 3 escalation
    needs_escalation = (
        tier2_confidence < CONFIDENCE_THRESHOLD
        or corrected_count > MAX_CORRECTIONS_BEFORE_ESCALATION
        or critical_corrected
    )

    if needs_escalation:
        print(f"  [Tier 2] ESCALATING to Tier 3 (confidence={tier2_confidence:.0%}, "
              f"corrections={corrected_count}, critical_corrected={critical_corrected})")
        return run_tier3(raw_text, meta)

    # Update confidence
    meta.confidence = max(meta.confidence, tier2_confidence)
    return meta


def run_tier3(raw_text: str, meta: ClaimMetadata) -> ClaimMetadata:
    """
    Tier 3: Sonnet full re-extraction.
    Only fires when Tier 2 flags low confidence or critical corrections.
    Returns re-extracted ClaimMetadata, falling back to Tier 2 result on failure.
    """
    if not ANTHROPIC_API_KEY:
        print("  [Tier 3] SKIPPED — no ANTHROPIC_API_KEY")
        return meta

    prompt = TIER3_PROMPT.format(raw_text=raw_text[:20000])

    print("  [Tier 3] Calling Sonnet for full re-extraction...")
    start = time.time()
    response = None
    for model in [SONNET_MODEL] + SONNET_FALLBACKS:
        response = call_anthropic(prompt, model, max_tokens=3000, timeout=45)
        if response:
            print(f"  [Tier 3] Got response using {model}")
            break
    elapsed = time.time() - start
    print(f"  [Tier 3] Response in {elapsed:.1f}s")

    if not response:
        print("  [Tier 3] No response — falling back to Tier 2 result")
        return meta

    result = parse_json_response(response)
    if not result:
        print("  [Tier 3] Could not parse response — falling back to Tier 2 result")
        return meta

    # Apply Sonnet values — these REPLACE the regex/Haiku values entirely
    replaced = 0
    for field_name, value in result.items():
        if hasattr(meta, field_name) and value and str(value).strip():
            # Convert booleans
            if isinstance(value, bool):
                setattr(meta, field_name, value)
            else:
                setattr(meta, field_name, str(value))
            replaced += 1

    print(f"  [Tier 3] Sonnet replaced {replaced} fields")
    meta.confidence = 0.95  # Sonnet extraction gets high confidence
    return meta


def validate_extraction(raw_text: str, meta: ClaimMetadata) -> ClaimMetadata:
    """
    Main entry point: run the full validation pipeline.
    Tier 1 (regex) → Tier 2 (Haiku validate) → Tier 3 (Sonnet if needed)
    """
    return run_tier2(raw_text, meta)


# --- Quick test ---
if __name__ == "__main__":
    import sys
    from pdf_extractor import extract_text_from_pdf, extract_claim_metadata

    if len(sys.argv) < 2:
        print("Usage: python ai_validation.py <path_to_pdf>")
        print("  Set ANTHROPIC_API_KEY env var first")
        sys.exit(1)

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("  Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"Processing: {pdf_path}")

    # Tier 1: regex
    text = extract_text_from_pdf(pdf_path)
    meta = extract_claim_metadata(text)
    print(f"\n[Tier 1] Regex confidence: {meta.confidence:.0%}")

    # Tier 2 + 3: AI validation
    meta = validate_extraction(text, meta)

    print(f"\n{'='*50}")
    print(f"FINAL RESULT (confidence: {meta.confidence:.0%})")
    print(f"{'='*50}")
    meta_dict = asdict(meta)
    for k, v in meta_dict.items():
        if v and k not in ('warnings', 'confidence', 'prior_loss_details'):
            print(f"  {k}: {v}")
