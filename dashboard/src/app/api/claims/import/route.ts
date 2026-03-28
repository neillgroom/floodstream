import { NextRequest, NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

const DROPBOX_APP_KEY = process.env.DROPBOX_APP_KEY || "";
const DROPBOX_APP_SECRET = process.env.DROPBOX_APP_SECRET || "";
const DROPBOX_REFRESH_TOKEN = process.env.DROPBOX_REFRESH_TOKEN || "";

let cachedToken = "";
let tokenExpiry = 0;

async function getDropboxToken(): Promise<string> {
  if (cachedToken && Date.now() < tokenExpiry - 60000) return cachedToken;
  const resp = await fetch("https://api.dropboxapi.com/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: DROPBOX_REFRESH_TOKEN,
      client_id: DROPBOX_APP_KEY,
      client_secret: DROPBOX_APP_SECRET,
    }),
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`Dropbox ${resp.status}: ${errText.slice(0, 200)}`);
  }
  const data = await resp.json();
  if (!data.access_token) {
    throw new Error(`No access_token: ${JSON.stringify(data).slice(0, 200)}`);
  }
  cachedToken = data.access_token;
  tokenExpiry = Date.now() + (data.expires_in || 14400) * 1000;
  return cachedToken;
}

async function createDropboxFolder(path: string, token: string): Promise<string> {
  const resp = await fetch("https://api.dropboxapi.com/2/files/create_folder_v2", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ path, autorename: false }),
  });
  if (!resp.ok) {
    const err = await resp.text();
    // "conflict/folder" means it already exists — that's fine
    if (err.includes("conflict")) return "exists";
    return `error: ${err.slice(0, 100)}`;
  }
  return "ok";
}

interface ParsedClaim {
  policy_number: string;
  fg_number: string;
  date_of_loss: string;
  claim_number: string;
  adjuster: string;
  insured_name: string;
  property_address: string;
}

function parseClaimsList(text: string): ParsedClaim[] {
  const claims: ParsedClaim[] = [];
  const lines = text.trim().split("\n");

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("//") || trimmed.startsWith("#")) continue;

    // The Venue claims list is tab-separated with these columns:
    // PolicyNumber  FG#  DOL  ClaimNumber  Adjuster  InsuredName  Address  Diary  Time  Docs  Open
    const parts = trimmed.split("\t").map((p) => p.trim());

    if (parts.length < 7) continue;

    // Find the FG number column — starts with "FG"
    let fgIdx = parts.findIndex((p) => /^FG\d+/.test(p));
    if (fgIdx < 0) continue;

    const policy_number = parts[fgIdx - 1] || "";
    const fg_number = parts[fgIdx];
    const date_of_loss = parts[fgIdx + 1] || "";
    const claim_number = parts[fgIdx + 2] || "";
    const adjuster = parts[fgIdx + 3] || "";
    const insured_name = parts[fgIdx + 4] || "";

    // Address is everything after insured name until we hit Diary/Time/Docs/Open
    const remaining = parts.slice(fgIdx + 5);
    const addressParts: string[] = [];
    for (const p of remaining) {
      if (["Diary", "Time", "Docs", "Open", "Edit"].includes(p)) break;
      addressParts.push(p);
    }
    const property_address = addressParts.join(" ").trim();

    if (fg_number && insured_name) {
      claims.push({
        policy_number,
        fg_number,
        date_of_loss,
        claim_number,
        adjuster,
        insured_name,
        property_address,
      });
    }
  }

  return claims;
}

// POST /api/claims/import — parse Venue claims list, create Supabase records + Dropbox folders
export async function POST(request: NextRequest) {
  const { text, create_folders } = await request.json();

  if (!text || typeof text !== "string") {
    return NextResponse.json({ error: "Paste the claims list" }, { status: 400 });
  }

  const claims = parseClaimsList(text);
  if (claims.length === 0) {
    return NextResponse.json({ error: "No claims found in paste. Check the format." }, { status: 400 });
  }

  const results: { fg: string; name: string; status: string }[] = [];
  let dropboxToken = "";
  let folderError = "";

  // Always create folders — the checkbox is a nicety, not a gate
  {
    if (!DROPBOX_APP_KEY || !DROPBOX_REFRESH_TOKEN) {
      folderError = `Dropbox not configured (key=${!!DROPBOX_APP_KEY}, token=${!!DROPBOX_REFRESH_TOKEN})`;
    } else {
      try {
        dropboxToken = await getDropboxToken();
      } catch (e) {
        folderError = `Dropbox auth failed: ${e instanceof Error ? e.message : e}`;
      }
    }
  }

  for (const claim of claims) {
    // Check if already exists in Supabase
    const { data: existing } = await supabase
      .from("claims")
      .select("id")
      .eq("fg_number", claim.fg_number)
      .limit(1);

    if (existing && existing.length > 0) {
      results.push({ fg: claim.fg_number, name: claim.insured_name, status: "exists" });
      continue;
    }

    // Format DOL for storage
    let dol = claim.date_of_loss;
    // Convert M/D/YYYY to YYYY-MM-DD if needed
    const dolMatch = dol.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (dolMatch) {
      dol = `${dolMatch[3]}-${dolMatch[1].padStart(2, "0")}-${dolMatch[2].padStart(2, "0")}`;
    }

    const folderName = claim.insured_name;

    // Insert into Supabase
    const { error } = await supabase.from("claims").insert({
      fg_number: claim.fg_number,
      insured_name: claim.insured_name,
      policy_number: claim.policy_number,
      date_of_loss: dol,
      carrier: "",
      report_type: "prelim",
      status: "pending_review",
      confidence: 0,
      xml_data: {
        claim_number: claim.claim_number,
        adjuster: claim.adjuster,
        property_address: claim.property_address,
      },
      xml_output: "",
      warnings: [],
      source: "dashboard",
    });

    if (error) {
      results.push({ fg: claim.fg_number, name: claim.insured_name, status: `error: ${error.message}` });
      continue;
    }

    // Create Dropbox folders
    if (dropboxToken) {
      const folderBase = `/RT Claims/2025 OPEN CLAIMS JULIO/1 setup claim/${claim.fg_number} ${folderName}`;
      await createDropboxFolder(folderBase, dropboxToken);
      await createDropboxFolder(`${folderBase}/Attach`, dropboxToken);
      await createDropboxFolder(`${folderBase}/Prelim Photos`, dropboxToken);
      await createDropboxFolder(`${folderBase}/Photos`, dropboxToken);
      results.push({ fg: claim.fg_number, name: claim.insured_name, status: "created + folders" });
    } else {
      results.push({ fg: claim.fg_number, name: claim.insured_name, status: "created" });
    }
  }

  const created = results.filter((r) => r.status.startsWith("created")).length;
  const skipped = results.filter((r) => r.status === "exists").length;
  const errors = results.filter((r) => r.status.startsWith("error")).length;

  return NextResponse.json({
    total: claims.length,
    created,
    skipped,
    errors,
    results,
    folderError: folderError || undefined,
  });
}
