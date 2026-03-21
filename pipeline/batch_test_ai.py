"""
Batch test with AI validation enabled.
"""

import os
import sys
import time
from dataclasses import asdict

from pdf_extractor import extract_text_from_pdf, extract_claim_metadata
from ai_validation import validate_extraction
from mapper import map_to_adjuster_data
from xml_builder import build_xml


PDF_FILES = [
    r"C:\Users\neill\Downloads\8008297346FG151429BAILEYFinal.pdf",
    r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final\BACKUP\0002844992FG143743HUERTAFINAL.pdf",
    r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final\BACKUP\DOLPHIN POINTE FINAL.pdf",
    r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final\DOLPHIN POINTE FINAL 1.pdf",
    r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\Backup\605 OCEAN BLVD CONDO FINAL.pdf",
]


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY")
        sys.exit(1)

    pdfs = [f for f in PDF_FILES if os.path.exists(f)]
    print(f"\nBATCH AI VALIDATION TEST -- {len(pdfs)} PDFs\n{'='*60}\n")

    total_cost_input = 0
    total_cost_output = 0

    for pdf in pdfs:
        name = os.path.basename(pdf)
        print(f"\n{'='*60}")
        print(f"FILE: {name}")
        print(f"{'='*60}")

        start = time.time()

        # Tier 1
        text = extract_text_from_pdf(pdf)
        meta = extract_claim_metadata(text)
        print(f"  Tier 1 confidence: {meta.confidence:.0%}")

        # Tier 2 + 3
        meta = validate_extraction(text, meta)
        elapsed = time.time() - start
        print(f"  Final confidence: {meta.confidence:.0%} ({elapsed:.1f}s total)")

        # Key values
        print(f"  insured: {meta.insured_name}")
        print(f"  policy:  {meta.policy_number}")
        print(f"  bldg payable: ${meta.bldg_claim_payable}")

        # Generate XML to verify it works
        data = map_to_adjuster_data(meta)
        xml = build_xml(data)
        if "<AdjusterData>" in xml:
            print(f"  XML: OK")
        else:
            print(f"  XML: FAILED")

    # Rough cost estimate
    # ~6K tokens input per claim, ~500 tokens output
    est_input_cost = len(pdfs) * 6000 * 0.80 / 1_000_000
    est_output_cost = len(pdfs) * 500 * 4.00 / 1_000_000
    total = est_input_cost + est_output_cost
    print(f"\n{'='*60}")
    print(f"ESTIMATED COST: ${total:.4f} for {len(pdfs)} claims")
    print(f"  (${total/len(pdfs):.4f} per claim)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
