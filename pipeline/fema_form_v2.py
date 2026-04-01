"""
FEMA FF-206-FY-21-146 Preliminary Report generator.

Pixel-accurate reproduction of the official FEMA form.
Coordinates extracted from an actual accepted submission.
All positions in PDF points (1/72 inch) on a 612x842 (A4-ish) page.

The actual form uses Helvetica at 7pt for fields, 8pt for headers,
10pt for titles, 12pt bold for the main title.
"""

import os
from datetime import datetime

import fitz  # PyMuPDF

from prelim_schema import PrelimData, CAUSE_CODES


# Page dimensions (from actual PDF)
PAGE_W = 612
PAGE_H = 842

# Colors
BLACK = (0, 0, 0)
GRAY_BG = (0.85, 0.85, 0.85)  # Gray section header background
WHITE = (1, 1, 1)

# Font sizes
FONT_TITLE = 12
FONT_HEADER = 10
FONT_SUBHEADER = 9
FONT_LABEL = 7
FONT_SMALL = 8
FONT_BOLD = "helv"  # PyMuPDF built-in Helvetica


def _inches_to_feet_inches(inches_val: str) -> str:
    """Convert inches to 'X feet Y inches' display."""
    try:
        total = abs(float(inches_val))
        feet = int(total // 12)
        remaining = total % 12
        return f"{feet} feet {remaining:.0f} inches"
    except (ValueError, TypeError):
        return "0 feet 0 inches"


def _format_date_display(date_str: str) -> str:
    """Convert YYYYMMDD to MM/DD/YYYY."""
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[4:6]}/{date_str[6:8]}/{date_str[:4]}"
    return date_str


def _calculate_duration_display(entered: str, receded: str) -> str:
    """Calculate duration string from entered/receded datetime strings."""
    # Try to parse various formats
    for fmt_e, fmt_r in [
        ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %I:%M %p"),
        ("%m/%d/%Y %I:%M%p", "%m/%d/%Y %I:%M%p"),
    ]:
        try:
            d1 = datetime.strptime(entered.strip(), fmt_e)
            d2 = datetime.strptime(receded.strip(), fmt_r)
            diff = max(0, int((d2 - d1).total_seconds()))
            days = diff // 86400
            hours = (diff % 86400) // 3600
            minutes = (diff % 3600) // 60
            return f"{days} Days, {hours} Hours, {minutes} Minutes"
        except ValueError:
            continue
    return "0 Days, 0 Hours, 0 Minutes"


def _draw_gray_bar(page, y, text, width=PAGE_W - 42):
    """Draw a gray header bar with bold text."""
    rect = fitz.Rect(20, y - 2, 20 + width, y + 12)
    page.draw_rect(rect, color=None, fill=GRAY_BG)
    page.insert_text(fitz.Point(21, y + 9), text, fontsize=7, fontname="helv", color=BLACK)


def _t(page, x, y, text, size=7, bold=False):
    """Insert text at position."""
    fontname = "helv" if not bold else "helv"
    # PyMuPDF doesn't have a separate bold Helvetica built-in,
    # but we can fake it with stroke or just use regular
    page.insert_text(fitz.Point(x, y), str(text), fontsize=size, fontname="helv", color=BLACK)


def _draw_line(page, x1, y1, x2, y2):
    """Draw a thin line."""
    page.draw_line(fitz.Point(x1, y1), fitz.Point(x2, y2), color=BLACK, width=0.5)


