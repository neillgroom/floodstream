"""
Builds the <AdjusterData> XML for Preliminary Reports from a PrelimData dataclass.
"""

import re
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from prelim_schema import PrelimData, CAUSE_CODES


def calculate_duration(entered: str, receded: str) -> str:
    """Calculate water duration from entered/receded datetime strings."""
    try:
        # Parse various formats
        for fmt in ["%m/%d/%Y %I:%M %p", "%m/%d/%Y %I:%M%p", "%m/%d/%Y %H:%M"]:
            try:
                dt_entered = datetime.strptime(entered.strip(), fmt)
                dt_receded = datetime.strptime(receded.strip(), fmt)
                break
            except ValueError:
                continue
        else:
            return "0 Days 0 Hours 0 Minutes"

        delta = dt_receded - dt_entered
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            total_seconds = 0

        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        return f"{days} Days {hours} Hours {minutes} Minutes"

    except Exception:
        return "0 Days 0 Hours 0 Minutes"


def build_prelim_xml(data: PrelimData) -> str:
    """Generate the <AdjusterData> XML for a Preliminary Report."""

    root = Element("AdjusterData")
    report = SubElement(root, "report", type="Prelim")

    # Insured info
    _t(report, "insuredName", data.insured_name.upper())
    _t(report, "insuredFirstName", data.insured_first_name)
    _t(report, "policyNumber", data.policy_number)
    _t(report, "dateOfLoss", data.date_of_loss)
    _t(report, "catNo", data.cat_no)
    _t(report, "adjusterFileNumber", data.adjuster_file_number)
    _t(report, "adjusterFCN", data.adjuster_fcn)

    # Water heights
    _t(report, "waterHeightExternal", _fmt_num(data.water_height_external))
    _t(report, "waterHeightInternal", _fmt_num(data.water_height_internal))

    # Reserves
    _t(report, "reservesBuilding", _fmt_dollar(data.reserves_building))
    _t(report, "reservesContent", _fmt_dollar(data.reserves_content))

    # Advance
    _t(report, "advancePaymentBuilding", _fmt_dollar(data.advance_payment_building))
    _t(report, "advancePaymentContents", _fmt_dollar(data.advance_payment_contents))

    # Dates
    _t(report, "adjusterInitialContactDate", data.contact_date)
    _t(report, "adjusterInitialInspectionDate", data.inspection_date)

    # Coverage
    _t(report, "coverageBuilding", _fmt_dollar(data.coverage_building))
    _t(report, "coverageContents", _fmt_dollar(data.coverage_contents))

    # Building info
    _t(report, "buildingType", data.building_type.upper())
    _t(report, "occupancy", data.occupancy.upper())
    _t(report, "residencyType", data.residency_type)
    _t(report, "numberOfFloors", data.number_of_floors)
    _t(report, "buildingElevated", data.building_elevated)
    _t(report, "bldgSplitLevel", data.split_level)
    _t(report, "underConstruction", data.under_construction)

    # Foundation
    foundation = SubElement(report, "foundationType")
    piles = SubElement(foundation, "piles")
    _t(piles, "type", "PILES" if "pile" in data.foundation_type.lower() else "")
    piers = SubElement(foundation, "piers")
    _t(piers, "type", "PIERS" if "pier" in data.foundation_type.lower() else "")
    walls = SubElement(foundation, "walls")
    _t(walls, "type", data.foundation_type.upper() if data.foundation_type.lower() not in ("piles", "piers") else "")
    _t(walls, "other", "")

    # Contents type
    contents = SubElement(report, "contentsType")
    _t(contents, "type", data.contents_type)

    # Cause
    cause_code = CAUSE_CODES.get(data.cause.lower(), data.cause.upper())
    _t(report, "cause", cause_code)
    _t(report, "condition_trait", data.condition_trait)
    _t(report, "controlFailure", data.control_failure)
    _t(report, "unnaturalCause", data.unnatural_cause)

    # Water dates
    _t(report, "enteredDate", data.water_entered_date)
    _t(report, "recededDate", data.water_receded_date)

    # Duration
    duration = data.water_duration or calculate_duration(
        data.water_entered_date, data.water_receded_date
    )
    _t(report, "timeWaterRemainedInBuilding2", duration)

    # Report info
    _t(report, "reportDate", data.report_date or datetime.now().strftime("%Y%m%d"))
    _t(report, "adjusterName", data.adjuster_name)

    # Pretty print
    rough = tostring(root, encoding="unicode")
    return parseString(rough).toprettyxml(indent="  ", encoding=None)


def _t(parent: Element, tag: str, text: str):
    el = SubElement(parent, tag)
    el.text = str(text) if text else ""
    return el


def _fmt_num(val: str) -> str:
    try:
        return f"{float(val.replace(',', '')):.2f}"
    except (ValueError, AttributeError):
        return "0.00"


def _fmt_dollar(val: str) -> str:
    try:
        return f"{float(str(val).replace(',', '').replace('$', '')):.2f}"
    except (ValueError, AttributeError):
        return "0.00"
