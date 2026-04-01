import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic();

// POST /api/diary/extract — AI filters raw Venue diary into clean official actions
// mode: "prelim" (extract dates only) or "final" (full activity report for PDF)
export async function POST(request: NextRequest) {
  const { text, mode } = await request.json();

  if (!text || typeof text !== "string" || text.trim().length < 20) {
    return NextResponse.json(
      { error: "Diary text must be at least 20 characters" },
      { status: 400 }
    );
  }

  const isPrelim = mode === "prelim";

  try {
    // Use Sonnet for final (needs stronger judgment to filter garbage)
    // Use Haiku for prelim (just pulling dates, simpler task)
    const model = isPrelim
      ? "claude-haiku-4-5-20251001"
      : "claude-sonnet-4-5-20250514";

    const response = await anthropic.messages.create({
      model,
      max_tokens: 4096,
      messages: [
        {
          role: "user",
          content: isPrelim
            ? buildPrelimPrompt(text.trim())
            : buildFinalPrompt(text.trim()),
        },
      ],
    });

    const responseText =
      response.content[0].type === "text" ? response.content[0].text : "";

    const cleaned = responseText
      .replace(/```json\s*\n?/g, "")
      .replace(/```\s*$/g, "")
      .trim();
    const extracted = JSON.parse(cleaned);

    return NextResponse.json({ extracted, mode }, { status: 200 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("Diary extraction failed:", message);
    return NextResponse.json(
      { error: `Extraction failed: ${message}` },
      { status: 500 }
    );
  }
}

function buildPrelimPrompt(text: string): string {
  return `Extract key dates from this Venue Claims portal diary log. This is a raw activity log with tab-separated columns: File#, Rpt. Date, Entry Time, Next Rpt. Date, Type, OfficeStaff, Details, Document Name.

I need these dates for the preliminary report:
- fg_number: The FG file number (e.g. "FG151159")
- date_assigned: When the file was opened/adjuster assigned (look for "File Opened" or "Adjuster Assigned")
- date_contacted: When the insured was first contacted (look for "Contacted Insured" type entries)
- date_inspected: When the inspection was completed (look for "Inspection Completed" type entries)
- date_prelim_due: When the preliminary report is due (look for "Final Report Due" or early report due dates)

Return a JSON object with ONLY these fields. Use M/D/YYYY format for dates. If a date can't be determined, use empty string.

DIARY LOG:
${text}

Return ONLY valid JSON, no markdown, no explanation.`;
}

function buildFinalPrompt(text: string): string {
  return `You are processing a raw Venue Claims portal diary log for an NFIP flood claim. The log contains tab-separated entries with columns: File#, Rpt. Date, Entry Time, Next Rpt. Date, Type, OfficeStaff, Details, Document Name.

Your job is to FILTER this log down to ONLY the official, external-facing actions that belong in a formal Activity Report. This report documents what the adjuster officially did on the claim — it is NOT an internal work log.

KEEP these types of entries (rewrite into clean activity entries):
- "File Opened" → Activity type: "Log", Description: "Received Claim for processing"
- "Contacted Insured" → Activity type: "Contact", Description: "Contact made with Insured"
- "Inspection Completed" → Activity type: "Inspection/Scope", Description: "Risk/Loss inspection and scope"
- Prelim report uploaded/approved → Activity type: "Preliminary Report", Description: "Completion of Preliminary Report"
- Status reports uploaded to carrier → Activity type: "30 Day Status", Description: "30 Day diary report" (or appropriate status description)
- Follow-up contacts with insured (actual phone calls, not internal notes) → Activity type: "Follow-up", Description: "Follow-up call to Insured"
- Estimate/scope completed → Activity type: "Flood Estimate", Description: "Estimate/Scope for Flood Loss"
- Final report uploaded/approved → Activity type: "Review", Description: "Final Closing Review"

REMOVE / IGNORE these:
- Internal rejections ("Report Rejected by...")
- RAP review/approval cycles (these are internal QA)
- Staff-to-staff notes and discussions
- "Prelim report has been sent for Manager review" (internal)
- Emails pasted into the log
- Duplicate entries for the same action
- "Manually uploaded..." entries (internal process notes)
- Any entry that documents internal workflow, not an official claim action

For each kept entry, determine a realistic due date. Use the Rpt. Date from the log entry.

Return a JSON object:
{
  "fg_number": "FG######",
  "date_insured_contacted": "M/D/YYYY",
  "date_loss_inspected": "M/D/YYYY",
  "activities": [
    {
      "activity_type": "Log|Contact|Inspection/Scope|Preliminary Report|Follow-up|Flood Estimate|30 Day Status|Review",
      "due_date": "M/D/YYYY",
      "status": "Not Completed",
      "description": "Clean, professional description"
    }
  ],
  "total_hours": "0.00",
  "total_expenses": "0.00",
  "total_travel": "0.00"
}

IMPORTANT:
- All statuses should be "Not Completed" (this is how Venue formats them)
- Activities must be in chronological order
- Use professional, clean descriptions — no internal jargon
- The goal is 5-15 clean entries from what might be 30+ raw entries
- When in doubt, LEAVE IT OUT — it's better to have too few than to include internal noise

DIARY LOG:
${text}

Return ONLY valid JSON, no markdown, no explanation.`;
}
