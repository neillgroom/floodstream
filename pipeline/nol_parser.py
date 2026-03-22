"""
NOL (Notice of Loss) Parser for FloodStream.

Handles 3 carrier formats:
  1. Wright XML — structured XML with <FloodClaimsData> root
  2. ASI/Progressive — PDF with timestamp header, "Bank Reg Unassigned" pattern
  3. Claim Assignment Form — PDF tabular layout (Selective, Liberty Mutual, NFIP Direct)

Extracts all pre-fillable prelim fields so Julio only enters inspection data.
"""

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from typing import Optional

import pdfplumber


@dataclass
class NOLData:
    """Data extracted from a Notice of Loss / Claim Assignment."""

    # Source format
    format: str = ""  # "wright_xml", "asi_pdf", "claim_assignment_pdf"

    # Insured
    insured_name: str = ""
    insured_first_name: str = ""
    insured_phone: str = ""
    insured_email: str = ""
    insured_address: str = ""
    insured_city: str = ""
    insured_state: str = ""
    insured_zip: str = ""

    # Property (may differ from mailing)
    property_address: str = ""
    property_city: str = ""
    property_state: str = ""
    property_zip: str = ""

    # Policy
    policy_number: str = ""
    claim_number: str = ""
    date_of_loss: str = ""
    date_assigned: str = ""
    policy_period_begin: str = ""
    policy_period_end: str = ""
    carrier: str = ""

    # Coverage
    building_coverage: str = ""
    contents_coverage: str = ""
    building_deductible: str = ""
    contents_deductible: str = ""
    icc_coverage: str = ""

    # Building info
    building_type: str = ""
    occupancy: str = ""
    number_of_floors: str = ""
    foundation_type: str = ""
    elevated: str = ""
    pre_post_firm: str = ""
    firm_date: str = ""
    flood_zone: str = ""
    year_built: str = ""

    # Mortgagee
    mortgagee_name: str = ""

    # Assignment
    fg_file_number: str = ""
    cat_code: str = ""

    # Prior loss
    has_prior_loss: bool = False

    # Confidence
    confidence: float = 0.0
    warnings: list = field(default_factory=list)


def detect_format(file_path: str) -> str:
    """Detect the NOL format from the file."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".xml":
        return "wright_xml"

    # Read first page of PDF
    try:
        with pdfplumber.open(file_path) as pdf:
            text = pdf.pages[0].extract_text() or ""

        if "Bank Reg Unassigned" in text or "American Strategic" in text:
            return "asi_pdf"
        if "Claim Assignment Form" in text:
            return "claim_assignment_pdf"

        # Fallback — check for common patterns
        if "Company Name" in text and "DateAssigned" in text:
            return "asi_pdf"
        if "Property Address" in text and "Tracking Number" in text:
            return "claim_assignment_pdf"

    except Exception:
        pass

    return "unknown"


def extract_raw_text(file_path: str) -> str:
    """Extract raw text from a NOL file (XML or PDF) for AI validation."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".xml":
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
            return text
    except Exception:
        return ""


def parse_nol(file_path: str, use_ai: bool = True) -> NOLData:
    """Parse any NOL format and return structured data.

    When use_ai=True and confidence < 100%, runs Haiku/Sonnet
    validation to fill gaps and correct regex errors.
    """
    fmt = detect_format(file_path)

    if fmt == "wright_xml":
        data = _parse_wright_xml(file_path)
    elif fmt == "asi_pdf":
        data = _parse_asi_pdf(file_path)
    elif fmt == "claim_assignment_pdf":
        data = _parse_claim_assignment_pdf(file_path)
    else:
        data = NOLData(format="unknown")
        data.warnings.append(f"Unknown NOL format for {os.path.basename(file_path)}")
        data = _parse_generic_pdf(file_path, data)

    # Tier 2/3: AI validation when regex didn't get everything
    if use_ai and data.confidence < 1.0:
        try:
            from nol_validation import validate_nol_extraction, ANTHROPIC_API_KEY
            if ANTHROPIC_API_KEY:
                raw_text = extract_raw_text(file_path)
                if raw_text:
                    data = validate_nol_extraction(raw_text, data)
        except Exception as e:
            data.warnings.append(f"AI validation failed: {e}")

    return data


