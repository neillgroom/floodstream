"""
FEMA Adjuster's Preliminary Report Form Generator (FF-206-FY-21-146).

Generates a 2-page PDF matching the FEMA form layout with all fields
populated from PrelimData.

Uses ReportLab for PDF generation.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import black, Color, white
from reportlab.pdfgen import canvas

from prelim_schema import PrelimData

PAGE_W, PAGE_H = letter
GRAY = Color(0.85, 0.85, 0.85)
DARK_GRAY = Color(0.3, 0.3, 0.3)
LIGHT_BG = Color(0.95, 0.95, 0.95)

# Fountain Group static info
FG_NAME = "FOUNTAIN GROUP ADJUSTERS, LLC"
FG_ADDR = "P.O. BOX 3998"
FG_CITY = "PINEVILLE"
FG_STATE = "LA"
FG_ZIP = "71361"
FG_PHONE = "(800) 604-9509"
FG_EMAIL = "CLAIMS@FGCLAIMS.COM"


def generate_fema_form(data: PrelimData, output_path: str):
    """Generate the 2-page FEMA preliminary report form."""
    c = canvas.Canvas(output_path, pagesize=letter)

    _draw_page1(c, data)
    c.showPage()
    _draw_page2(c, data)

    c.save()


def _draw_page1(c: canvas.Canvas, d: PrelimData):
    """Page 1: Header, policyholder/insurer info, coverage, property, dates, cause."""
    y = PAGE_H - 0.4 * inch

    # --- Title block ---
    c.setFont("Helvetica", 7)
    c.drawCentredString(PAGE_W / 2, y, "DEPARTMENT OF HOMELAND SECURITY")
    y -= 0.12 * inch
    c.drawCentredString(PAGE_W / 2, y, "Federal Emergency Management Agency")
    y -= 0.12 * inch
    c.drawCentredString(PAGE_W / 2, y, "National Flood Insurance Program")
    y -= 0.18 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(PAGE_W / 2, y, "ADJUSTER'S PRELIMINARY REPORT")
    y -= 0.16 * inch

    # Date and adjustment type
    c.setFont("Helvetica", 7)
    report_date = _fmt_date_display(d.report_date) or _fmt_date_display(d.inspection_date)
    c.drawString(0.5 * inch, y, f"Date: {report_date}")
    c.drawString(3.5 * inch, y, "Adjustment type: [X] On Site")
    y -= 0.12 * inch
    c.drawString(0.5 * inch, y, "with: [X] Initial Reserve")
    y -= 0.25 * inch

    # --- Policyholder info ---
    y = _section_header(c, y, "Policyholder information")
    y = _field_row(c, y, [
        ("Policyholder (primary):", d.insured_name.upper()),
        ("Insurer:", ""),
    ])
    y = _field_row(c, y, [
        ("Property address:", ""),
        ("Policy #:", d.policy_number),
    ])
    y = _field_row(c, y, [
        ("Phone #1:", ""),
        ("Claim #:", ""),
    ])
    y -= 0.1 * inch

    # --- Insurer info ---
    y = _section_header(c, y, "Insurer / Adjuster information")
    y = _field_row(c, y, [
        ("Adjuster:", d.adjuster_name),
        ("File #:", d.adjuster_file_number),
    ])
    y = _field_row(c, y, [
        ("Adjusting firm:", FG_NAME),
        ("FCN:", d.adjuster_fcn),
    ])
    y = _field_row(c, y, [
        ("Address:", f"{FG_ADDR}, {FG_CITY}, {FG_STATE} {FG_ZIP}"),
        ("Phone:", FG_PHONE),
    ])
    y -= 0.1 * inch

    # --- Coverage ---
    y = _section_header(c, y, "Insurance information")
    c.setFont("Helvetica", 7)
    y -= 0.02 * inch
    # Table header
    col_x = [0.6, 2.5, 3.8, 5.0]
    c.setFont("Helvetica-Bold", 7)
    for x, label in zip(col_x, ["Coverage type", "Coverage", "Deductible", "Reserve"]):
        c.drawString(x * inch, y, label)
    y -= 0.14 * inch
    c.setFont("Helvetica", 7)
    c.drawString(col_x[0] * inch, y, "Coverage A - Building")
    c.drawString(col_x[1] * inch, y, f"${_fmt_dollar(d.coverage_building)}")
    c.drawString(col_x[2] * inch, y, "$2,000.00")
    c.drawString(col_x[3] * inch, y, f"${_fmt_dollar(d.reserves_building)}")
    y -= 0.14 * inch
    c.drawString(col_x[0] * inch, y, "Coverage B - Contents")
    c.drawString(col_x[1] * inch, y, f"${_fmt_dollar(d.coverage_contents)}")
    c.drawString(col_x[2] * inch, y, "$2,000.00")
    c.drawString(col_x[3] * inch, y, f"${_fmt_dollar(d.reserves_content)}")
    y -= 0.14 * inch

    # Advance
    if float(d.advance_payment_building or 0) > 0 or float(d.advance_payment_contents or 0) > 0:
        c.drawString(col_x[0] * inch, y, "Advance Payment")
        c.drawString(col_x[1] * inch, y, f"Bldg: ${_fmt_dollar(d.advance_payment_building)}")
        c.drawString(col_x[2] * inch, y, f"Cont: ${_fmt_dollar(d.advance_payment_contents)}")
        y -= 0.14 * inch

    y -= 0.1 * inch

    # --- Property info ---
    y = _section_header(c, y, "Property risk information")
    y = _field_row(c, y, [
        ("Building type:", d.building_type),
        ("Occupancy:", d.occupancy),
    ])
    y = _field_row(c, y, [
        ("Foundation:", d.foundation_type),
        ("Number of floors:", d.number_of_floors),
    ])
    y = _field_row(c, y, [
        ("Elevated:", d.building_elevated or "NO"),
        ("Split level:", d.split_level or "NO"),
    ])
    y = _field_row(c, y, [
        ("Under construction:", d.under_construction),
        ("Contents type:", d.contents_type),
    ])
    y -= 0.1 * inch

    # --- Dates ---
    y = _section_header(c, y, "Date and time information")
    y = _field_row(c, y, [
        ("Date of loss:", _fmt_date_display(d.date_of_loss)),
        ("Date contacted:", _fmt_date_display(d.contact_date)),
    ])
    y = _field_row(c, y, [
        ("Date inspected:", _fmt_date_display(d.inspection_date)),
        ("Report date:", _fmt_date_display(d.report_date)),
    ])
    y -= 0.1 * inch

    # --- Cause ---
    y = _section_header(c, y, "Cause of flood loss information")
    cause_display = d.cause.replace("_", " ").title() if d.cause else ""
    y = _field_row(c, y, [
        ("Cause:", cause_display),
    ])
    y = _field_row(c, y, [
        ("General condition of flood:", "Yes"),
        ("Control failure:", d.control_failure),
    ])
    y = _field_row(c, y, [
        ("Unnatural cause:", d.unnatural_cause),
    ])

    # Footer
    c.setFont("Helvetica", 6)
    c.drawString(0.5 * inch, 0.3 * inch, "FEMA Form FF-206-FY-21-146 (10/21)")


def _draw_page2(c: canvas.Canvas, d: PrelimData):
    """Page 2: Flood water information and signature."""
    y = PAGE_H - 0.5 * inch

    # --- Flood water info ---
    y = _section_header(c, y, "Flood water information:  Main building or unit")

    ext_inches = _safe_float(d.water_height_external)
    int_inches = _safe_float(d.water_height_internal)
    ext_ft = int(abs(ext_inches)) // 12
    ext_in = int(abs(ext_inches)) % 12
    int_ft = int(abs(int_inches)) // 12
    int_in = int(abs(int_inches)) % 12
    int_sign = "-" if int_inches < 0 else ""

    y = _field_row(c, y, [
        ("Approx. date water entered:", d.water_entered_date),
    ])
    y = _field_row(c, y, [
        ("Approx. date water receded:", d.water_receded_date),
    ])
    y -= 0.05 * inch
    y = _field_row(c, y, [
        ("Exterior water height:", f"{ext_inches:.0f} inches = {ext_ft}ft. {ext_in}in."),
        ("Interior water height:", f"{int_inches:.0f} inches = {int_sign}{int_ft}ft. {int_in}in."),
    ])
    y -= 0.05 * inch

    # Duration
    duration = d.water_duration
    if not duration:
        duration = "0 Days 0 Hours 0 Minutes"
    y = _field_row(c, y, [
        ("Approximate duration flood water in main building:", duration),
    ])

    y -= 0.5 * inch

    # --- Signature block ---
    y = _section_header(c, y, "Adjuster signature")
    y -= 0.3 * inch
    c.setFont("Helvetica", 8)
    c.drawString(0.6 * inch, y, "Adjuster's signature: ___________________________")
    c.drawString(3.5 * inch, y, "Adjuster")
    c.drawString(4.8 * inch, y, f"FCN: {d.adjuster_fcn}")
    c.drawString(6.2 * inch, y, f"Date signed: {_fmt_date_display(d.inspection_date)}")

    # Footer
    c.setFont("Helvetica", 6)
    c.drawString(0.5 * inch, 0.3 * inch, "FEMA Form FF-206-FY-21-146 (10/21)")
    c.drawCentredString(PAGE_W / 2, 0.3 * inch, "Page 2 of 2")


def _section_header(c: canvas.Canvas, y: float, title: str) -> float:
    """Draw a section header bar."""
    bar_h = 0.18 * inch
    c.setFillColor(LIGHT_BG)
    c.rect(0.5 * inch, y - bar_h + 0.04 * inch, PAGE_W - 1.0 * inch, bar_h, fill=True, stroke=False)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(0.6 * inch, y - 0.08 * inch, title)
    return y - bar_h - 0.08 * inch


def _field_row(c: canvas.Canvas, y: float, fields: list[tuple[str, str]]) -> float:
    """Draw a row of label: value pairs."""
    c.setFont("Helvetica", 7)
    x = 0.6 * inch
    col_w = (PAGE_W - 1.2 * inch) / len(fields)

    for i, (label, value) in enumerate(fields):
        fx = x + i * col_w
        c.setFont("Helvetica-Bold", 7)
        c.drawString(fx, y, label)
        c.setFont("Helvetica", 7)
        label_w = c.stringWidth(label, "Helvetica-Bold", 7)
        c.drawString(fx + label_w + 4, y, str(value))

    return y - 0.16 * inch


def _fmt_date_display(date_str: str) -> str:
    """Convert YYYYMMDD to MM/DD/YYYY."""
    if not date_str:
        return ""
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[4:6]}/{date_str[6:8]}/{date_str[:4]}"
    return date_str


def _fmt_dollar(val: str) -> str:
    """Format a number string as dollar display."""
    try:
        n = float(str(val).replace(",", "").replace("$", ""))
        return f"{n:,.2f}"
    except (ValueError, TypeError):
        return "0.00"


def _safe_float(val: str) -> float:
    """Parse a string to float safely."""
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


# --- Quick test ---
if __name__ == "__main__":
    from prelim_schema import PrelimData

    d = PrelimData(
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
        foundation_type="Basement",
        cause="ACCUMULATION_OF_RAINFALL_OR_SNOWMELT",
        water_entered_date="07/31/2025 12:00 PM",
        water_receded_date="08/01/2025 00:00 AM",
        water_duration="0 Days 12 Hours 0 Minutes",
        report_date="20251024",
    )

    import os
    out = os.path.join(os.path.dirname(__file__), "test_fema_form.pdf")
    generate_fema_form(d, out)
    print(f"Generated: {out}")
