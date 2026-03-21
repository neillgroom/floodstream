import { NextRequest, NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

// GET /api/claims — list all claims, pending first
export async function GET() {
  const { data, error } = await supabase
    .from("claims")
    .select("*")
    .order("status", { ascending: true })  // pending_review sorts first alphabetically
    .order("created_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}

// POST /api/claims — create a new claim (from pipeline or prelim form)
export async function POST(request: NextRequest) {
  const body = await request.json();

  const { data, error } = await supabase
    .from("claims")
    .insert({
      fg_number: body.fg_number,
      insured_name: body.insured_name,
      policy_number: body.policy_number,
      date_of_loss: body.date_of_loss,
      carrier: body.carrier || "",
      report_type: body.report_type,
      confidence: body.confidence || 0,
      xml_data: body.xml_data || {},
      xml_output: body.xml_output || "",
      warnings: body.warnings || [],
      source: body.source || "dashboard",
    })
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}
