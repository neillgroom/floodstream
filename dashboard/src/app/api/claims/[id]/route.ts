import { NextRequest, NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

// GET /api/claims/[id] — get a single claim
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const { data, error } = await supabase
    .from("claims")
    .select("*")
    .eq("id", id)
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 404 });
  }

  return NextResponse.json(data);
}

// PATCH /api/claims/[id] — update status (approve/reject)
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();

  const update: Record<string, unknown> = {};

  if (body.status) {
    update.status = body.status;
  }
  if (body.reviewed_by) {
    update.reviewed_by = body.reviewed_by;
    update.reviewed_at = new Date().toISOString();
  }
  if (body.xml_data) {
    update.xml_data = body.xml_data;
  }
  if (body.xml_output) {
    update.xml_output = body.xml_output;
  }

  const { data, error } = await supabase
    .from("claims")
    .update(update)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}