def generate_fema_form_v2(prelim: PrelimData, output_path: str, **kwargs):
    """
    Generate the FEMA FF-206-FY-21-146 Adjuster's Preliminary Report.
    Coordinates match the actual accepted submission exactly.
    """
    doc = fitz.open()

    # Get optional kwargs
    carrier_name = kwargs.get("carrier_name", "")
    claim_number = kwargs.get("claim_number", "")
    property_address = kwargs.get("property_address", "")
    property_csz = kwargs.get("property_csz", "")
    property_city = kwargs.get("property_city", "")
    property_state = kwargs.get("property_state", "")
    property_zip = kwargs.get("property_zip", "")

    report_date = _format_date_display(prelim.report_date) if prelim.report_date else datetime.now().strftime("%m/%d/%Y")
    dol_display = _format_date_display(prelim.date_of_loss)
    contact_display = _format_date_display(prelim.contact_date)
    inspection_display = _format_date_display(prelim.inspection_date)

    # Map cause code back to display text
    cause_display = prelim.cause
    cause_type_map = {
        "rainfall": "Accumulation Rain",
        "ACCUMULATION_OF_RAINFALL_OR_SNOWMELT": "Accumulation Rain",
        "river": "Tidal Water Overflow",
        "OVERFLOW_OF_INLAND_OR_TIDAL_WATERS": "Tidal Water Overflow",
        "surge": "Storm Surge",
        "UNUSUAL_AND_RAPID_ACCUMULATION_OR_RUNOFF": "Storm Surge",
        "mudflow": "Mudflow",
        "MUDFLOW": "Mudflow",
        "erosion": "Erosion",
        "COLLAPSE_OR_SUBSIDENCE_OF_LAND": "Erosion",
    }
    flood_type = cause_type_map.get(prelim.cause, prelim.cause)

    # Foundation display
    foundation_display = prelim.foundation_type.capitalize() if prelim.foundation_type else ""
    if foundation_display.lower() in ("piles", "piers"):
        foundation_display = f"Elevated without enclosure (on piers, posts or piles)"
    elif foundation_display.lower() == "basement":
        foundation_display = "Basement"
    elif foundation_display.lower() == "crawlspace":
        foundation_display = "Crawlspace/subgrade crawlspace"
    elif foundation_display.lower() == "slab":
        foundation_display = "Slab-on-grade"

    # Occupancy display
    occupancy_map = {
        "OWNER-OCCUPIED (PRINCIPAL RESIDENCE)": "Owner-occupied (principal residency)",
        "OWNER-OCCUPIED (SEASONAL RESIDENCE)": "Owner-occupied (non-principal residency)",
        "TENANT-OCCUPIED": "Tenant",
        "RENTAL (NOT OWNER OCCUPIED)": "Rental (not owner occupied)",
        "VACANT": "Vacant",
    }
    occupancy_display = occupancy_map.get(prelim.occupancy, prelim.occupancy)

    # Building type display
    building_display = prelim.building_type.title() if prelim.building_type else ""

    # ==================== PAGE 1 ====================
    page1 = doc.new_page(width=PAGE_W, height=PAGE_H)

    # --- Header ---
    _t(page1, 20, 27, "Date", size=8)
    _t(page1, 90, 27, report_date, size=8)
    _t(page1, 210, 27, "DEPARTMENT OF HOMELAND SECURITY", size=10)
    _t(page1, 515, 26, "Adjustment Type", size=8)
    _t(page1, 214, 40, "Federal Emergency Management Agency", size=10)
    _t(page1, 536, 46, "[x]", size=10)
    _t(page1, 546, 45, "On Site", size=8)
    _t(page1, 245, 50, "National Flood Insurance Program", size=8)
    _t(page1, 536, 65, "[ ]", size=10)
    _t(page1, 545, 64, "Remote", size=8)
    _t(page1, 199, 64, "ADJUSTER'S PRELIMINARY REPORT", size=12)
    _t(page1, 261, 75, "with (select all that apply)", size=8)

    # Checkboxes row
    _t(page1, 20, 89, "[x] Initial Reserves [ ] Advance Payment Request [ ] Expert Request [ ] Subrogation Referral [ ] Underwriting Referral [ ] APDA", size=9)

    # Notice text
    _t(page1, 21, 103, "Adjusters use this form to report information to the insurer for setting reserves and initial claims reporting. NOTE: The NFIP requires that a Preliminary Report be", size=7)
    _t(page1, 21, 113, "received within 15 days of assignment", size=7)

    # --- Policyholder / Insurer info section ---
    _draw_gray_bar(page1, 119, "Policyholder information  [x] Add third - party representative(if any)")
    _t(page1, 300, 128, "Insurer information", size=7)

    # Row: Policyholder / Insurer / EDN
    _t(page1, 21, 143, "Policyholder (primary):", size=7)
    _t(page1, 110, 143, prelim.insured_name.upper(), size=7)
    _t(page1, 278, 143, "Insurer:", size=7)
    _t(page1, 311, 143, carrier_name, size=7)

    # Row: Policy # / Claim #
    _t(page1, 21, 158, "Policyholder (additional):", size=7)
    _t(page1, 278, 158, "Policy #:", size=7)
    _t(page1, 311, 158, prelim.policy_number, size=7)
    _t(page1, 478, 158, "Claim #:", size=7)
    _t(page1, 512, 158, claim_number, size=7)

    # Row: Property Address / Adjuster / File #
    _t(page1, 21, 173, "Property Address", size=7)
    _t(page1, 110, 173, property_address, size=7)
    _t(page1, 278, 173, "Adjuster:", size=7)
    _t(page1, 311, 173, "Julio Lopez", size=7)
    _t(page1, 478, 173, "File #:", size=7)
    _t(page1, 512, 173, prelim.adjuster_file_number, size=7)

    # Row: City/State/Zip / Adjusting Firm
    _t(page1, 21, 188, "City:", size=7)
    _t(page1, 39, 188, property_city, size=7)
    _t(page1, 147, 188, "State:", size=7)
    _t(page1, 169, 188, property_state, size=7)
    _t(page1, 203, 188, "Zip:", size=7)
    _t(page1, 220, 188, property_zip, size=7)
    _t(page1, 279, 188, "Adjusting Firm:", size=7)
    _t(page1, 335, 188, "Fountain Group Adjusters, LLC.", size=7)

    # Row: Mailing Address
    _t(page1, 21, 203, "Mailing Address:", size=7)
    _t(page1, 83, 203, property_address, size=7)
    _t(page1, 278, 203, "Mailing Address:", size=7)
    _t(page1, 334, 203, "PO Box 3998", size=7)

    # Row: City/State/Zip (mailing, both sides)
    _t(page1, 21, 218, "City:", size=7)
    _t(page1, 39, 218, property_city, size=7)
    _t(page1, 150, 218, "State:", size=7)
    _t(page1, 172, 218, property_state, size=7)
    _t(page1, 200, 218, "Zip:", size=7)
    _t(page1, 217, 218, property_zip, size=7)
    _t(page1, 278, 218, "City:", size=7)
    _t(page1, 305, 218, "Pineville", size=7)
    _t(page1, 378, 218, "State:", size=7)
    _t(page1, 406, 218, "LA", size=7)
    _t(page1, 478, 218, "Zip:", size=7)
    _t(page1, 506, 218, "71361", size=7)

    # Row: Phone
    _t(page1, 21, 233, "Phone# 1:", size=7)
    _t(page1, 278, 233, "Phone# 1:", size=7)
    _t(page1, 316, 233, "318-487-6557", size=7)

    # Row: Email
    _t(page1, 21, 248, "Email:", size=7)
    _t(page1, 278, 248, "Email:", size=7)
    _t(page1, 334, 248, "claims@fgclaims.com", size=7)

    # Row: Comments
    _t(page1, 21, 263, "Comments:", size=7)
    _t(page1, 278, 263, "Comments:", size=7)

    # --- Representative info ---
    _draw_gray_bar(page1, 269, "Representative information")

    # --- Insurance information ---
    _draw_gray_bar(page1, 360, "Insurance information  [ ]Other perils or insurance involved(If so explain in Adjuster's Report)")

    _t(page1, 21, 384, "Flood program type:", size=7)
    _t(page1, 97, 384, "Regular program", size=7)
    _t(page1, 199, 384, "Coverage type:", size=7)
    _t(page1, 392, 384, "Coverage", size=7)
    _t(page1, 440, 384, "Deductible", size=7)
    _t(page1, 497, 384, "Reserve", size=7)
    _t(page1, 547, 384, "Advance", size=7)

    # SFIP / Coverage A
    _t(page1, 21, 399, "SFIP policy type:", size=7)
    _t(page1, 97, 399, "Dwelling Form", size=7)
    _t(page1, 199, 399, "Coverage A - Building Property US$:", size=7)
    _t(page1, 389, 399, f"{float(prelim.coverage_building or 0):.2f}", size=7)
    _t(page1, 447, 399, "1250.00", size=7)
    _t(page1, 490, 399, f"{float(prelim.reserves_building or 0):.2f}", size=7)
    _t(page1, 560, 399, f"{float(prelim.advance_payment_building or 0):.2f}", size=7)

    # Term / Coverage B
    _t(page1, 21, 414, "Term:", size=7)
    _t(page1, 199, 414, "Coverage B - Personal Property US$:", size=7)
    _t(page1, 393, 414, f"{float(prelim.coverage_contents or 0):.2f}", size=7)
    _t(page1, 447, 414, "1000.00", size=7)
    _t(page1, 498, 414, f"{float(prelim.reserves_content or 0):.2f}", size=7)
    _t(page1, 560, 414, f"{float(prelim.advance_payment_contents or 0):.2f}", size=7)

    # Number of insured buildings
    _t(page1, 21, 429, "Number of insured buildings at described location:", size=7)
    _t(page1, 188, 429, "1", size=7)

    # --- Property risk information ---
    _draw_gray_bar(page1, 441, "Property risk information  [ ]Add comments")

    _t(page1, 21, 465, "Building occupancy:", size=7)
    _t(page1, 88, 465, building_display, size=7)
    _t(page1, 283, 465, "Ownership verified:", size=7)
    _t(page1, 350, 465, "No", size=7)
    _t(page1, 406, 465, "Current flood zone:", size=7)

    _t(page1, 21, 480, "Building type:", size=7)
    _t(page1, 71, 480, building_display, size=7)

    _t(page1, 21, 495, "Occupied by:", size=7)
    _t(page1, 71, 495, occupancy_display, size=7)
    _t(page1, 283, 495, "Under construction:", size=7)
    _t(page1, 350, 495, "No", size=7)

    _t(page1, 21, 510, "Foundation type:", size=7)
    _t(page1, 82, 510, foundation_display, size=7)

    _t(page1, 21, 525, "Construction type:", size=7)
    _t(page1, 88, 525, "Frame", size=7)
    _t(page1, 154, 525, "First floor height:", size=7)

    _t(page1, 21, 540, f"No. of floors in building(Excluding basement/enclosure):", size=7)
    _t(page1, 216, 540, prelim.number_of_floors, size=7)

    _t(page1, 21, 570, "Substantial improvements after FIRM date (if yes, explain below):", size=7)
    _t(page1, 233, 570, "[ ]  Yes  [x] No", size=7)
    _t(page1, 288, 570, "Prior flood loss(es) (if yes, explain below):", size=7)
    _t(page1, 428, 570, "[ ]  Yes  [x] No", size=7)

    _t(page1, 21, 599, "Nearest body of water to the insured property:", size=7)
    _t(page1, 283, 599, "Distance from insured property:", size=7)

    _t(page1, 21, 614, "Comments:", size=7)

    # --- Date and time information ---
    _draw_gray_bar(page1, 625, "Date and time information  [ ]Add comments")

    _t(page1, 21, 650, "Date of FIRM:", size=7)
    _t(page1, 136, 650, "FIRM status:", size=7)
    _t(page1, 205, 650, "Post-FIRM", size=7)
    _t(page1, 291, 650, "Date of loss:", size=7)
    _t(page1, 337, 650, dol_display, size=7)
    _t(page1, 383, 650, "Date assigned:", size=7)

    _t(page1, 21, 665, "Date of construction:", size=7)
    _t(page1, 136, 665, "Building age(years):", size=7)
    _t(page1, 291, 665, "Time of loss:", size=7)
    _t(page1, 383, 665, "Date contacted:", size=7)
    _t(page1, 440, 665, contact_display, size=7)

    _t(page1, 21, 680, "Date of occupancy:", size=7)
    _t(page1, 383, 680, "Date inspected:", size=7)
    _t(page1, 440, 680, inspection_display, size=7)

    _t(page1, 21, 694, "Comments:", size=7)

    # --- Cause of flood loss information ---
    _draw_gray_bar(page1, 706, "Cause of flood loss information  [ ]Add comments")

    _t(page1, 21, 730, "Was There a General and Temporary Condition of Flooding:", size=7)
    _t(page1, 216, 730, "Yes", size=7)
    _t(page1, 272, 730, "Inundation:", size=7)
    _t(page1, 316, 730, "Complete", size=7)
    _t(page1, 355, 730, "Inundation Area:", size=7)
    _t(page1, 411, 730, "Two or more acres", size=7)

    _t(page1, 21, 750, "Potential flood-in progress:", size=7)
    _t(page1, 115, 750, "No", size=7)

    _t(page1, 21, 770, "Has flood receded from building:", size=7)
    _t(page1, 127, 770, "Yes", size=7)
    _t(page1, 372, 770, "Habitability status:", size=7)
    _t(page1, 439, 770, "Uninhabitable", size=7)

    _t(page1, 21, 790, "Type of flood:", size=7)
    _t(page1, 76, 790, flood_type, size=7)
    _t(page1, 244, 790, "Other contributing cause(s) of loss (if yes, submit Subrogation Referral):", size=7)
    _t(page1, 478, 790, "[ ]  Yes  [x] No", size=7)

    _t(page1, 21, 805, "Comments:", size=7)

    _t(page1, 532, 832, "Page: 1 of 2", size=7)

    # Draw section divider lines
    for y in [117, 268, 358, 439, 623, 704]:
        _draw_line(page1, 20, y, PAGE_W - 20, y)

    # ==================== PAGE 2 ====================
    page2 = doc.new_page(width=PAGE_W, height=PAGE_H)

    # Header (same as page 1)
    _t(page2, 20, 27, "Date", size=8)
    _t(page2, 90, 27, report_date, size=8)
    _t(page2, 210, 27, "DEPARTMENT OF HOMELAND SECURITY", size=10)
    _t(page2, 214, 40, "Federal Emergency Management Agency", size=10)
    _t(page2, 245, 50, "National Flood Insurance Program", size=8)
    _t(page2, 199, 64, "ADJUSTER'S PRELIMINARY REPORT", size=12)

    # --- Flood water information ---
    _draw_gray_bar(page2, 73, "Flood water information. Main building/unit")

    # Water entered/receded
    entered_date = ""
    entered_time = ""
    receded_date = ""
    receded_time = ""
    if prelim.water_entered_date:
        parts = prelim.water_entered_date.split()
        entered_date = parts[0] if len(parts) >= 1 else ""
        entered_time = " ".join(parts[1:]) if len(parts) > 1 else ""
    if prelim.water_receded_date:
        parts = prelim.water_receded_date.split()
        receded_date = parts[0] if len(parts) >= 1 else ""
        receded_time = " ".join(parts[1:]) if len(parts) > 1 else ""

    _t(page2, 21, 96, "Approx. date water entered:", size=7)
    _t(page2, 115, 96, entered_date, size=7)
    _t(page2, 160, 96, "Approx. time water entered:", size=7)
    _t(page2, 254, 96, entered_time, size=7)
    _t(page2, 317, 96, "Exterior water height:", size=7)
    _t(page2, 405, 96, "Interior water height", size=7)

    _t(page2, 21, 111, "Approx. date water receded:", size=7)
    _t(page2, 115, 111, receded_date, size=7)
    _t(page2, 160, 111, "Approx. time water receded:", size=7)
    _t(page2, 254, 111, receded_time, size=7)
    _t(page2, 316, 111, "inches = feet & inches", size=7)
    _t(page2, 405, 111, "inches = feet & inches", size=7)

    # Duration + water heights
    duration = _calculate_duration_display(prelim.water_entered_date, prelim.water_receded_date)
    ext_fi = _inches_to_feet_inches(prelim.water_height_external)
    int_fi = _inches_to_feet_inches(prelim.water_height_internal)

    _t(page2, 21, 130, f"Approximate duration flood water in main building or unit: {duration}", size=7)
    _t(page2, 316, 130, f"{float(prelim.water_height_external or 0):.2f} = {ext_fi}", size=7)
    _t(page2, 405, 130, f"{float(prelim.water_height_internal or 0):.2f} = {int_fi}", size=7)

    # Signature line
    _draw_line(page2, 21, 150, 280, 150)
    _draw_line(page2, 290, 150, 365, 150)
    _draw_line(page2, 373, 150, 465, 150)
    _draw_line(page2, 473, 150, 575, 150)

    _t(page2, 21, 153, "Adjuster's signature:", size=7)
    _t(page2, 291, 153, "Adjuster", size=7)
    _t(page2, 374, 153, f"FCN: {prelim.adjuster_fcn}", size=7)
    _t(page2, 473, 153, f"Date signed: {report_date}", size=7)

    _t(page2, 532, 832, "Page: 2 of 2", size=7)

    # Footer
    _t(page2, 21, 842 - 10, "FEMA Form FF-206-FY-21-146 (10/21)", size=7)

    # Save
    doc.save(output_path)
    doc.close()