def _parse_wright_xml(file_path: str) -> NOLData:
    """Parse Wright National XML NOL format."""
    data = NOLData(format="wright_xml", carrier="Wright National")

    tree = ET.parse(file_path)
    root = tree.getroot()

    def get(tag: str) -> str:
        el = root.find(tag)
        return (el.text or "").strip() if el is not None else ""

    # Insured
    data.insured_name = get("InsuredName")
    data.insured_first_name = get("InsuredFirstName")
    data.insured_phone = get("InsuredCellPhone") or get("InsuredHomePhone")
    data.insured_email = get("InsuredEmail")
    data.insured_address = get("InsuredAddrLine1")
    data.insured_city = get("InsuredCity")
    data.insured_state = get("InsuredState")
    data.insured_zip = get("InsuredZip")

    # Property
    data.property_address = get("PropertyLocAddrLine1") or data.insured_address
    data.property_city = get("PropertyLocCity") or data.insured_city
    data.property_state = get("PropertyLocState") or data.insured_state
    data.property_zip = get("PropertyLocZip") or data.insured_zip

    # Policy
    data.policy_number = get("PolicyNumber").strip()
    data.claim_number = get("ClaimNumber").strip()
    data.date_of_loss = get("LossDate")
    data.date_assigned = get("AdjusterDateAssigned") or get("DateAssigned")
    data.policy_period_begin = get("PolicyPeriodBeginDate")
    data.policy_period_end = get("PolicyPeriodEndDate")

    # Coverage
    data.building_coverage = get("BldgCoverageLimit")
    data.contents_coverage = get("ContentsCoverageLimit")
    data.building_deductible = get("BldgCoverageDed")
    data.contents_deductible = get("ContentsCoverageDed")
    data.icc_coverage = get("ICCCoverageLimit")

    # Building
    data.building_type = get("OccupancyType")
    data.occupancy = get("OccupancyType")
    data.number_of_floors = get("NumberOfFloors")
    data.foundation_type = get("FoundationType")
    data.elevated = get("ElevatedInd")
    data.flood_zone = get("FloodRiskZone")

    # FG file number from LossFileNumber or adjuster info
    data.fg_file_number = get("LossFileNumber")

    # Confidence — XML is highly structured
    critical = [data.insured_name, data.policy_number, data.date_of_loss,
                data.building_coverage, data.carrier]
    data.confidence = sum(1 for f in critical if f) / len(critical)

    return data


