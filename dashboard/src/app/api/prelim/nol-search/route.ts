import { NextRequest, NextResponse } from "next/server";

const DROPBOX_APP_KEY = process.env.DROPBOX_APP_KEY || "";
const DROPBOX_APP_SECRET = process.env.DROPBOX_APP_SECRET || "";
const DROPBOX_REFRESH_TOKEN = process.env.DROPBOX_REFRESH_TOKEN || "";

let cachedToken = "";
let tokenExpiry = 0;

async function getAccessToken(): Promise<string> {
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
  const data = await resp.json();
  cachedToken = data.access_token;
  tokenExpiry = Date.now() + (data.expires_in || 14400) * 1000;
  return cachedToken;
}

// POST /api/prelim/nol-search — search Dropbox for NOL, download + parse with Haiku
export async function POST(request: NextRequest) {
  const { query } = await request.json();

  if (!query || typeof query !== "string" || query.trim().length < 2) {
    return NextResponse.json({ error: "Enter an FG number or insured name" }, { status: 400 });
  }

  if (!DROPBOX_APP_KEY || !DROPBOX_REFRESH_TOKEN) {
    return NextResponse.json({ error: "Dropbox not configured" }, { status: 500 });
  }

  try {
    const token = await getAccessToken();

    // Search for NOL files
    const searchResp = await fetch("https://api.dropboxapi.com/2/files/search_v2", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: query.trim(),
        options: {
          path: "/RT Claims/2025 OPEN CLAIMS JULIO",
          max_results: 10,
          file_status: "active",
          filename_only: false,
        },
      }),
    });

    const searchData = await searchResp.json();
    const matches = (searchData.matches || [])
      .map((m: any) => m.metadata?.metadata)
      .filter((m: any) => {
        if (!m || m[".tag"] !== "file") return false;
        const name = (m.name || "").toLowerCase();
        return name.includes("nol") && (name.endsWith(".pdf") || name.endsWith(".xml"));
      });

    if (matches.length === 0) {
      return NextResponse.json({ found: false, message: `No NOL found for '${query.trim()}'` });
    }

    const nolFile = matches[0];
    const nolPath = nolFile.path_display;
    const nolName = nolFile.name;

    // Download the NOL
    const downloadResp = await fetch("https://content.dropboxapi.com/2/files/download", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Dropbox-API-Arg": JSON.stringify({ path: nolPath }),
      },
    });

    const fileBuffer = await downloadResp.arrayBuffer();
    const fileBytes = Buffer.from(fileBuffer);

    // Extract text from PDF using simple text extraction
    // For XML files, parse directly
    let extractedFields: Record<string, string> = {};

    if (nolName.toLowerCase().endsWith(".xml")) {
      extractedFields = parseXmlNol(fileBytes.toString("utf-8"));
    } else {
      // Use Haiku to extract from PDF text
      // First get raw text via a simple approach
      const Anthropic = (await import("@anthropic-ai/sdk")).default;
      const anthropic = new Anthropic();

      // Send the PDF as base64 to Haiku for extraction
      const base64 = fileBytes.toString("base64");

      const response = await anthropic.messages.create({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 1024,
        messages: [
          {
            role: "user",
            content: [
              {
                type: "document",
                source: { type: "base64", media_type: "application/pdf", data: base64 },
              },
              {
                type: "text",
                text: `Extract NFIP Notice of Loss data from this PDF. Return ONLY valid JSON with these fields (omit any you can't find):

- insured_name (full name, UPPERCASE)
- policy_number
- date_of_loss (YYYY-MM-DD)
- carrier (insurance company name)
- coverage_building (dollar amount, numbers only)
- coverage_contents (dollar amount, numbers only)
- claim_number
- property_address
- fg_number (FG file number if present)

Return ONLY JSON, no markdown.`,
              },
            ],
          },
        ],
      });

      const text = response.content[0].type === "text" ? response.content[0].text : "";
      const cleaned = text.replace(/```json\s*\n?/g, "").replace(/```\s*$/g, "").trim();
      try {
        extractedFields = JSON.parse(cleaned);
      } catch {
        return NextResponse.json({
          found: true,
          nol_name: nolName,
          fields: {},
          message: "Found NOL but couldn't parse it. Enter fields manually.",
        });
      }
    }

    // Map to PrelimFormData field names
    const mapped: Record<string, string> = {};
    if (extractedFields.insured_name) mapped.insured_name = extractedFields.insured_name;
    if (extractedFields.policy_number) mapped.policy_number = extractedFields.policy_number;
    if (extractedFields.date_of_loss) mapped.date_of_loss = extractedFields.date_of_loss;
    if (extractedFields.carrier) mapped.carrier = extractedFields.carrier;
    if (extractedFields.coverage_building) mapped.coverage_building = extractedFields.coverage_building;
    if (extractedFields.coverage_contents) mapped.coverage_contents = extractedFields.coverage_contents;
    if (extractedFields.fg_number) mapped.fg_number = extractedFields.fg_number;

    // Figure out what's missing
    const expected = ["insured_name", "policy_number", "date_of_loss", "carrier", "coverage_building"];
    const missing = expected.filter((f) => !mapped[f]);

    const confidence = Math.round(((expected.length - missing.length) / expected.length) * 100);

    return NextResponse.json({
      found: true,
      nol_name: nolName,
      fields: mapped,
      confidence,
      missing: missing.length > 0 ? missing : undefined,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("NOL search failed:", message);
    return NextResponse.json({ error: `Search failed: ${message}` }, { status: 500 });
  }
}

function parseXmlNol(xml: string): Record<string, string> {
  const get = (tag: string): string => {
    const m = xml.match(new RegExp(`<${tag}>([^<]*)</${tag}>`));
    return m ? m[1].trim() : "";
  };

  return {
    insured_name: `${get("InsuredLastName")}, ${get("InsuredFirstName")}`.replace(/^, |, $/g, ""),
    policy_number: get("PolicyNumber"),
    date_of_loss: get("DateOfLoss"),
    carrier: get("CarrierName") || get("WritingCompanyName"),
    coverage_building: get("BuildingAmount") || get("CoverageABuilding"),
    coverage_contents: get("ContentsAmount") || get("CoverageCContents"),
    claim_number: get("ClaimNumber"),
    fg_number: get("LossFileNumber"),
  };
}
