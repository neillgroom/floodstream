"""
Prelim PDF Assembler for FloodStream.

Assembles the complete Preliminary Report PDF stack:
  1. FEMA Adjuster's Preliminary Report form (2 pages, template-based)
  2. FCN card (1 page)
  3. Photo sheets (2 photos per page, FG header with box)

Also generates the Prelim XML simultaneously.
"""

import os
from datetime import datetime

import fitz  # PyMuPDF for merging PDFs

from prelim_schema import PrelimData
from prelim_xml_builder import build_prelim_xml
from photo_sheet import generate_photo_sheets, PhotoItem
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

    Returns:
        dict with 'pdf_path', 'xml_path', 'xml_string'
    """
    os.makedirs(output_dir, exist_ok=True)

    base = f"{prelim.adjuster_file_number}_{prelim.insured_name.replace(' ', '_')}"

    # Parse property_csz into city, state, zip
    prop_city = prop_state = prop_zip = ""
    if property_csz:
        parts = [p.strip() for p in property_csz.split(",")]
        if len(parts) >= 1:
            prop_city = parts[0]
        if len(parts) >= 2:
            prop_state = parts[1]
        if len(parts) >= 3:
            prop_zip = parts[2]

    report_date = datetime.now().strftime("%m/%d/%Y")
    dol_display = _format_date_display(prelim.date_of_loss)

    # Carrier address lines
    carrier_addr1 = ""
    carrier_addr2 = ""
    if carrier_address:
        lines = carrier_address.split("\n")
        carrier_addr1 = lines[0] if len(lines) >= 1 else ""
        carrier_addr2 = lines[1] if len(lines) >= 2 else ""

    # 1. Generate FEMA form (pages 1-2) — template-based, pixel-identical
    fema_path = os.path.join(output_dir, f"{base}_fema.pdf")
    generate_fema_form(
        prelim, fema_path,
        carrier_name=carrier_name,
        claim_number=claim_number,
        property_address=property_address,
        property_city=prop_city,
        property_state=prop_state,
        property_zip=prop_zip,
    )

    # 2. Generate photo sheets (2 per page, FG header with box)
    photo_path = os.path.join(output_dir, f"{base}_photos.pdf")
    if photos:
        generate_photo_sheets(
            photos, photo_path,
            insured_name=prelim.insured_name.upper(),
            location_line1=property_address or "",
            location_line2=property_csz or "",
            company=carrier_name or "",
            company_addr1=carrier_addr1,
            company_addr2=carrier_addr2,
            date_of_report=report_date,
            date_of_loss=dol_display,
            policy_number=prelim.policy_number,
            claim_number=claim_number or "",
            file_number=prelim.adjuster_file_number,
            adjuster_name=prelim.adjuster_name,
        )

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
    page = doc.new_page(width=612, height=792)

    if os.path.exists(FCN_CARD_PATH):
        img_rect = fitz.Rect(72, 144, 540, 648)
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
