"""
Prelim PDF Assembler for FloodStream.

Assembles the complete Preliminary Report PDF stack:
  1. FEMA Adjuster's Preliminary Report form (2 pages)
  2. FCN card (1 page)
  3. Photo sheets (1 photo per page, FG header with logo)

Also generates the Prelim XML simultaneously.

Inputs:
  - PrelimData (from bot or dashboard form)
  - List of PhotoItems
  - FCN card image path

Output:
  - Combined prelim PDF
  - Prelim XML string
"""

import os
from datetime import datetime

import fitz  # PyMuPDF for merging PDFs

from prelim_schema import PrelimData
from prelim_xml_builder import build_prelim_xml
from photo_sheet import generate_photo_sheet, PhotoItem, ClaimInfo
from fema_form import generate_fema_form


# FCN card path (stored asset)
FCN_CARD_PATH = os.path.join(os.path.dirname(__file__), "assets", "fcn_card.png")


def generate_prelim_package(
    prelim: PrelimData,
    photos: list[PhotoItem],
    output_dir: str,
    carrier_address: str = "",
    carrier_name: str = "",
    claim_number: str = "",
    property_address: str = "",
    property_csz: str = "",
) -> dict:
    """
    Generate the complete prelim package: PDF + XML.

    Args:
        prelim: Populated PrelimData with all fields
        photos: List of PhotoItems for the photo sheet
        output_dir: Directory to write output files
        carrier_address: Carrier mailing address (from NOL, multi-line)
        carrier_name: Carrier name (from NOL, e.g. "NFIP Direct")
        claim_number: Claim number (from NOL)
        property_address: Property street address (from NOL)
        property_csz: Property city,state,zip (from NOL)

    Returns:
        dict with 'pdf_path', 'xml_path', 'xml_string'
    """
    os.makedirs(output_dir, exist_ok=True)

    # Base filename
    base = f"{prelim.adjuster_file_number}_{prelim.insured_name.replace(' ', '_')}"

    # 1. Generate FEMA form (pages 1-2)
    fema_path = os.path.join(output_dir, f"{base}_fema.pdf")
    generate_fema_form(prelim, fema_path)

    # 2. Generate photo sheet with FG header
    claim_info = ClaimInfo(
        insured_name=prelim.insured_name.upper(),
        date_of_report=datetime.now().strftime("%m/%d/%Y"),
        location=property_address or "",
        location_csz=property_csz or "",
        date_of_loss=_format_date_display(prelim.date_of_loss),
        policy_number=prelim.policy_number,
        company=carrier_name or "",
        company_address=carrier_address or "",
        claim_number=claim_number or "",
        fg_file_number=prelim.adjuster_file_number,
        adjuster_name=prelim.adjuster_name,
    )
    photo_path = os.path.join(output_dir, f"{base}_photos.pdf")
    if photos:
        generate_photo_sheet(claim_info, photos, photo_path)

    # 3. Generate FCN card page
    fcn_path = os.path.join(output_dir, f"{base}_fcn.pdf")
    _create_fcn_page(fcn_path)

    # 4. Merge into single PDF: FEMA form + FCN card + photos
    final_pdf_path = os.path.join(output_dir, f"{base}_PRELIM.pdf")
    _merge_pdfs(final_pdf_path, fema_path, fcn_path, photo_path if photos else None)

    # 5. Generate XML
    xml_string = build_prelim_xml(prelim)
    xml_path = os.path.join(output_dir, f"{base}_PRELIM.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_string)

    # Clean up intermediate files
    for tmp in [fema_path, photo_path, fcn_path]:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

    return {
        "pdf_path": final_pdf_path,
        "xml_path": xml_path,
        "xml_string": xml_string,
    }


def _create_fcn_page(output_path: str):
    """Create a single-page PDF with the FCN card image centered."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # Letter size

    if os.path.exists(FCN_CARD_PATH):
        # Center the FCN card image on the page
        img_rect = fitz.Rect(72, 144, 540, 648)  # Margins: 1" sides, 2" top/bottom
        page.insert_image(img_rect, filename=FCN_CARD_PATH)

    doc.save(output_path)
    doc.close()


def _merge_pdfs(output_path: str, *input_paths: str):
    """Merge multiple PDFs into one."""
    merged = fitz.open()

    for path in input_paths:
        if path and os.path.exists(path):
            doc = fitz.open(path)
            merged.insert_pdf(doc)
            doc.close()

    merged.save(output_path)
    merged.close()


def _format_date_display(date_str: str) -> str:
    """Convert YYYYMMDD to MM/DD/YYYY for display."""
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[4:6]}/{date_str[6:8]}/{date_str[:4]}"
    return date_str


# --- Quick test ---
if __name__ == "__main__":
    from prelim_schema import PrelimData

    prelim = PrelimData(
        insured_name="JYL CAPITAL INVESTORS LLC",
        policy_number="5000025672",
        date_of_loss="20260223",
        adjuster_file_number="FG152134",
        water_height_external="1.00",
        water_height_internal="-80.00",
        reserves_building="5000.00",
        reserves_content="0.00",
        contact_date="20260310",
        inspection_date="20260312",
        coverage_building="225000.00",
        coverage_contents="0.00",
        building_type="MAIN DWELLING",
        occupancy="TENANT-OCCUPIED",
        number_of_floors="2",
        foundation_type="basement",
        cause="ACCUMULATION_OF_RAINFALL_OR_SNOWMELT",
        water_entered_date="02/23/2026 12:00 PM",
        water_receded_date="02/24/2026 12:00 PM",
        water_duration="1 Days 0 Hours 0 Minutes",
    )

    # Use FCN card as placeholder photo
    test_photos = [
        PhotoItem(
            image_path=FCN_CARD_PATH,
            label="Front of Risk",
            date_taken="03/12/2026",
            comment=(
                "Risk is a single family, tenant occupied, pre firm, "
                "non elevated over a basement and located in risk zone AE. "
                'Ext wm 1". Int wm -80" in the basement. Duration 24 hours. '
                "Advance payment discussed, however insured will advise later."
            ),
        ),
        PhotoItem(
            image_path=FCN_CARD_PATH,
            label="Address",
            date_taken="03/12/2026",
        ),
    ]

    out_dir = os.path.join(os.path.dirname(__file__), "test_output")
    result = generate_prelim_package(
        prelim, test_photos, out_dir,
        carrier_name="NFIP Direct",
        carrier_address="6330 SPRING PARKWAY, SUITE 450\nOVERLAND PARK, KS, 66211",
        claim_number="N999920260107",
        property_address="811 ELSINORE PL,",
        property_csz="Chester,PA,19013",
    )

    print(f"PDF: {result['pdf_path']}")
    print(f"XML: {result['xml_path']}")
    print(f"XML preview:\n{result['xml_string'][:500]}")
