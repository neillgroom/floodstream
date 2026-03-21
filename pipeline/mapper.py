"""
Maps extracted PDF metadata → AdjusterData schema → XML output.

This is the glue between pdf_extractor (source of truth) and xml_builder (output).
Handles date normalization, field mapping, and cross-validation with Excel data.
"""

import re
from dataclasses import asdict
from typing import Optional

from xml_schema import (
    AdjusterData, Alteration, Prior, OtherInsurance, ExcludedDamages
)
from pdf_extractor import ClaimMetadata


def normalize_date_yyyymmdd(date_str: str) -> str:
    """Convert various date formats to YYYYMMDD."""
    if not date_str:
        return ""

    # Already YYYYMMDD
    if re.match(r'^\d{8}$', date_str):
        return date_str

    # M/D/YYYY or MM/DD/YYYY
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
    if m:
        return f"{m.group(3)}{int(m.group(1)):02d}{int(m.group(2)):02d}"

    # Just a year (e.g. "1962") — use 01/01
    if re.match(r'^\d{4}$', date_str):
        return f"{date_str}0101"

    return date_str


def normalize_date_mmddyyyy(date_str: str) -> str:
    """Convert various date formats to MM/DD/YYYY."""
    if not date_str:
        return ""

    # Already MM/DD/YYYY
    if re.match(r'^\d{2}/\d{2}/\d{4}$', date_str):
        return date_str

    # M/D/YYYY → zero-pad
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"

    # Just a year — use 01/01/YYYY
    if re.match(r'^\d{4}$', date_str):
        return f"01/01/{date_str}"

    return date_str


def fmt(val: str) -> str:
    """Format a numeric string to 2 decimal places, or return '0.00'."""
    if not val:
        return "0.00"
    try:
        return f"{float(val.replace(',', '')):.2f}"
    except (ValueError, AttributeError):
        return "0.00"


def map_to_adjuster_data(
    meta: ClaimMetadata,
    excel_totals: Optional[dict] = None
) -> AdjusterData:
    """
    Map extracted PDF metadata to AdjusterData XML schema.

    Args:
        meta: ClaimMetadata from pdf_extractor (SOURCE OF TRUTH)
        excel_totals: Optional cross-check totals from Excel parser.
                      Used for validation only — PDF values always win.

    Returns:
        Populated AdjusterData ready for xml_builder.
    """

    data = AdjusterData()

    # --- Identifiers ---
    data.insured_name = meta.insured_name.upper()
    data.insured_first_name = ""  # Left blank per XML convention
    data.policy_number = meta.policy_number
    data.date_of_loss = normalize_date_yyyymmdd(meta.date_of_loss)
    data.adjuster_file_number = meta.adjuster_file_number

    # --- Risk info ---
    data.risk_construction_date = normalize_date_mmddyyyy(
        meta.risk_construction_date
    )
    data.ins_at_premises = normalize_date_mmddyyyy(meta.ins_at_premises)

    # --- Property values ---
    # RCV main = the gross RCV of the building (pre-loss value)
    # If we have it from the Xactimate summary, use it; otherwise derive
    if meta.prop_val_bldg_rcv:
        data.prop_val_bldg_rcv_main = fmt(meta.prop_val_bldg_rcv)
    else:
        # Fallback: use the gross RCV loss as a proxy (not ideal)
        data.prop_val_bldg_rcv_main = fmt(meta.bldg_rcv_loss)

    data.prop_val_cont_rcv_main = fmt(meta.prop_val_cont_rcv) if meta.prop_val_cont_rcv else fmt(meta.cont_rcv_loss)

    # ACV values
    data.bldg_acv_main = fmt(meta.prop_val_bldg_acv) if meta.prop_val_bldg_acv else fmt(meta.bldg_acv_loss)
    data.cont_acv_main = fmt(meta.prop_val_cont_acv) if meta.prop_val_cont_acv else fmt(meta.cont_acv_loss)

    # --- Gross loss (RCV) ---
    data.gross_loss_bldg_rcv_main = fmt(meta.bldg_rcv_loss)
    data.gross_loss_cont_rcv_main = fmt(meta.cont_rcv_loss)

    # --- Covered damage (ACV) ---
    data.covered_damage_bldg_acv_main = fmt(meta.bldg_acv_loss)
    data.covered_damage_cont_acv_main = fmt(meta.cont_acv_loss)

    # --- Total loss (same as covered damage for most NFIP claims) ---
    data.total_loss_bldg_main = fmt(meta.bldg_acv_loss)
    data.total_loss_cont_main = fmt(meta.cont_acv_loss)

    # --- Deductibles ---
    data.less_deductible_bldg_main = fmt(meta.bldg_deductible)
    data.less_deductible_cont_main = fmt(meta.cont_deductible)

    # --- Claim payable ---
    data.claim_payable_acv_bldg_main = fmt(meta.bldg_claim_payable)
    data.claim_payable_acv_cont_main = fmt(meta.cont_claim_payable)

    # --- RC coverage ---
    data.main_bldg_rcv = data.prop_val_bldg_rcv_main
    data.ins_qualifies_for_rc_covg = "YES" if meta.qualifies_for_rc else "NO"
    data.rc_claim = fmt(meta.bldg_rc_claim)
    data.total_bldg_claim = fmt(meta.bldg_claim_payable)

    # --- Depreciation ---
    data.depreciation_bldg_main = fmt(meta.bldg_depreciation)
    data.depreciation_cont_main = fmt(meta.cont_non_recoverable_depreciation)

    # --- Cross-validation with Excel (if provided) ---
    if excel_totals:
        _cross_validate(data, meta, excel_totals)

    return data