def _parse_asi_pdf(file_path: str) -> NOLData:
    """Parse ASI/Progressive PDF NOL format."""
    data = NOLData(format="asi_pdf")

    with pdfplumber.open(file_path) as pdf:
        text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"

    # Carrier
    if "American Strategic" in text:
        data.carrier = "ASI"
    elif "Progressive" in text:
        data.carrier = "Progressive"
    else:
        data.carrier = _find(r'^.*?(?:Insurance|Company).*$', text, re.MULTILINE) or "Unknown"

    # Policy number — appears after "Company Name" and "Policy Number"
    data.policy_number = _find(r'(?:FLD|Policy\s*Number)\s*[\n:]?\s*([A-Z0-9]+)', text) or ""

    # Insured name
    data.insured_name = _find(r'Insureds?\s*Name\s*\n?\s*(.+?)(?:\n|$)', text) or ""

    # Property address
    addr_match = re.search(
        r'Property\s*Location:?\s*\n?\s*(.+?)(?:\n|$)', text, re.IGNORECASE
    )
    if addr_match:
        data.property_address = addr_match.group(1).strip()
    else:
        # ASI format puts address near the top
        addr = _find(r'(\d+\s+\w+.+?(?:ST|DR|AVE|RD|BLVD|CT|CIR|LN|WAY|PL).+?\d{5})', text)
        if addr:
            data.property_address = addr

    # Date of loss
    data.date_of_loss = _find(r'Date\s*of\s*Loss:?\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""

    # Date assigned
    data.date_assigned = _find(r'DateAssigned\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""

    # Coverage
    data.building_coverage = _find_dollar(r'Dwelling:?\s*\$?([\d,]+)', text)
    data.contents_coverage = _find_dollar(r'Contents:?\s*\$?([\d,]+)', text)
    data.building_deductible = _find_dollar(r'Building\s*Deductible:?\s*\$?([\d,]+)', text)
    data.contents_deductible = _find_dollar(r'Contents\s*Deductible:?\s*\$?([\d,]+)', text)

    # Building info
    data.number_of_floors = _find(r'((?:One|Two|Three|Four|\d)\s*(?:Floor|Story))', text, re.IGNORECASE) or ""
    data.flood_zone = _find(r'Flood\s*Zone:?\s*\n?\s*([A-Z0-9]+)', text) or ""
    data.elevated = _find(r'Elevated:?\s*\n?\s*(\w+)', text) or ""
    data.pre_post_firm = _find(r'Pre\s*/?\s*Post\s*Firm:?\s*\n?\s*(\w+)', text) or ""
    data.firm_date = _find(r'Firm\s*Date:?\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""
    data.year_built = _find(r'DOC:?\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""

    # Occupancy
    for occ in ["Single Family", "Condo", "Commercial", "Residential"]:
        if occ.lower() in text.lower():
            data.occupancy = occ
            break

    # Phone
    data.insured_phone = _find(r'(?:Phone|Cell|Mobile)\s*(?:Home|Number)?:?\s*\n?\s*([\d-]{10,})', text) or ""

    # Mortgagee
    mort = _find(r'(?:1st|Mortgagee).*?:\s*\n?\s*(.+?)(?:\n|$)', text)
    if mort and len(mort) > 3:
        data.mortgagee_name = mort.strip()

    # Confidence
    critical = [data.insured_name, data.policy_number, data.date_of_loss, data.building_coverage]
    data.confidence = sum(1 for f in critical if f) / len(critical)

    return data


def _parse_claim_assignment_pdf(file_path: str) -> NOLData:
    """Parse Claim Assignment Form PDF (Selective, Liberty Mutual, NFIP Direct)."""
    data = NOLData(format="claim_assignment_pdf")

    with pdfplumber.open(file_path) as pdf:
        text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"

    # Carrier — try to find from text
    for carrier in ["Liberty Mutual", "Selective", "NFIP Direct", "Bankers",
                     "National General", "Allied", "American Family"]:
        if carrier.lower() in text.lower():
            data.carrier = carrier
            break

    # Policy number
    data.policy_number = _find(
        r'Policy\s*Number\s*\n?\s*([\d\w-]+)', text
    ) or ""

    # Claim/tracking number
    data.claim_number = _find(
        r'Tracking\s*Number\s*\n?\s*([\d]+)', text
    ) or ""

    # Dates
    data.date_of_loss = _find(r'Loss\s*Date\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""
    data.date_assigned = _find(r'Date\s*Assigned\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""

    # Insured name
    data.insured_name = _find(
        r'Insured\s*Name.*?\n?\s*(.+?)(?:\n|$)', text
    ) or ""
    # Clean up — sometimes the address is on the same line
    if data.insured_name and len(data.insured_name) > 50:
        data.insured_name = data.insured_name[:50].strip()

    # Property address
    addr = _find(r'Property\s*Address\s*\n?\s*(.+?)(?:\n|$)', text)
    if addr:
        data.property_address = addr.strip()

    # Coverage
    data.building_coverage = _find_dollar(r'Building\s*Coverage:?\s*\$?([\d,]+)', text)
    data.contents_coverage = _find_dollar(r'Contents\s*Coverage:?\s*\$?([\d,]+)', text)
    data.building_deductible = _find_dollar(r'Building\s*Deductible:?\s*\$?([\d,]+)', text)
    data.contents_deductible = _find_dollar(r'Contents\s*Deductible:?\s*\$?([\d,]+)', text)

    # Building info
    data.building_type = _find(r'Building\s*Type:?\s*\n?\s*(.+?)(?:\n|$)', text) or ""
    data.occupancy = _find(r'Occupancy:?\s*\n?\s*(.+?)(?:\n|$)', text) or ""
    data.foundation_type = _find(r'Foundation:?\s*\n?\s*(.+?)(?:\n|$)', text) or ""
    data.flood_zone = _find(r'Flood\s*Zone:?\s*\n?\s*([A-Z0-9]+)', text) or ""
    data.number_of_floors = _find(r'(?:Number.*?Floors|Floors):?\s*\n?\s*(.+?)(?:\n|$)', text, re.IGNORECASE) or ""
    data.year_built = _find(r'(?:Date.*?Construction|Year\s*Built):?\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4}|\d{4})', text) or ""
    data.elevated = _find(r'(?:Elevated|Post\s*Firm):?\s*\n?\s*(\w+)', text) or ""
    data.firm_date = _find(r'Firm\s*Date:?\s*\n?\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""

    # Phone
    data.insured_phone = _find(r'(?:Cell|Home|Phone)\s*Phone:?\s*\n?\s*([\d()-]{10,})', text) or ""
    data.insured_email = _find(r'Email:?\s*\n?\s*([\w.+-]+@[\w.-]+)', text) or ""

    # Mortgagee
    data.mortgagee_name = _find(r'Mortgagee.*?\n?\s*(.+?)(?:\n|$)', text) or ""

    # Confidence
    critical = [data.insured_name, data.policy_number, data.date_of_loss, data.building_coverage]
    data.confidence = sum(1 for f in critical if f) / len(critical)

    return data


def _parse_generic_pdf(file_path: str, data: NOLData) -> NOLData:
    """Fallback parser for unknown PDF formats."""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"

        # Try to extract whatever we can
        data.policy_number = _find(r'Policy\s*#?:?\s*([\d\w-]+)', text) or ""
        data.date_of_loss = _find(r'(?:Loss|DOL)\s*(?:Date)?:?\s*(\d{1,2}/\d{1,2}/\d{4})', text) or ""
        data.insured_name = _find(r'(?:Insured|Policyholder):?\s*(.+?)(?:\n|$)', text) or ""

        critical = [data.insured_name, data.policy_number, data.date_of_loss]
        data.confidence = sum(1 for f in critical if f) / len(critical)
    except Exception as e:
        data.warnings.append(f"Parse error: {e}")

    return data


def _find(pattern: str, text: str, flags: int = 0) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _find_dollar(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(1).replace(",", "")
    return ""


# --- Quick test ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python nol_parser.py <path_to_nol>")
        sys.exit(1)

    nol_path = sys.argv[1]
    print(f"Parsing: {nol_path}")

    data = parse_nol(nol_path)

    print(f"\nFormat: {data.format}")
    print(f"Carrier: {data.carrier}")
    print(f"Confidence: {data.confidence:.0%}")
    print(f"\nExtracted fields:")
    for k, v in asdict(data).items():
        if v and k not in ("format", "confidence", "warnings"):
            print(f"  {k}: {v}")

    if data.warnings:
        print(f"\nWarnings:")
        for w in data.warnings:
            print(f"  - {w}")
