"""
Prelim XML schema — defines all fields for the NFIP Preliminary Report XML.
Fields marked as 'from_nol' are auto-extracted from the Notice of Loss.
Fields marked as 'from_inspection' require Julio's input on-site.
Fields marked as 'static' are always the same.
"""

from dataclasses import dataclass, field
from typing import Optional


# Valid cause codes for the XML
CAUSE_CODES = {
    "rainfall": "ACCUMULATION_OF_RAINFALL_OR_SNOWMELT",
    "river": "OVERFLOW_OF_INLAND_OR_TIDAL_WATERS",
    "surge": "UNUSUAL_AND_RAPID_ACCUMULATION_OR_RUNOFF",
    "mudflow": "MUDFLOW",
    "erosion": "COLLAPSE_OR_SUBSIDENCE_OF_LAND",
}

BUILDING_TYPES = [
    "MAIN DWELLING",
    "CONDO UNIT",
    "COMMERCIAL BUILDING",
    "RCBAP",
    "OTHER RESIDENTIAL",
    "MANUFACTURED/MOBILE HOME",
]

OCCUPANCY_TYPES = [
    "OWNER-OCCUPIED (PRINCIPAL RESIDENCE)",
    "OWNER-OCCUPIED (SEASONAL RESIDENCE)",
    "TENANT-OCCUPIED",
    "RENTAL (NOT OWNER OCCUPIED)",
    "VACANT",
]

FOUNDATION_TYPES = [
    "slab",
    "crawlspace",
    "basement",
    "piles",
    "piers",
    "walls",
    "elevated",
]


@dataclass
class PrelimData:
    """Complete Prelim XML schema for NFIP Preliminary Report."""

    # --- From NOL (auto-extracted) ---
    insured_name: str = ""          # from_nol
    insured_first_name: str = ""    # from_nol
    policy_number: str = ""         # from_nol
    date_of_loss: str = ""          # from_nol (YYYYMMDD)
    cat_no: str = "N/a"             # from_nol or static
    coverage_building: str = ""     # from_nol
    coverage_contents: str = ""     # from_nol

    # --- Static (always the same) ---
    adjuster_file_number: str = ""  # from venue/assignment
    adjuster_fcn: str = "0005070169"  # Julio's FCN — always
    adjuster_name: str = "Julio Lopez"  # always
    report_date: str = ""           # today's date (YYYYMMDD)

    # --- From inspection (Julio/Neill input via bot) ---
    water_height_external: str = ""     # inches
    water_height_internal: str = ""     # inches (negative = basement)
    reserves_building: str = ""         # dollar amount
    reserves_content: str = ""          # dollar amount
    advance_payment_building: str = "0.00"
    advance_payment_contents: str = "0.00"
    contact_date: str = ""              # YYYYMMDD
    inspection_date: str = ""           # YYYYMMDD
    building_type: str = ""             # from BUILDING_TYPES
    occupancy: str = ""                 # from OCCUPANCY_TYPES
    residency_type: str = ""
    number_of_floors: str = ""
    building_elevated: str = ""         # YES/NO
    split_level: str = ""               # YES/NO
    under_construction: str = "NO"
    foundation_type: str = ""           # from FOUNDATION_TYPES
    contents_type: str = "HOUSEHOLD"
    cause: str = ""                     # from CAUSE_CODES
    condition_trait: str = ""
    control_failure: str = "NO"
    unnatural_cause: str = "NO"
    water_entered_date: str = ""        # MM/DD/YYYY HH:MM AM/PM
    water_receded_date: str = ""        # MM/DD/YYYY HH:MM AM/PM
    water_duration: str = ""            # "X Days Y Hours Z Minutes"


# The questions the bot asks, in order.
# Fields with a value from defaults.json are skipped.
# Each tuple: (field_name, question_text, input_type, options_or_hint)
PRELIM_QUESTIONS = [
    # Always asked — different every inspection
    ("water_height_external", "Ext water height (inches)?", "number",
     "Positive number in inches"),
    ("water_height_internal", "Int water height (inches)?\n(-negative = basement)", "number",
     "Positive = above grade, negative = below grade"),
    ("building_type", "Building type?", "choice", BUILDING_TYPES),
    ("occupancy", "Occupancy?", "choice", OCCUPANCY_TYPES),
    ("number_of_floors", "Floors?", "number", "1, 2, 3, etc."),
    ("building_elevated", "Elevated?", "yesno", None),
    ("split_level", "Split level?", "yesno", None),
    ("foundation_type", "Foundation?", "choice", FOUNDATION_TYPES),
    ("reserves_building", "Building reserves ($)?", "dollar", "e.g. 10000"),
    ("reserves_content", "Contents reserves ($)?", "dollar", "e.g. 1000"),
    ("contact_date", "Contact date?", "date", "MM/DD/YYYY"),

    # Pre-filled $0, still asked
    ("advance_payment_building", "Advance building ($)?", "dollar", "0 if none"),
    ("advance_payment_contents", "Advance contents ($)?", "dollar", "0 if none"),

    # Defaultable — skipped when set via defaults.json
    ("cause", "Cause of flooding?", "choice", list(CAUSE_CODES.keys())),
    ("water_entered_date", "When did water enter?", "datetime",
     "MM/DD/YYYY HH:MM AM"),
    ("water_receded_date", "When did water recede?", "datetime",
     "MM/DD/YYYY HH:MM AM"),
]

# Fields that must NEVER be skipped by defaults — always different per inspection
ALWAYS_ASK = {
    "water_height_external", "water_height_internal",
    "building_type", "occupancy", "number_of_floors",
    "building_elevated", "split_level", "foundation_type",
    "reserves_building", "reserves_content", "contact_date",
    "advance_payment_building", "advance_payment_contents",
}
