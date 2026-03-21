import { NextRequest, NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

// Allow large PDF uploads (up to 100MB) and extend timeout
export const maxDuration = 60; // 60 second timeout for extraction

// Anthropic API key for Haiku extraction
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY || "";

const EXTRACTION_PROMPT = `You are an NFIP flood insurance claim data extractor. Extract ALL of the following fields from this Final Report PDF text.

Return a JSON object with these fields (use empty string "" if not found):
- insured_name: Full name of the insured
- policy_number: Policy number (10+ digits)
- claim_number: Claim number
- adjuster_file_number: FG file number (e.g. FG151429)
- date_of_loss: Date of loss (MM/DD/YYYY)
- risk_construction_date: When built (MM/DD/YYYY or year)
- ins_at_premises: Insured since (MM/DD/YYYY or year)
- bldg_policy_limit: Building coverage limit
- cont_policy_limit: Contents coverage limit
- bldg_deductible: Building deductible
- cont_deductible: Contents deductible
- qualifies_for_rc: "YES" or "NO"
- bldg_rcv_loss: Building RCV loss (number only)
- bldg_depreciation: Building depreciation (number only)
- bldg_acv_loss: Building ACV loss
- bldg_claim_payable: Building claim payable
- bldg_rc_claim: Building RC claim
- cont_rcv_loss: Contents RCV loss
- cont_non_recoverable_depreciation: Contents non-recoverable depreciation
- cont_acv_loss: Contents ACV loss
- cont_claim_payable: Contents claim payable
- prop_val_bldg_rcv: Pre-loss building RCV (from Proof of Loss)
- prop_val_bldg_acv: Pre-loss building ACV
- prop_val_cont_rcv: Pre-loss contents RCV
- prop_val_cont_acv: Pre-loss contents ACV

For dollar amounts, return just the number (no $ or commas), e.g. "48602.93".

--- PDF TEXT ---
`;

export async function POST(request: NextRequest) {
  try {
    // Text is extracted client-side (pdf.js) and sent as JSON
    const body = await request.json();
    const text = body.text as string;
    const fgNumber = (body.fg_number as string) || "";

    if (!text || text.length < 100) {
      return NextResponse.json(
        { error: "No text extracted from PDF. It may be a scanned document or photo sheet." },
        { status: 400 }
      );
    }

    // Send to Claude Haiku for extraction
    if (!ANTHROPIC_API_KEY) {
      return NextResponse.json(
        { error: "ANTHROPIC_API_KEY not configured on server" },
        { status: 500 }
      );
    }

    const extractionResponse = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 2000,
        messages: [
          {
            role: "user",
            content: EXTRACTION_PROMPT + text.slice(0, 15000),
          },
        ],
      }),
    });

    if (!extractionResponse.ok) {
      const errText = await extractionResponse.text();
      return NextResponse.json(
        { error: `Claude API error: ${extractionResponse.status} ${errText.slice(0, 200)}` },
        { status: 500 }
      );
    }

    const aiResult = await extractionResponse.json();
    const aiText = aiResult.content?.[0]?.text || "";

    // Parse JSON from response
    let extracted: Record<string, string> = {};
    try {
      const jsonMatch = aiText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        extracted = JSON.parse(jsonMatch[0]);
      }
    } catch {
      return NextResponse.json(
        { error: "Failed to parse extraction results" },
        { status: 500 }
      );
    }

    // Build the Final XML
    const xml = buildFinalXml(extracted);

    // Push to Supabase
    const { data, error } = await supabase
      .from("claims")
      .insert({
        fg_number: fgNumber || extracted.adjuster_file_number || "UNKNOWN",
        insured_name: extracted.insured_name || "UNKNOWN",
        policy_number: extracted.policy_number || "",
        date_of_loss: extracted.date_of_loss || "",
        carrier: "",
        report_type: "final",
        confidence: 0.95,
        xml_data: extracted,
        xml_output: xml,
        warnings: [],
        source: "dashboard",
      })
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({
      id: data.id,
      fg_number: data.fg_number,
      insured_name: data.insured_name,
    });

  } catch (err) {
    return NextResponse.json(
      { error: `Server error: ${err instanceof Error ? err.message : err}` },
      { status: 500 }
    );
  }
}

