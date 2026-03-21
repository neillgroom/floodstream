"""
PDF extractor for Xactimate Final Report PDFs.
Tier 1: regex extraction from pdfplumber text.
Tier 2: Haiku validates regex output.
Tier 3: Sonnet full re-extraction if confidence is low.

The PDF is the SOURCE OF TRUTH for all summary financials.
Adapted from the tax-scanner-api pattern.
"""

import re
import pdfplumber
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ClaimMetadata:
    """Claim-level metadata extracted from the PDF narrative and cover page."""
    # Identifiers
    insured_name: str = ""
    insured_first_name: str = ""
    policy_number: str = ""
    claim_number: str = ""
    adjuster_file_number: str = ""
    date_of_loss: str = ""  # raw from PDF, normalized later to YYYYMMDD

    # Risk info
    risk_construction_date: str = ""
    ins_at_premises: str = ""
    building_type: str = ""  # e.g. "split level", "2-story"
    occupancy: str = ""  # e.g. "principal residence"
    foundation: str = ""  # e.g. "concrete slab"
    flood_zone: str = ""  # e.g. "AE"
    pre_firm: bool = False
    elevated: bool = False
    square_footage: str = ""

    # Coverage
    bldg_policy_limit: str = ""
    cont_policy_limit: str = ""
    bldg_deductible: str = ""
    cont_deductible: str = ""
    qualifies_for_rc: bool = False

    # Financials — these are THE authority, not the Excel
    bldg_rcv_loss: str = ""
    bldg_depreciation: str = ""
    bldg_acv_loss: str = ""
    bldg_claim_payable: str = ""
    bldg_rc_claim: str = ""

    cont_rcv_loss: str = ""
    cont_depreciation: str = ""
    cont_non_recoverable_depreciation: str = ""
    cont_acv_loss: str = ""
    cont_claim_payable: str = ""

    # Property values
    prop_val_bldg_rcv: str = ""
    prop_val_bldg_acv: str = ""
    prop_val_cont_rcv: str = ""
    prop_val_cont_acv: str = ""

    # Prior losses
    has_prior_losses: bool = False
    prior_loss_details: str = ""

    # Extraction confidence
    confidence: float = 0.0
    warnings: list = field(default_factory=list)


def extract_text_from_pdf(pdf_path: str, max_pages: int = 20) -> str:
    """Extract text from the first N pages of the PDF using pdfplumber."""
    combined = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            text = page.extract_text()
            if text:
                combined += f"\n--- PAGE {i+1} ---\n{text}\n"
    return combined