def _cross_validate(
    data: AdjusterData,
    meta: ClaimMetadata,
    excel: dict
):
    """
    Compare PDF-extracted values against Excel-computed totals.
    Logs warnings but NEVER overrides the PDF values.
    """
    checks = [
        ("bldg_rcv", meta.bldg_rcv_loss, excel.get("bldg_rcv_total")),
        ("bldg_acv", meta.bldg_acv_loss, excel.get("bldg_acv_total")),
        ("cont_rcv", meta.cont_rcv_loss, excel.get("cont_rcv_total")),
        ("cont_acv", meta.cont_acv_loss, excel.get("cont_acv_total")),
        ("bldg_depreciation", meta.bldg_depreciation, excel.get("bldg_depreciation_total")),
    ]

    for name, pdf_val, excel_val in checks:
        if not pdf_val or not excel_val:
            continue
        try:
            pdf_num = float(pdf_val.replace(",", ""))
            excel_num = float(str(excel_val).replace(",", ""))
            delta = abs(pdf_num - excel_num)
            if delta > 0.01:
                # Flag but do NOT override — PDF is authority
                print(f"  ⚠ DELTA on {name}: PDF={pdf_num:.2f} vs Excel={excel_num:.2f} "
                      f"(Δ={delta:.2f}) — using PDF value")
        except (ValueError, TypeError):
            pass


# --- Quick test ---
if __name__ == "__main__":
    import sys
    from pdf_extractor import extract_text_from_pdf, extract_claim_metadata
    from xml_builder import build_xml

    if len(sys.argv) < 2:
        print("Usage: python mapper.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    use_ai = "--no-ai" not in sys.argv

    # Extract
    print(f"Extracting from: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    meta = extract_claim_metadata(text)
    print(f"Tier 1 (regex) confidence: {meta.confidence:.0%}")

    if meta.warnings:
        for w in meta.warnings:
            print(f"  WARNING: {w}")

    # AI validation (Tier 2 + 3)
    if use_ai:
        from ai_validation import validate_extraction
        meta = validate_extraction(text, meta)
        print(f"Post-validation confidence: {meta.confidence:.0%}")
    else:
        print("AI validation skipped (--no-ai)")

    # Map
    data = map_to_adjuster_data(meta)

    # Build XML
    xml = build_xml(data)

    # Output
    out_path = pdf_path.rsplit(".", 1)[0] + "_generated.xml"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"\nGenerated XML: {out_path}")
    print(f"\nPreview (first 50 lines):")
    for line in xml.split("\n")[:50]:
        print(line)
