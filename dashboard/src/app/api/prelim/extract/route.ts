import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic();

// POST /api/prelim/extract — Haiku reads messy field notes and extracts structured prelim data
export async function POST(request: NextRequest) {
  const { notes } = await request.json();

  if (!notes || typeof notes !== "string" || notes.trim().length < 10) {
    return NextResponse.json(
      { error: "Notes must be at least 10 characters" },
      { status: 400 }
    );
  }

  try {
    const response = await anthropic.messages.create({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: `Extract NFIP flood claim preliminary report data from these field notes. Return a JSON object with ONLY the fields you can confidently extract. Omit fields you can't determine — do NOT guess.

FIELD DEFINITIONS (return these exact keys):
- fg_number: FG file number (e.g. "FG151849")
- insured_name: Insured's full name, UPPERCASE
- policy_number: NFIP policy number
- date_of_loss: Date of loss (YYYY-MM-DD format)
- coverage_building: Building coverage dollar amount (number only, no $)
- coverage_contents: Contents coverage dollar amount (number only, no $)
- carrier: Insurance carrier name (e.g. "Wright Flood", "ASI", "Selective")
- contact_date: Date insured was first contacted (YYYY-MM-DD)
- inspection_date: Date of property inspection (YYYY-MM-DD)
- water_height_external: Exterior water height in inches (positive number)
- water_height_internal: Interior water height in inches (negative = below grade/basement)
- water_entered_date: When water entered building (YYYY-MM-DDTHH:MM format for datetime-local input)
- water_receded_date: When water receded (YYYY-MM-DDTHH:MM format)
- building_type: One of: MAIN DWELLING, CONDO UNIT, COMMERCIAL BUILDING, RCBAP, OTHER RESIDENTIAL, MANUFACTURED/MOBILE HOME
- occupancy: One of: OWNER-OCCUPIED (PRINCIPAL RESIDENCE), OWNER-OCCUPIED (SEASONAL RESIDENCE), TENANT-OCCUPIED, RENTAL (NOT OWNER OCCUPIED), VACANT
- number_of_floors: Number of floors (e.g. "2")
- building_elevated: "YES" or "NO"
- split_level: "YES" or "NO"
- foundation_type: One of: Slab, Crawlspace, Basement, Piles, Piers, Walls, Elevated
- cause: One of: rainfall, river, surge, mudflow, erosion
- reserves_building: Building reserves dollar amount (number only)
- reserves_content: Contents reserves dollar amount (number only)
- advance_building: Advance payment building (number only, "0" if none/declined)
- advance_contents: Advance payment contents (number only, "0" if none/declined)

FIELD NOTES:
${notes}

Return ONLY valid JSON, no markdown, no explanation.`,
        },
      ],
    });

    const text =
      response.content[0].type === "text" ? response.content[0].text : "";

    // Parse the JSON response, stripping any markdown fences Haiku might add
    const cleaned = text.replace(/```json\s*\n?/g, "").replace(/```\s*$/g, "").trim();
    const extracted = JSON.parse(cleaned);

    return NextResponse.json({ extracted }, { status: 200 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("Extraction failed:", message);
    return NextResponse.json({ error: `Extraction failed: ${message}` }, { status: 500 });
  }
}
