"""
Batch test the FloodStream pipeline against multiple final report PDFs.
Reports extraction confidence and flags any failures or missing fields.
"""

import sys
import os
from dataclasses import asdict

from pdf_extractor import extract_text_from_pdf, extract_claim_metadata
from mapper import map_to_adjuster_data
from xml_builder import build_xml


# Critical fields that must be present for a valid XML
CRITICAL_FIELDS = [
    "insured_name", "policy_number", "date_of_loss",
    "bldg_rcv_loss", "bldg_acv_loss", "bldg_claim_payable"
]

# Fields we want to verify got populated
IMPORTANT_FIELDS = [
    "adjuster_file_number", "claim_number",
    "risk_construction_date", "ins_at_premises",
    "bldg_deductible", "cont_deductible",
    "bldg_policy_limit", "cont_policy_limit",
    "prop_val_bldg_rcv", "prop_val_bldg_acv",
    "prop_val_cont_rcv", "prop_val_cont_acv",
    "bldg_depreciation", "qualifies_for_rc",
    "cont_rcv_loss", "cont_acv_loss", "cont_claim_payable",
]


def test_pdf(pdf_path: str) -> dict:
    """Test extraction pipeline against a single PDF."""
    result = {
        "file": os.path.basename(pdf_path),
        "success": False,
        "confidence": 0.0,
        "critical_missing": [],
        "important_missing": [],
        "warnings": [],
        "key_values": {},
        "error": None,
    }

    try:
        text = extract_text_from_pdf(pdf_path)
        if not text or len(text) < 100:
            result["error"] = "PDF text extraction failed or too short"
            return result

        meta = extract_claim_metadata(text)
        meta_dict = asdict(meta)

        result["confidence"] = meta.confidence
        result["warnings"] = meta.warnings

        # Check critical fields
        for f in CRITICAL_FIELDS:
            val = meta_dict.get(f)
            if not val:
                result["critical_missing"].append(f)

        # Check important fields
        for f in IMPORTANT_FIELDS:
            val = meta_dict.get(f)
            if not val and val != False:  # False is valid for booleans
                result["important_missing"].append(f)

        # Store key values for review
        for f in CRITICAL_FIELDS + ["prop_val_bldg_rcv", "prop_val_bldg_acv",
                                      "bldg_deductible", "cont_claim_payable",
                                      "bldg_depreciation", "qualifies_for_rc"]:
            result["key_values"][f] = str(meta_dict.get(f, ""))

        # Try to generate XML
        data = map_to_adjuster_data(meta)
        xml = build_xml(data)

        if "<AdjusterData>" in xml and "<policyNumber>" in xml:
            result["success"] = True

            # Write XML for inspection
            out_path = pdf_path.rsplit(".", 1)[0] + "_generated.xml"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(xml)
            result["xml_path"] = out_path

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def main():
    pdf_files = [
        r"C:\Users\neill\Downloads\8008297346FG151429BAILEYFinal.pdf",
        r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final\BACKUP\0002844992FG143743HUERTAFINAL.pdf",
        r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final\BACKUP\BEST4LESS FINAL.pdf",
        r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final\BACKUP\DOLPHIN POINTE FINAL.pdf",
        r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final\DOLPHIN POINTE FINAL 1.pdf",
        r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\Backup\605 OCEAN BLVD CONDO FINAL.pdf",
    ]

    # Filter to files that exist
    pdf_files = [f for f in pdf_files if os.path.exists(f)]

    print(f"\n{'='*70}")
    print(f"FLOODSTREAM BATCH TEST — {len(pdf_files)} PDFs")
    print(f"{'='*70}\n")

    results = []
    for pdf in pdf_files:
        print(f"Testing: {os.path.basename(pdf)}")
        r = test_pdf(pdf)
        results.append(r)

        status = "PASS" if r["success"] else "FAIL"
        conf = f"{r['confidence']:.0%}"

        if r["error"]:
            print(f"  [{status}] ERROR: {r['error']}")
        else:
            print(f"  [{status}] confidence={conf}")

            # Show key values
            print(f"    insured: {r['key_values'].get('insured_name', '?')}")
            print(f"    policy:  {r['key_values'].get('policy_number', '?')}")
            print(f"    DOL:     {r['key_values'].get('date_of_loss', '?')}")
            print(f"    bldg RCV loss: ${r['key_values'].get('bldg_rcv_loss', '?')}")
            print(f"    bldg ACV loss: ${r['key_values'].get('bldg_acv_loss', '?')}")
            print(f"    bldg payable:  ${r['key_values'].get('bldg_claim_payable', '?')}")
            print(f"    prop val RCV:  ${r['key_values'].get('prop_val_bldg_rcv', '?')}")
            print(f"    qualifies RC:  {r['key_values'].get('qualifies_for_rc', '?')}")

            if r["critical_missing"]:
                print(f"    CRITICAL MISSING: {', '.join(r['critical_missing'])}")
            if r["important_missing"]:
                print(f"    important missing: {', '.join(r['important_missing'])}")
            if r["warnings"]:
                for w in r["warnings"]:
                    print(f"    WARNING: {w}")

        print()

    # Summary
    passed = sum(1 for r in results if r["success"])
    print(f"{'='*70}")
    print(f"SUMMARY: {passed}/{len(results)} passed")

    if passed < len(results):
        print("\nFAILED:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['file']}: {r.get('error') or 'missing critical fields: ' + ', '.join(r['critical_missing'])}")

    # Aggregate missing fields
    all_missing = {}
    for r in results:
        if r["success"]:
            for f in r["important_missing"]:
                all_missing[f] = all_missing.get(f, 0) + 1

    if all_missing:
        print(f"\nMOST COMMONLY MISSING (across passing PDFs):")
        for f, count in sorted(all_missing.items(), key=lambda x: -x[1]):
            print(f"  {f}: missing in {count}/{passed} PDFs")

    print(f"{'='*70}")


if __name__ == "__main__":
    main()
