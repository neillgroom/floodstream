import { NextRequest, NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

// POST /api/prelim — generate prelim XML from form data and push to queue
export async function POST(request: NextRequest) {
  const form = await request.json();

  // Build the prelim XML server-side
  const xml = buildPrelimXml(form);

  // Push to Supabase
  const { data, error } = await supabase
    .from("claims")
    .insert({
      fg_number: form.fg_number || "UNKNOWN",
      insured_name: form.insured_name || "",
      policy_number: form.policy_number || "",
      date_of_loss: form.date_of_loss || "",
      carrier: form.carrier || "",
      report_type: "prelim",
      confidence: 1.0, // Human-entered
      xml_data: form, // Store all form fields
      xml_output: xml,
      warnings: [],
      source: "dashboard",
    })
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ id: data.id, xml }, { status: 201 });
}

// --- Prelim XML builder (TypeScript port of Python version) ---

function buildPrelimXml(form: Record<string, string>): string {
  const causeMap: Record<string, string> = {
    rainfall: "ACCUMULATION_OF_RAINFALL_OR_SNOWMELT",
    river: "OVERFLOW_OF_INLAND_OR_TIDAL_WATERS",
    surge: "UNUSUAL_AND_RAPID_ACCUMULATION_OR_RUNOFF",
    mudflow: "MUDFLOW",
    erosion: "COLLAPSE_OR_SUBSIDENCE_OF_LAND",
  };

  const dol = formatDateYYYYMMDD(form.date_of_loss);
  const contactDate = formatDateYYYYMMDD(form.contact_date);
  const inspectionDate = formatDateYYYYMMDD(form.inspection_date);
  const reportDate = new Date().toISOString().slice(0, 10).replace(/-/g, "");

  const enteredDate = formatDateTimeForXml(form.water_entered_date);
  const recededDate = formatDateTimeForXml(form.water_receded_date);
  const duration = calculateDuration(form.water_entered_date, form.water_receded_date);

  const cause = causeMap[form.cause] || form.cause || "";
  const foundationType = form.foundation_type || "";

  return `<?xml version="1.0" encoding="utf-8"?>
<AdjusterData>
  <report type="Prelim">
    <insuredName>${esc(form.insured_name?.toUpperCase())}</insuredName>
    <insuredFirstName></insuredFirstName>
    <policyNumber>${esc(form.policy_number)}</policyNumber>
    <dateOfLoss>${dol}</dateOfLoss>
    <catNo>N/a</catNo>
    <adjusterFileNumber>${esc(form.fg_number)}</adjusterFileNumber>
    <adjusterFCN>0005070169</adjusterFCN>
    <waterHeightExternal>${fmtNum(form.water_height_external)}</waterHeightExternal>
    <waterHeightInternal>${fmtNum(form.water_height_internal)}</waterHeightInternal>
    <reservesBuilding>${fmtDollar(form.reserves_building)}</reservesBuilding>
    <reservesContent>${fmtDollar(form.reserves_content)}</reservesContent>
    <advancePaymentBuilding>${fmtDollar(form.advance_building)}</advancePaymentBuilding>
    <advancePaymentContents>${fmtDollar(form.advance_contents)}</advancePaymentContents>
    <adjusterInitialContactDate>${contactDate}</adjusterInitialContactDate>
    <adjusterInitialInspectionDate>${inspectionDate}</adjusterInitialInspectionDate>
    <coverageBuilding>${fmtDollar(form.coverage_building)}</coverageBuilding>
    <coverageContents>${fmtDollar(form.coverage_contents)}</coverageContents>
    <buildingType>${esc(form.building_type?.toUpperCase())}</buildingType>
    <occupancy>${esc(form.occupancy?.toUpperCase())}</occupancy>
    <residencyType></residencyType>
    <numberOfFloors>${esc(form.number_of_floors)}</numberOfFloors>
    <buildingElevated>${esc(form.building_elevated)}</buildingElevated>
    <bldgSplitLevel>${esc(form.split_level)}</bldgSplitLevel>
    <underConstruction>NO</underConstruction>
    <foundationType>
      <piles>
        <type>${foundationType.toLowerCase() === "piles" ? "PILES" : ""}</type>
      </piles>
      <piers>
        <type>${foundationType.toLowerCase() === "piers" ? "PIERS" : ""}</type>
      </piers>
      <walls>
        <type>${!["piles", "piers"].includes(foundationType.toLowerCase()) ? esc(foundationType.toUpperCase()) : ""}</type>
        <other />
      </walls>
    </foundationType>
    <contentsType>
      <type>HOUSEHOLD</type>
    </contentsType>
    <cause>${cause}</cause>
    <condition_trait></condition_trait>
    <controlFailure>NO</controlFailure>
    <unnaturalCause>NO</unnaturalCause>
    <enteredDate>${enteredDate}</enteredDate>
    <recededDate>${recededDate}</recededDate>
    <timeWaterRemainedInBuilding2>${duration}</timeWaterRemainedInBuilding2>
    <reportDate>${reportDate}</reportDate>
    <adjusterName>Julio Lopez</adjusterName>
  </report>
</AdjusterData>`;
}

function esc(val: string | undefined): string {
  if (!val) return "";
  return val.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtNum(val: string | undefined): string {
  if (!val) return "0.00";
  const n = parseFloat(val.replace(/,/g, ""));
  return isNaN(n) ? "0.00" : n.toFixed(2);
}

function fmtDollar(val: string | undefined): string {
  if (!val) return "0.00";
  const n = parseFloat(val.replace(/[$,]/g, ""));
  return isNaN(n) ? "0.00" : n.toFixed(2);
}

function formatDateYYYYMMDD(val: string | undefined): string {
  if (!val) return "";
  // Handle HTML date input (YYYY-MM-DD)
  const m = val.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[1]}${m[2]}${m[3]}`;
  // Handle MM/DD/YYYY
  const m2 = val.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (m2) return `${m2[3]}${m2[1].padStart(2, "0")}${m2[2].padStart(2, "0")}`;
  return val;
}

function formatDateTimeForXml(val: string | undefined): string {
  if (!val) return "";
  // HTML datetime-local gives: "2025-07-31T12:00"
  const m = val.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (m) {
    const hour = parseInt(m[4]);
    const ampm = hour >= 12 ? "PM" : "AM";
    const h12 = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
    return `${m[2]}/${m[3]}/${m[1]} ${h12.toString().padStart(2, "0")}:${m[5]} ${ampm}`;
  }
  return val;
}

function calculateDuration(entered: string | undefined, receded: string | undefined): string {
  if (!entered || !receded) return "0 Days 0 Hours 0 Minutes";
  try {
    const d1 = new Date(entered);
    const d2 = new Date(receded);
    let diff = Math.max(0, d2.getTime() - d1.getTime());
    const days = Math.floor(diff / 86400000);
    diff %= 86400000;
    const hours = Math.floor(diff / 3600000);
    diff %= 3600000;
    const minutes = Math.floor(diff / 60000);
    return `${days} Days ${hours} Hours ${minutes} Minutes`;
  } catch {
    return "0 Days 0 Hours 0 Minutes";
  }
}
