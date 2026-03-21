"""
Prelim PDF Assembler for FloodStream.

Assembles the complete Preliminary Report PDF stack:
  1. FEMA Adjuster's Preliminary Report form (2 pages)
  2. FCN card (1 page)
  3. Photo sheets (2 photos per page)

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
) -> dict:
    """
    Generate the complete prelim package: PDF + XML.

    Args:
        prelim: Populated PrelimData with all fields
        photos: List of PhotoItems for the photo sheet
        output_dir: Directory to write output files

    Returns:
        dict with 'pdf_path', 'xml_path', 'xml_string'
    """
    os.makedirs(output_dir, exist_ok=True)

    # Base filename
    base = f"{prelim.adjuster_file_number}_{prelim.insured_name.replace(' ', '_')}"

    # 1. Generate FEMA form (pages 1-2)
    fema_path = os.path.join(output_dir, f"{base}_fema.pdf")
    generate_fema_form(prelim, fema_path)

    # 2. Generate photo sheet
    claim_info = ClaimInfo(
        insured_name=prelim.insured_name.upper(),
        date_of_report=datetime.now().strftime("%m/%d/%Y"),
        date_of_loss=_format_date_display(prelim.date_of_loss),
        policy_number=prelim.policy_number,
        claim_number="",  # Will be filled from NOL if available
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
        insured_name="BRYAN HURLEY",
        policy_number="37115256152001",
        date_of_loss="20250731",
        adjuster_file_number="FG151849",
        water_height_external="1.00",
        water_height_internal="-84.00",
        reserves_building="10000.00",
        reserves_content="1000.00",
        contact_date="20251014",
        inspection_date="20251023",
        coverage_building="200000.00",
        coverage_contents="80000.00",
        building_type="MAIN DWELLING",
        occupancy="OWNER-OCCUPIED (PRINCIPAL RESIDENCE)",
        number_of_floors="2",
        foundation_type="basement",
        cause="ACCUMULATION_OF_RAINFALL_OR_SNOWMELT",
        water_entered_date="07/31/2025 12:00 PM",
        water_receded_date="08/01/2025 00:00 AM",
        water_duration="0 Days 12 Hours 0 Minutes",
    )

    # Use FCN card as placeholder photo
    test_photos = [
        PhotoItem(
            image_path=FCN_CARD_PATH,
            label="FRONT OF RISK",
            date_taken="10/23/2025",
            comment="Test photo — front view of property.",
        ),
        PhotoItem(
            image_path=FCN_CARD_PATH,
            label="ADDRESS",
            date_taken="10/23/2025",
        ),
    ]

    out_dir = os.path.join(os.path.dirname(__file__), "test_output")
    result = generate_prelim_package(prelim, test_photos, out_dir)

    print(f"PDF: {result['pdf_path']}")
    print(f"XML: {result['xml_path']}")
    print(f"XML preview:\n{result['xml_string'][:500]}")