def extract_claim_metadata(text: str) -> ClaimMetadata:
    """Tier 1: Regex extraction of claim metadata from PDF text."""
    meta = ClaimMetadata()
    warnings = []

    # --- Identifiers ---
    meta.adjuster_file_number = _find(r'FILE\s*#:\s*(\S+)', text) or ""
    meta.policy_number = _find(r'POLICY\s*#?:?\s*(\d{10})', text) or ""
    meta.claim_number = _find(r'CLAIM\s*#?:?\s*(\d+)', text) or ""
    meta.date_of_loss = _find(r'DATE\s+OF\s+LOSS:\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""

    # Insured name — usually after "INSURED:" on cover page
    name_match = _find(r'INSURED:\s*(.+?)(?:\n|LOCATION)', text)
    if name_match:
        meta.insured_name = name_match.strip()
        parts = meta.insured_name.split()
        if parts:
            meta.insured_first_name = parts[0]

    # --- Risk info ---
    # Construction date — can be "1962" or "1/1/1956" or "01/01/1956"
    meta.risk_construction_date = _find(
        r'(?:originally\s+)?constructed\s+in\s+(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE
    ) or _find(
        r'(?:originally\s+)?constructed\s+in\s+(\d{4})', text, re.IGNORECASE
    ) or ""

    # Ownership date — "since 2002" or "since 12/1/2022"
    meta.ins_at_premises = _find(
        r'(?:owned\s+by|insured\s+since)\s+.*?(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE
    ) or _find(
        r'(?:owned\s+by|insured\s+since)\s+.*?(\d{4})', text, re.IGNORECASE
    ) or ""

    meta.square_footage = _find(
        r'BUILDING\s+SQUARE\s+FOOTAGE:\s*([\d,]+)', text
    ) or ""

    meta.flood_zone = _find(
        r'(?:located\s+in\s+)?zone\s+([A-Z]{1,3}\d*)', text, re.IGNORECASE
    ) or ""

    meta.pre_firm = bool(re.search(r'pre-firm', text, re.IGNORECASE))
    meta.elevated = not bool(re.search(r'non-elevated', text, re.IGNORECASE))

    # Foundation type
    for ftype in ['concrete slab', 'crawlspace', 'basement', 'pier', 'pilings']:
        if re.search(ftype, text, re.IGNORECASE):
            meta.foundation = ftype
            break

    # Building type
    btype = _find(
        r'risk\s+is\s+a\s+(.+?),\s+(?:principal|single|multi)', text, re.IGNORECASE
    )
    if btype:
        meta.building_type = btype.strip()

    # RC qualification
    meta.qualifies_for_rc = bool(
        re.search(r'does\s+qualify\s+for\s+Replacement\s+Cost', text, re.IGNORECASE)
    )

    # --- Coverage limits and deductibles ---
    # Pattern: "Building (Coverage A)\n$250,000.00\n$2,000.00"
    meta.bldg_policy_limit = _find_dollar(
        r'Building\s*\(Coverage\s*A\)\s*\$?([\d,]+\.?\d*)', text
    )
    meta.cont_policy_limit = _find_dollar(
        r'Contents\s*\(Coverage\s*B\)\s*\$?([\d,]+\.?\d*)', text
    )
    meta.bldg_deductible = _find_dollar(
        r'Building.*?Deductible.*?\$?([\d,]+\.?\d*)', text
    ) or _find_dollar(
        r'Building\s*\(Coverage\s*A\)\s*\$[\d,]+\.?\d*\s*\$?([\d,]+\.?\d*)', text
    )
    meta.cont_deductible = _find_dollar(
        r'Contents.*?Deductible.*?\$?([\d,]+\.?\d*)', text
    ) or _find_dollar(
        r'Contents\s*\(Coverage\s*B\)\s*\$[\d,]+\.?\d*\s*\$?([\d,]+\.?\d*)', text
    )

    # --- Financial summary (from CLAIM TOTALS section) ---
    # RCV Loss
    meta.bldg_rcv_loss = _find_dollar(
        r'RCV\s+Loss\s*\$?([\d,]+\.?\d*)', text
    )
    # Look for contents RCV after building RCV on same line
    rcv_line = _find(r'RCV\s+Loss\s*\$?[\d,]+\.?\d*\s*\$?([\d,]+\.?\d*)', text)
    if rcv_line:
        meta.cont_rcv_loss = rcv_line.replace(",", "")

    # Depreciation
    meta.bldg_depreciation = _find_dollar(
        r'Less\s+Depreciation\s*\$?([\d,]+\.?\d*)', text
    )

    # Non-recoverable depreciation
    meta.cont_non_recoverable_depreciation = _find_dollar(
        r'Non-Recoverable\s+Depreciation\s*\$?[\d,]+\.?\d*\s*\$?([\d,]+\.?\d*)', text
    ) or "0.00"

    # ACV Loss
    meta.bldg_acv_loss = _find_dollar(
        r'ACV\s+Loss\s*\$?([\d,]+\.?\d*)', text
    )
    acv_line = _find(r'ACV\s+Loss\s*\$?[\d,]+\.?\d*\s*\$?([\d,]+\.?\d*)', text)
    if acv_line:
        meta.cont_acv_loss = acv_line.replace(",", "")

    # Claim payable
    meta.bldg_claim_payable = _find_dollar(
        r'Claim\s+Payable\s*\$?([\d,]+\.?\d*)', text
    )
    cp_line = _find(r'Claim\s+Payable\s*\$?[\d,]+\.?\d*\s*\$?([\d,]+\.?\d*)', text)
    if cp_line:
        meta.cont_claim_payable = cp_line.replace(",", "")

    # RC claim
    meta.bldg_rc_claim = _find_dollar(
        r'RC\s+Claim\s+Payable\s*\$?([\d,]+\.?\d*)', text
    )

    # --- Property values (from Proof of Loss page) ---
    # The POL page has a structured column of dollar values after the deductibles.
    # Pattern: coverage limits → deductibles → coverage% → propval RCV bldg → 0 → propval RCV cont → 0
    #          → ACV 80% bldg → ACV bldg → 0 → ACV cont → 0
    # We look for the sequence: 100.00% followed by the property values
    # POL page: property values after "100.00%"
    # Dwelling format: "100.00% $391,906.05 $0.00 $100,000.00 $0.00"
    # Condo format:    "100.00% $15,597,116.00 $0.00"  (no contents columns)
    #
    # Try dwelling (4-value) format first, then fall back to 2-value
    pol_match = re.search(
        r'100\.00%\s+'
        r'\$([\d,]+\.?\d*)\s+'   # prop val bldg RCV main
        r'\$([\d,]+\.?\d*)\s+'   # prop val bldg RCV aprt OR cont RCV main
        r'\$([\d,]+\.?\d*)\s+'   # cont RCV main OR cont RCV aprt
        r'\$([\d,]+\.?\d*)',     # cont RCV aprt
        text
    )
    if pol_match:
        # 4 values: bldg_main, bldg_aprt, cont_main, cont_aprt
        # bldg_aprt is typically 0.00 for dwelling form
        meta.prop_val_bldg_rcv = pol_match.group(1).replace(",", "")
        # group 2 = bldg aprt (usually 0), group 3 = cont main
        meta.prop_val_cont_rcv = pol_match.group(3).replace(",", "")
    else:
        # 2-value format (condo/RCBAP — no separate contents columns)
        pol_match2 = re.search(
            r'100\.00%\s+'
            r'\$([\d,]+\.?\d*)\s+'  # prop val bldg RCV
            r'\$([\d,]+\.?\d*)',    # prop val bldg RCV aprt or next value
            text
        )
        if pol_match2:
            meta.prop_val_bldg_rcv = pol_match2.group(1).replace(",", "")
        else:
            meta.prop_val_bldg_rcv = _find_dollar(
                r'Replacement\s+Cost\s+Value\s*.*?\$?([\d,]+\.?\d*)', text
            )

    # ACV values: "80% of RCV: $12,477,692.80 $9,254,372.00 $0.00 ..."
    # Dwelling: 80% → bldg_80pct → bldg_acv → bldg_acv_aprt → cont_acv → cont_acv_aprt
    # Condo:    80% → bldg_80pct → bldg_acv → bldg_acv_aprt
    acv_match = re.search(
        r'80%\s+of\s+RCV:?\s+'
        r'\$([\d,]+\.?\d*)\s+'     # 80% of bldg RCV
        r'\$([\d,]+\.?\d*)\s+'     # bldg ACV main
        r'\$([\d,]+\.?\d*)',       # bldg ACV aprt or cont ACV
        text
    )
    if acv_match:
        meta.prop_val_bldg_acv = acv_match.group(2).replace(",", "")
        # Try to get cont ACV (5th value if dwelling format)
        acv_full = re.search(
            r'80%\s+of\s+RCV:?\s+'
            r'\$[\d,]+\.?\d*\s+'
            r'\$[\d,]+\.?\d*\s+'
            r'\$[\d,]+\.?\d*\s+'
            r'\$([\d,]+\.?\d*)',
            text
        )
        if acv_full:
            meta.prop_val_cont_acv = acv_full.group(1).replace(",", "")
    # (property value extraction is handled above in the POL regex block)

    # Prior losses
    meta.has_prior_losses = bool(
        re.search(r'prior\s+flood\s+claim', text, re.IGNORECASE)
    )
    if meta.has_prior_losses:
        prior_text = _find(
            r'PRIOR\s+LOSS\s+HISTORY:(.+?)(?:MORTGAGEE|CAUSE\s+OF\s+LOSS)',
            text, re.IGNORECASE | re.DOTALL
        )
        if prior_text:
            meta.prior_loss_details = prior_text.strip()[:500]

    # --- Confidence scoring ---
    critical_fields = [
        meta.insured_name, meta.policy_number, meta.date_of_loss,
        meta.bldg_rcv_loss, meta.bldg_acv_loss, meta.bldg_claim_payable
    ]
    filled = sum(1 for f in critical_fields if f)
    meta.confidence = filled / len(critical_fields)

    if meta.confidence < 0.85:
        warnings.append(f"Low confidence ({meta.confidence:.0%}): "
                       f"missing {len(critical_fields) - filled} critical fields")

    meta.warnings = warnings
    return meta


def _find(pattern: str, text: str, flags: int = 0) -> Optional[str]:
    """Find first regex match group 1."""
    m = re.search(pattern, text, flags)
    return m.group(1) if m else None


def _find_dollar(pattern: str, text: str) -> str:
    """Find a dollar amount and return as clean decimal string."""
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(1).replace(",", "")
    return ""


# --- Quick test ---
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    text = extract_text_from_pdf(pdf_path)
    meta = extract_claim_metadata(text)

    print(f"\n{'='*60}")
    print(f"EXTRACTION RESULTS (confidence: {meta.confidence:.0%})")
    print(f"{'='*60}")
    for k, v in asdict(meta).items():
        if v and k not in ('warnings', 'confidence'):
            print(f"  {k}: {v}")

    if meta.warnings:
        print(f"\nWARNINGS:")
        for w in meta.warnings:
            print(f"  ⚠ {w}")
