import { NextRequest, NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

// POST /api/diary/save — save extracted diary data to the claim's Supabase record
export async function POST(request: NextRequest) {
  const { fg_number, diary_data } = await request.json();

  if (!fg_number || !diary_data) {
    return NextResponse.json(
      { error: "fg_number and diary_data are required" },
      { status: 400 }
    );
  }

  // Find the claim by FG number
  const { data: existing, error: findError } = await supabase
    .from("claims")
    .select("id, xml_data")
    .eq("fg_number", fg_number)
    .limit(1);

  if (findError) {
    return NextResponse.json(
      { error: `Lookup failed: ${findError.message}` },
      { status: 500 }
    );
  }

  if (!existing || existing.length === 0) {
    return NextResponse.json(
      { error: `No claim found for ${fg_number}` },
      { status: 404 }
    );
  }

  const claim = existing[0];
  const updatedXmlData = {
    ...(claim.xml_data || {}),
    // Merge diary-specific fields into xml_data
    diary_contact_date: diary_data.date_insured_contacted,
    diary_inspection_date: diary_data.date_loss_inspected,
    diary_referral_date: diary_data.referral_date,
    diary_loss_amount: diary_data.loss_amount,
    diary_insured_tel: diary_data.insured_tel,
    diary_mailing_address: diary_data.mailing_address,
    diary_property_address: diary_data.property_address,
    diary_activities: diary_data.activities,
    diary_total_hours: diary_data.total_hours,
    diary_total_expenses: diary_data.total_expenses,
    diary_total_travel: diary_data.total_travel,
    diary_extracted_at: new Date().toISOString(),
  };

  const { error: updateError } = await supabase
    .from("claims")
    .update({ xml_data: updatedXmlData })
    .eq("id", claim.id);

  if (updateError) {
    return NextResponse.json(
      { error: `Save failed: ${updateError.message}` },
      { status: 500 }
    );
  }

  return NextResponse.json({
    saved: true,
    fg_number,
    claim_id: claim.id,
  });
}