function buildFinalXml(d: Record<string, string>): string {
  const dol = formatDate(d.date_of_loss);
  return `<?xml version="1.0" encoding="utf-8"?>
<AdjusterData>
  <report type="FINAL">
    <insuredName>${esc(d.insured_name?.toUpperCase())}</insuredName>
    <insuredFirstName></insuredFirstName>
    <policyNumber>${esc(d.policy_number)}</policyNumber>
    <dateOfLoss>${dol}</dateOfLoss>
    <adjusterFileNumber>${esc(d.adjuster_file_number)}</adjusterFileNumber>
    <propValBldgRCVMain>0</propValBldgRCVMain>
    <riskConstuctionDate>${esc(d.risk_construction_date)}</riskConstuctionDate>
    <insAtPremises>${esc(d.ins_at_premises)}</insAtPremises>
    <Alterations>
      <Alteration1><Date/><Description/><MarketValue/><Cost/><Type/><substantialImprovement>NO</substantialImprovement></Alteration1>
      <Alteration2><Date/><Description/><MarketValue/><Cost/><Type/><substantialImprovement>NO</substantialImprovement></Alteration2>
      <Alteration3><Date/><Description/><MarketValue/><Cost/><substantialImprovement>NO</substantialImprovement></Alteration3>
    </Alterations>
    <Priors>
      <Prior1><Date/><Amount/><RepairsCompleted>NO</RepairsCompleted><Insured>NO</Insured><NoClaim>NO</NoClaim></Prior1>
      <Prior2><Date/><Amount/><RepairsCompleted>NO</RepairsCompleted><Insured>NO</Insured><NoClaim>NO</NoClaim></Prior2>
      <Prior3><Date/><Amount/><RepairsCompleted>NO</RepairsCompleted><Insured>NO</Insured><NoClaim>NO</NoClaim></Prior3>
    </Priors>
    <OtherInsurance><Company/><Type>HOMEOWNERS</Type><PolicyNumber/><BuildingCoverage>0.00</BuildingCoverage><ContentsCoverage>0.00</ContentsCoverage><FloodCoverage>NO</FloodCoverage><Duration>2TO4WEEKS</Duration></OtherInsurance>
    <propValBldgRCVMain>${fmtD(d.prop_val_bldg_rcv)}</propValBldgRCVMain>
    <propValBldgRCVAprt>0.00</propValBldgRCVAprt>
    <propValContRCVMain>${fmtD(d.prop_val_cont_rcv)}</propValContRCVMain>
    <propValContRCVAprt>0.00</propValContRCVAprt>
    <bldgACVMain>${fmtD(d.prop_val_bldg_acv)}</bldgACVMain>
    <bldgACVAprt>0.00</bldgACVAprt>
    <contACVMain>${fmtD(d.prop_val_cont_acv)}</contACVMain>
    <contACVAprt>0.00</contACVAprt>
    <grossLossBldgRCVMain>${fmtD(d.bldg_rcv_loss)}</grossLossBldgRCVMain>
    <grossLossBldgRCVAprt>0.00</grossLossBldgRCVAprt>
    <grossLossContRCVMain>${fmtD(d.cont_rcv_loss)}</grossLossContRCVMain>
    <grossLossContRCVAprt>0.00</grossLossContRCVAprt>
    <coveredDamageBldgACVMain>${fmtD(d.bldg_acv_loss)}</coveredDamageBldgACVMain>
    <coveredDamageBldgACVAprt>0.00</coveredDamageBldgACVAprt>
    <coveredDamageContACVMain>${fmtD(d.cont_acv_loss)}</coveredDamageContACVMain>
    <coveredDamageContACVAprt>0.00</coveredDamageContACVAprt>
    <removalProtectionBldgMain>0.00</removalProtectionBldgMain>
    <removalProtectionBldgAprt>0.00</removalProtectionBldgAprt>
    <removalProtectionContMain>0.00</removalProtectionContMain>
    <removalProtectionContAprt>0.00</removalProtectionContAprt>
    <totalLossBldgMain>${fmtD(d.bldg_acv_loss)}</totalLossBldgMain>
    <totalLossBldgAprt>0.00</totalLossBldgAprt>
    <totalLossContMain>${fmtD(d.cont_acv_loss)}</totalLossContMain>
    <totalLossContAprt>0.00</totalLossContAprt>
    <lessSalvageBldgMain>0.00</lessSalvageBldgMain>
    <lessSalvageBldgAprt>0.00</lessSalvageBldgAprt>
    <lessSalvageContMain>0.00</lessSalvageContMain>
    <lessSalvageContAprt>0.00</lessSalvageContAprt>
    <lessDeductibleBldgMain>${fmtD(d.bldg_deductible)}</lessDeductibleBldgMain>
    <lessDeductibleBldgAprt>0.00</lessDeductibleBldgAprt>
    <lessDeductibleContMain>${fmtD(d.cont_deductible)}</lessDeductibleContMain>
    <lessDeductibleContAprt>0.00</lessDeductibleContAprt>
    <excessOverLimitBldgMain>0.00</excessOverLimitBldgMain>
    <excessOverLimitBldgAprt>0.00</excessOverLimitBldgAprt>
    <excessOverLimitContMain>0.00</excessOverLimitContMain>
    <excessOverLimitContAprt>0.00</excessOverLimitContAprt>
    <claimPayableACVBldgMain>${fmtD(d.bldg_claim_payable)}</claimPayableACVBldgMain>
    <claimPayableACVBldgAprt>0.00</claimPayableACVBldgAprt>
    <claimPayableACVContMain>${fmtD(d.cont_claim_payable)}</claimPayableACVContMain>
    <claimPayableACVContAprt>0.00</claimPayableACVContAprt>
    <mainBldgRCV>${fmtD(d.prop_val_bldg_rcv)}</mainBldgRCV>
    <insQualifiesForRCCovg>${d.qualifies_for_rc || "NO"}</insQualifiesForRCCovg>
    <rCClaim>${fmtD(d.bldg_rc_claim)}</rCClaim>
    <totalBldgClaim>${fmtD(d.bldg_claim_payable)}</totalBldgClaim>
    <ExcludedDamages>
      <ExcludedBuildingValue><value>LESS_THAN_ONE_THOUSAND</value></ExcludedBuildingValue>
      <ExcludedBuildingDamage><value>LESS_THAN_ONE_THOUSAND</value></ExcludedBuildingDamage>
      <ExcludedContentsValue><value>LESS_THAN_ONE_THOUSAND</value></ExcludedContentsValue>
      <ExcludedContentsDamage><value>LESS_THAN_ONE_THOUSAND</value></ExcludedContentsDamage>
    </ExcludedDamages>
    <depreciationBldgMain>${fmtD(d.bldg_depreciation)}</depreciationBldgMain>
    <depreciationBldgAprt>0.00</depreciationBldgAprt>
    <depreciationContMain>${fmtD(d.cont_non_recoverable_depreciation)}</depreciationContMain>
    <depreciationContAprt>0.00</depreciationContAprt>
    <bldgCwopReason>None</bldgCwopReason>
    <contCwopReason>None</contCwopReason>
    <bldgCoinsurance>0.00</bldgCoinsurance>
    <bldgCoinsurancePenalty>0.00</bldgCoinsurancePenalty>
    <bldgCoinsuranceFactor>0.00</bldgCoinsuranceFactor>
    <hasCoinsurancePenalty>NO</hasCoinsurancePenalty>
  </report>
</AdjusterData>`;
}

function esc(val: string | undefined): string {
  if (!val) return "";
  return val.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtD(val: string | undefined): string {
  if (!val) return "0.00";
  const n = parseFloat(val.replace(/[$,]/g, ""));
  return isNaN(n) ? "0.00" : n.toFixed(2);
}

function formatDate(val: string | undefined): string {
  if (!val) return "";
  const m = val.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (m) return `${m[3]}${m[1].padStart(2, "0")}${m[2].padStart(2, "0")}`;
  return val.replace(/\D/g, "").slice(0, 8);
}
