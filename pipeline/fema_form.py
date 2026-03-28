"""
FEMA FF-206-FY-21-146 Adjuster's Preliminary Report — template-based generation.

Uses the actual accepted FEMA form as a fillable PDF template.
Form fields are overlaid at exact positions matching the real submission.
Pixel-identical output because it IS the real form.
"""

import os
from datetime import datetime

import fitz  # PyMuPDF

from prelim_schema import PrelimData

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "assets", "fema_fillable_template.pdf")


def _format_date_display(date_str: str) -> str:
    """Convert YYYYMMDD to MM/DD/YYYY."""
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[4:6]}/{date_str[6:8]}/{date_str[:4]}"
    return date_str


def _inches_to_feet_inches(inches_val: str) -> str:
    """Convert inches to 'X.XX = Y feet Z inches' display."""
    try:
        total = abs(float(inches_val))
        feet = int(total // 12)
        remaining = total % 12
        return f"{total:.2f} = {feet} feet {remaining:.0f} inches"
    except (ValueError, TypeError):
        return "0.00 = 0 feet 0 inches"


def _calculate_duration(entered: str, receded: str) -> str:
    """Calculate duration string from entered/receded datetime strings."""
    for fmt in ["%m/%d/%Y %I:%M %p", "%m/%d/%Y %I:%M%p"]:
        try:
            d1 = datetime.strptime(entered.strip(), fmt)
            d2 = datetime.strptime(receded.strip(), fmt)
            diff = max(0, int((d2 - d1).total_seconds()))
            days = diff // 86400
            hours = (diff % 86400) // 3600
            minutes = (diff % 3600) // 60
            return f"{days} Days, {hours} Hours, {minutes} Minutes"
        except ValueError:
            continue
    return "0 Days, 0 Hours, 0 Minutes"


def _foundation_display(raw: str) -> str:
    mapping = {
        "slab": "Slab-on-grade",
        "crawlspace": "Crawlspace/subgrade crawlspace",
        "basement": "Basement",
        "piles": "Elevated without enclosure (on piers, posts or piles)",
        "piers": "Elevated without enclosure (on piers, posts or piles)",
        "walls": "Walls",
        "elevated": "Elevated without enclosure (on piers, posts or piles)",
    }
    return mapping.get(raw.lower(), raw.capitalize()) if raw else ""


def _occupancy_display(raw: str) -> str:
    mapping = {
        "OWNER-OCCUPIED (PRINCIPAL RESIDENCE)": "Owner-occupied (principal residency)",
        "OWNER-OCCUPIED (SEASONAL RESIDENCE)": "Owner-occupied (non-principal residency)",
        "TENANT-OCCUPIED": "Tenant",
        "RENTAL (NOT OWNER OCCUPIED)": "Rental (not owner occupied)",
        "VACANT": "Vacant",
    }
    return mapping.get(raw, raw)


def _flood_type_display(cause: str) -> str:
    mapping = {
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
    return mapping.get(cause, cause)


def generate_fema_form(prelim: PrelimData, output_path: str, **kwargs):
    """
    Generate the FEMA preliminary report by filling the template PDF.

    Args:
        prelim: PrelimData with all fields populated
        output_path: Where to save the filled PDF
        **kwargs: carrier_name, claim_number, property_address, property_city,
                  property_state, property_zip
    """
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"FEMA template not found: {TEMPLATE_PATH}")

    doc = fitz.open(TEMPLATE_PATH)

    report_date = _format_date_display(prelim.report_date) if prelim.report_date else datetime.now().strftime("%m/%d/%Y")
    dol_display = _format_date_display(prelim.date_of_loss)
    contact_display = _format_date_display(prelim.contact_date)
    inspection_display = _format_date_display(prelim.inspection_date)

    # Parse water entered/receded into date + time parts
    entered_date = entered_time = receded_date = receded_time = ""
    if prelim.water_entered_date:
        parts = prelim.water_entered_date.split()
        entered_date = parts[0] if parts else ""
        entered_time = " ".join(parts[1:]) if len(parts) > 1 else ""
    if prelim.water_receded_date:
        parts = prelim.water_receded_date.split()
        receded_date = parts[0] if parts else ""
        receded_time = " ".join(parts[1:]) if len(parts) > 1 else ""

    duration = _calculate_duration(prelim.water_entered_date, prelim.water_receded_date)

    fill_data = {
        "report_date": report_date,
        "insured_name": prelim.insured_name.upper(),
        "carrier_name": kwargs.get("carrier_name", ""),
        "policy_number": prelim.policy_number,
        "claim_number": kwargs.get("claim_number", ""),
        "property_address": kwargs.get("property_address", ""),
        "adjuster_name": prelim.adjuster_name,
        "file_number": prelim.adjuster_file_number,
        "prop_city": kwargs.get("property_city", ""),
        "prop_state": kwargs.get("property_state", ""),
        "prop_zip": kwargs.get("property_zip", ""),
        "mail_address": kwargs.get("property_address", ""),
        "mail_city": kwargs.get("property_city", ""),
        "mail_state": kwargs.get("property_state", ""),
        "mail_zip": kwargs.get("property_zip", ""),
        "insured_email": "",
        "insured_phone": "",
        "flood_program": "Regular program",
        "sfip_type": "Dwelling Form",
        "coverage_building": f"{float(prelim.coverage_building or 0):.2f}",
        "deductible_building": "1250.00",
        "reserve_building": f"{float(prelim.reserves_building or 0):.2f}",
        "advance_building": f"{float(prelim.advance_payment_building or 0):.2f}",
        "coverage_contents": f"{float(prelim.coverage_contents or 0):.2f}",
        "deductible_contents": "1000.00",
        "reserve_contents": f"{float(prelim.reserves_content or 0):.2f}",
        "advance_contents": f"{float(prelim.advance_payment_contents or 0):.2f}",
        "num_buildings": "1",
        "building_occupancy": prelim.building_type.title() if prelim.building_type else "",
        "building_type": prelim.building_type.title() if prelim.building_type else "",
        "occupied_by": _occupancy_display(prelim.occupancy),
        "foundation_type": _foundation_display(prelim.foundation_type),
        "construction_type": "Frame",
        "num_floors": prelim.number_of_floors,
        "flood_zone": "",
        "date_of_loss": dol_display,
        "date_contacted": contact_display,
        "date_inspected": inspection_display,
        "firm_status": "Post-FIRM",
        "flooding_yes_no": "Yes",
        "inundation": "Complete",
        "inundation_area": "Two or more acres",
        "flood_in_progress": "No",
        "flood_receded": "Yes",
        "habitability": "Uninhabitable",
        "flood_type": _flood_type_display(prelim.cause),
        "report_date_p2": report_date,
        "water_entered_date": entered_date,
        "water_entered_time": entered_time,
        "water_receded_date": receded_date,
        "water_receded_time": receded_time,
        "water_duration": duration,
        "water_ext_display": _inches_to_feet_inches(prelim.water_height_external),
        "water_int_display": _inches_to_feet_inches(prelim.water_height_internal),
        "fcn": prelim.adjuster_fcn,
        "date_signed": report_date,
    }

    for page in doc:
        for widget in page.widgets():
            name = widget.field_name
            if name in fill_data:
                widget.field_value = fill_data[name]
                widget.update()

    doc.save(output_path)
    doc.close()
