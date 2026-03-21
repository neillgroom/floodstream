"""
Builds the <AdjusterData> XML from a populated AdjusterData dataclass.
Pure code — no AI, no guessing. Just maps fields to XML elements.
"""

from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from xml_schema import AdjusterData


def build_xml(data: AdjusterData) -> str:
    """Generate the <AdjusterData> XML string from a populated schema."""

    root = Element("AdjusterData")
    report = SubElement(root, "report", type=data.report_type)

    # --- Insured info ---
    _t(report, "insuredName", data.insured_name)
    _t(report, "insuredFirstName", data.insured_first_name)
    _t(report, "policyNumber", data.policy_number)
    _t(report, "dateOfLoss", data.date_of_loss)
    _t(report, "adjusterFileNumber", data.adjuster_file_number)

    # --- Risk info ---
    _t(report, "propValBldgRCVMain", "0")  # first occurrence is always 0
    _t(report, "riskConstuctionDate", data.risk_construction_date)
    _t(report, "insAtPremises", data.ins_at_premises)

    # --- Alterations ---
    alts = SubElement(report, "Alterations")
    for i, alt in enumerate(data.alterations[:3], 1):
        alt_el = SubElement(alts, f"Alteration{i}")
        _t(alt_el, "Date", alt.date)
        _t(alt_el, "Description", alt.description)
        _t(alt_el, "MarketValue", alt.market_value)
        _t(alt_el, "Cost", alt.cost)
        if i <= 2:  # Alteration3 has no Type in the schema
            _t(alt_el, "Type", alt.type)
        _t(alt_el, "substantialImprovement", alt.substantial_improvement)

    # --- Priors ---
    priors = SubElement(report, "Priors")
    for i, prior in enumerate(data.priors[:3], 1):
        prior_el = SubElement(priors, f"Prior{i}")
        _t(prior_el, "Date", prior.date)
        _t(prior_el, "Amount", prior.amount)
        _t(prior_el, "RepairsCompleted", prior.repairs_completed)
        _t(prior_el, "Insured", prior.insured)
        _t(prior_el, "NoClaim", prior.no_claim)

    # --- Other insurance ---
    oi = SubElement(report, "OtherInsurance")
    _t(oi, "Company", data.other_insurance.company)
    _t(oi, "Type", data.other_insurance.type)
    _t(oi, "PolicyNumber", data.other_insurance.policy_number)
    _t(oi, "BuildingCoverage", data.other_insurance.building_coverage)
    _t(oi, "ContentsCoverage", data.other_insurance.contents_coverage)
    _t(oi, "FloodCoverage", data.other_insurance.flood_coverage)
    _t(oi, "Duration", data.other_insurance.duration)

    # --- Financial summary (all from PDF — source of truth) ---
    _t(report, "propValBldgRCVMain", data.prop_val_bldg_rcv_main)
    _t(report, "propValBldgRCVAprt", data.prop_val_bldg_rcv_aprt)
    _t(report, "propValContRCVMain", data.prop_val_cont_rcv_main)
    _t(report, "propValContRCVAprt", data.prop_val_cont_rcv_aprt)

    _t(report, "bldgACVMain", data.bldg_acv_main)
    _t(report, "bldgACVAprt", data.bldg_acv_aprt)
    _t(report, "contACVMain", data.cont_acv_main)
    _t(report, "contACVAprt", data.cont_acv_aprt)

    _t(report, "grossLossBldgRCVMain", data.gross_loss_bldg_rcv_main)
    _t(report, "grossLossBldgRCVAprt", data.gross_loss_bldg_rcv_aprt)
    _t(report, "grossLossContRCVMain", data.gross_loss_cont_rcv_main)
    _t(report, "grossLossContRCVAprt", data.gross_loss_cont_rcv_aprt)

    _t(report, "coveredDamageBldgACVMain", data.covered_damage_bldg_acv_main)
    _t(report, "coveredDamageBldgACVAprt", data.covered_damage_bldg_acv_aprt)
    _t(report, "coveredDamageContACVMain", data.covered_damage_cont_acv_main)
    _t(report, "coveredDamageContACVAprt", data.covered_damage_cont_acv_aprt)

    _t(report, "removalProtectionBldgMain", data.removal_protection_bldg_main)
    _t(report, "removalProtectionBldgAprt", data.removal_protection_bldg_aprt)
    _t(report, "removalProtectionContMain", data.removal_protection_cont_main)
    _t(report, "removalProtectionContAprt", data.removal_protection_cont_aprt)

    _t(report, "totalLossBldgMain", data.total_loss_bldg_main)
    _t(report, "totalLossBldgAprt", data.total_loss_bldg_aprt)
    _t(report, "totalLossContMain", data.total_loss_cont_main)
    _t(report, "totalLossContAprt", data.total_loss_cont_aprt)

    _t(report, "lessSalvageBldgMain", data.less_salvage_bldg_main)
    _t(report, "lessSalvageBldgAprt", data.less_salvage_bldg_aprt)
    _t(report, "lessSalvageContMain", data.less_salvage_cont_main)
    _t(report, "lessSalvageContAprt", data.less_salvage_cont_aprt)

    _t(report, "lessDeductibleBldgMain", data.less_deductible_bldg_main)
    _t(report, "lessDeductibleBldgAprt", data.less_deductible_bldg_aprt)
    _t(report, "lessDeductibleContMain", data.less_deductible_cont_main)
    _t(report, "lessDeductibleContAprt", data.less_deductible_cont_aprt)

    _t(report, "excessOverLimitBldgMain", data.excess_over_limit_bldg_main)
    _t(report, "excessOverLimitBldgAprt", data.excess_over_limit_bldg_aprt)
    _t(report, "excessOverLimitContMain", data.excess_over_limit_cont_main)
    _t(report, "excessOverLimitContAprt", data.excess_over_limit_cont_aprt)

    _t(report, "claimPayableACVBldgMain", data.claim_payable_acv_bldg_main)
    _t(report, "claimPayableACVBldgAprt", data.claim_payable_acv_bldg_aprt)
    _t(report, "claimPayableACVContMain", data.claim_payable_acv_cont_main)
    _t(report, "claimPayableACVContAprt", data.claim_payable_acv_cont_aprt)

    # --- RC coverage ---
    _t(report, "mainBldgRCV", data.main_bldg_rcv)
    _t(report, "insQualifiesForRCCovg", data.ins_qualifies_for_rc_covg)
    _t(report, "rCClaim", data.rc_claim)
    _t(report, "totalBldgClaim", data.total_bldg_claim)

    # --- Excluded damages ---
    ed = SubElement(report, "ExcludedDamages")
    for tag, val in [
        ("ExcludedBuildingValue", data.excluded_damages.excluded_building_value),
        ("ExcludedBuildingDamage", data.excluded_damages.excluded_building_damage),
        ("ExcludedContentsValue", data.excluded_damages.excluded_contents_value),
        ("ExcludedContentsDamage", data.excluded_damages.excluded_contents_damage),
    ]:
        wrapper = SubElement(ed, tag)
        _t(wrapper, "value", val)

    # --- Depreciation ---
    _t(report, "depreciationBldgMain", data.depreciation_bldg_main)
    _t(report, "depreciationBldgAprt", data.depreciation_bldg_aprt)
    _t(report, "depreciationContMain", data.depreciation_cont_main)
    _t(report, "depreciationContAprt", data.depreciation_cont_aprt)

    # --- CWOP ---
    _t(report, "bldgCwopReason", data.bldg_cwop_reason)
    _t(report, "contCwopReason", data.cont_cwop_reason)

    # --- Coinsurance ---
    _t(report, "bldgCoinsurance", data.bldg_coinsurance)
    _t(report, "bldgCoinsurancePenalty", data.bldg_coinsurance_penalty)
    _t(report, "bldgCoinsuranceFactor", data.bldg_coinsurance_factor)
    _t(report, "hasCoinsurancePenalty", data.has_coinsurance_penalty)

    # Pretty print
    rough = tostring(root, encoding="unicode")
    return parseString(rough).toprettyxml(indent="  ", encoding=None)


def _t(parent: Element, tag: str, text: str):
    """Helper: add a text sub-element."""
    el = SubElement(parent, tag)
    el.text = str(text)
    return el
