"""
AdjusterData XML schema — defines all fields and their types for the NFIP Final XML.

The PDF is the source of truth for all summary financials.
The Excel provides line-item detail for narrative generation and cross-checks.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Alteration:
    date: str = ""
    description: str = ""
    market_value: str = ""
    cost: str = ""
    type: str = ""
    substantial_improvement: str = "NO"


@dataclass
class Prior:
    date: str = ""
    amount: str = ""
    repairs_completed: str = "NO"
    insured: str = "NO"
    no_claim: str = "NO"


@dataclass
class OtherInsurance:
    company: str = ""
    type: str = "HOMEOWNERS"
    policy_number: str = ""
    building_coverage: str = "0.00"
    contents_coverage: str = "0.00"
    flood_coverage: str = "NO"
    duration: str = "2TO4WEEKS"


@dataclass
class ExcludedDamages:
    excluded_building_value: str = "LESS_THAN_ONE_THOUSAND"
    excluded_building_damage: str = "LESS_THAN_ONE_THOUSAND"
    excluded_contents_value: str = "LESS_THAN_ONE_THOUSAND"
    excluded_contents_damage: str = "LESS_THAN_ONE_THOUSAND"


@dataclass
class AdjusterData:
    """Complete AdjusterData schema for NFIP Final XML (Dwelling Form)."""

    # Report type
    report_type: str = "FINAL"

    # Insured info
    insured_name: str = ""
    insured_first_name: str = ""
    policy_number: str = ""
    date_of_loss: str = ""  # YYYYMMDD format
    adjuster_file_number: str = ""

    # Risk info
    risk_construction_date: str = ""  # MM/DD/YYYY
    ins_at_premises: str = ""  # MM/DD/YYYY

    # Alterations (up to 3)
    alterations: list = field(default_factory=lambda: [Alteration() for _ in range(3)])

    # Prior losses (up to 3)
    priors: list = field(default_factory=lambda: [Prior() for _ in range(3)])

    # Other insurance
    other_insurance: OtherInsurance = field(default_factory=OtherInsurance)

    # Property values — RCV
    prop_val_bldg_rcv_main: str = "0.00"
    prop_val_bldg_rcv_aprt: str = "0.00"
    prop_val_cont_rcv_main: str = "0.00"
    prop_val_cont_rcv_aprt: str = "0.00"

    # Property values — ACV
    bldg_acv_main: str = "0.00"
    bldg_acv_aprt: str = "0.00"
    cont_acv_main: str = "0.00"
    cont_acv_aprt: str = "0.00"

    # Gross loss — RCV
    gross_loss_bldg_rcv_main: str = "0.00"
    gross_loss_bldg_rcv_aprt: str = "0.00"
    gross_loss_cont_rcv_main: str = "0.00"
    gross_loss_cont_rcv_aprt: str = "0.00"

    # Covered damage — ACV
    covered_damage_bldg_acv_main: str = "0.00"
    covered_damage_bldg_acv_aprt: str = "0.00"
    covered_damage_cont_acv_main: str = "0.00"
    covered_damage_cont_acv_aprt: str = "0.00"

    # Removal/protection
    removal_protection_bldg_main: str = "0.00"
    removal_protection_bldg_aprt: str = "0.00"
    removal_protection_cont_main: str = "0.00"
    removal_protection_cont_aprt: str = "0.00"

    # Total loss
    total_loss_bldg_main: str = "0.00"
    total_loss_bldg_aprt: str = "0.00"
    total_loss_cont_main: str = "0.00"
    total_loss_cont_aprt: str = "0.00"

    # Less salvage
    less_salvage_bldg_main: str = "0.00"
    less_salvage_bldg_aprt: str = "0.00"
    less_salvage_cont_main: str = "0.00"
    less_salvage_cont_aprt: str = "0.00"

    # Less deductible
    less_deductible_bldg_main: str = "0.00"
    less_deductible_bldg_aprt: str = "0.00"
    less_deductible_cont_main: str = "0.00"
    less_deductible_cont_aprt: str = "0.00"

    # Excess over limit
    excess_over_limit_bldg_main: str = "0.00"
    excess_over_limit_bldg_aprt: str = "0.00"
    excess_over_limit_cont_main: str = "0.00"
    excess_over_limit_cont_aprt: str = "0.00"

    # Claim payable — ACV
    claim_payable_acv_bldg_main: str = "0.00"
    claim_payable_acv_bldg_aprt: str = "0.00"
    claim_payable_acv_cont_main: str = "0.00"
    claim_payable_acv_cont_aprt: str = "0.00"

    # RC coverage
    main_bldg_rcv: str = "0.00"
    ins_qualifies_for_rc_covg: str = "NO"
    rc_claim: str = "0.00"
    total_bldg_claim: str = "0.00"

    # Excluded damages
    excluded_damages: ExcludedDamages = field(default_factory=ExcludedDamages)

    # Depreciation
    depreciation_bldg_main: str = "0.00"
    depreciation_bldg_aprt: str = "0.00"
    depreciation_cont_main: str = "0.00"
    depreciation_cont_aprt: str = "0.00"

    # CWOP reasons
    bldg_cwop_reason: str = "None"
    cont_cwop_reason: str = "None"

    # Coinsurance
    bldg_coinsurance: str = "0.00"
    bldg_coinsurance_penalty: str = "0.00"
    bldg_coinsurance_factor: str = "0.00"
    has_coinsurance_penalty: str = "NO"