# --- Quick test ---
if __name__ == "__main__":
    prelim = PrelimData(
        insured_name="HAHNS KANODE",
        policy_number="6820579039",
        date_of_loss="20241009",
        adjuster_file_number="FG149855",
        water_height_external="130.00",
        water_height_internal="1.00",
        reserves_building="100000.00",
        reserves_content="5000.00",
        contact_date="20241105",
        inspection_date="20241108",
        report_date="20241110",
        coverage_building="250000.00",
        coverage_contents="91000.00",
        building_type="MAIN DWELLING",
        occupancy="OWNER-OCCUPIED (SEASONAL RESIDENCE)",
        number_of_floors="2",
        foundation_type="piles",
        cause="river",
        water_entered_date="10/09/2024 10:00 PM",
        water_receded_date="10/10/2024 10:00 AM",
        advance_payment_building="0.00",
        advance_payment_contents="0.00",
    )

    out = os.path.join(os.path.dirname(__file__), "test_output", "fema_v2_test.pdf")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    generate_fema_form_v2(
        prelim, out,
        carrier_name="First Community Insurance Company",
        claim_number="567121",
        property_address="301 S GULF BLVD UNIT 417,",
        property_city="PLACIDA",
        property_state="FL",
        property_zip="33946",
    )
    print(f"Generated: {out}")
