"""
Activity Report (Diary) generator — pixel-identical to Venue Claims portal output.

All coordinates extracted from actual Venue diary PDF using PyMuPDF.
See extract_diary_layout.py for the extraction script.

Layout:
- Page: 612 x 792 (US Letter)
- Header: claim info (left + right columns)
- Separator lines, referral/contact/inspected row
- "Activity Report" title (centered, bold 14pt)
- Double separator line
- 5 activity entries per page, 114.4pt vertical spacing
- Each entry: Activity name, Due date, Status, Description, underline
- Last page: totals footer (hours, expenses, travel)
- Page footer: date + page number
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import fitz  # PyMuPDF

PAGE_W = 612
PAGE_H = 792

# --- Fonts ---
FONT_REGULAR = "helv"         # Helvetica
FONT_BOLD = "hebo"            # Helvetica-Bold
FONT_BOLD_ITALIC = "hebi"     # Helvetica-BoldOblique
FONT_TIMES_BOLD = "tibo"      # Times-Bold

# Baseline offset: PyMuPDF insert_text y = baseline, bbox y0 = baseline - ascent.
# Empirically measured: Helvetica 10pt ascent = 10.8, scale linearly for other sizes.
ASCENT_10 = 10.8               # Helvetica/Times at 10pt
ASCENT_14 = 15.12              # Helvetica-Bold at 14pt (10.8 * 14/10)

# --- Coordinates extracted from actual Venue diary PDF (bbox y0 values) ---

# Header - left column
HEADER_LABEL_X = 27.0
HEADER_VALUE_X = 138.0
HEADER_ROW_Y = [19.6, 33.8, 62.3, 76.8]  # Insured, Address, Mailing, Tel
# Note: there's a gap between Address (33.8) and Mailing (62.3) — intentional

# Header - right column
HEADER_RIGHT_LABEL_X = 383.0
HEADER_RIGHT_VALUE_X = 475.3
HEADER_RIGHT_ROW_Y = [19.6, 33.8, 48.0, 62.3, 76.8]  # Policy, DOL, Cat, Adj File, Loss Amt

# Separator lines
HEADER_LINE_Y = 104.6          # thin line below header
REFERRAL_ROW_Y = 108.2         # Referral Date / Contact / Inspected row
POST_REFERRAL_LINE_Y = 129.3   # thin line below referral row

# Title
TITLE_Y = 135.4                # "Activity Report" baseline
TITLE_X = 255.9                # approximate left edge (we'll center it)

# Double line below title
DOUBLE_LINE_Y1 = 165.3
DOUBLE_LINE_Y2 = 169.8

# Activity entries
FIRST_ACTIVITY_Y = 192.4       # y of first "Activity" text on page 1
ACTIVITY_SPACING = 114.4        # vertical spacing between entries
MAX_ENTRIES_PAGE1 = 5           # entries that fit on page 1 (below header)
MAX_ENTRIES_CONTINUATION = 5    # entries per continuation page (no header)

# Within each activity entry
ACTIVITY_LABEL_X = 27.0         # "Activity" label
ACTIVITY_NAME_X = 90.2          # activity type name
DUE_LABEL_X = 382.2            # "Due:" label
DUE_DATE_X = 406.8             # due date value
STATUS_X = 490.0               # "Not Completed" / "Completed"
DESCRIPTION_LABEL_X = 27.0     # "Description:" label
DESCRIPTION_TEXT_X = 90.2      # description text
DESC_OFFSET_Y = 27.0           # description is 27pt below activity line
UNDERLINE_X_START = 84.6       # description underline start
UNDERLINE_X_END = 592.9        # description underline end
UNDERLINE_OFFSET_Y = 42.7      # underline is 42.7pt below activity line

# Lines
LINE_LEFT_X = 18.0
LINE_RIGHT_X = 592.9
THIN_LINE_WIDTH = 0.36
THICK_LINE_WIDTH = 0.90

# Footer
FOOTER_DATE_X = 463.1
FOOTER_PAGE_X = 555.6
FOOTER_Y = 752.7

# Totals section (last page)
TOTALS_LINE_Y = 598.5
TOTALS_TITLE_X = 219.4
TOTALS_TITLE_Y = 581.8
TOTALS_ROW_Y = 604.9
TOTALS_HOURS_LABEL_X = 26.3
TOTALS_HOURS_VALUE_X = 90.0
TOTALS_EXPENSES_LABEL_X = 246.7
TOTALS_EXPENSES_VALUE_X = 324.0
TOTALS_TRAVEL_LABEL_X = 435.8
TOTALS_TRAVEL_VALUE_X = 515.2


@dataclass
class ActivityEntry:
    activity_type: str          # e.g. "Log", "Contact", "Inspection/Scope"
    due_date: str               # e.g. "7/15/2025"
    status: str = "Not Completed"  # "Not Completed" or "Completed"
    description: str = ""       # e.g. "Received Claim for processing"


@dataclass
class DiaryData:
    # Header fields
    insured_name: str = ""
    property_address: str = ""
    mailing_address: str = ""
    insured_tel: str = ""
    policy_no: str = ""
    date_of_loss: str = ""
    catastrophe_no: str = ""
    adj_file_no: str = ""
    loss_amount: str = ""

    # Referral row
    referral_date: str = ""
    date_insured_contacted: str = ""
    date_loss_inspected: str = ""

    # Report date (printed in footer + top of referral context)
    report_date: str = ""

    # Activity entries
    activities: list = field(default_factory=list)

    # Totals
    total_hours: str = "0.00"
    total_expenses: str = "0.00"
    total_travel: str = "0.00"


def _draw_header(page, data: DiaryData):
    """Draw the claim info header — pixel-identical to Venue output."""

    # Left column - labels
    left_labels = ["Insured :", "Property Address :", "Mailing Address :", "Insured Tel. No. :"]
    left_values = [data.insured_name, data.property_address, data.mailing_address, data.insured_tel]

    for i, (label, value) in enumerate(zip(left_labels, left_values)):
        y = HEADER_ROW_Y[i] + ASCENT_10
        page.insert_text(fitz.Point(HEADER_LABEL_X, y),
                        label, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))
        if value:
            page.insert_text(fitz.Point(HEADER_VALUE_X, y),
                            value, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Right column - labels
    right_labels = ["Policy No. :", "Date of Loss :", "Catastrophe No. :", "Adj. File No. :", "Loss Amount:"]
    right_values = [data.policy_no, data.date_of_loss, data.catastrophe_no, data.adj_file_no, data.loss_amount]

    for i, (label, value) in enumerate(zip(right_labels, right_values)):
        y = HEADER_RIGHT_ROW_Y[i] + ASCENT_10
        page.insert_text(fitz.Point(HEADER_RIGHT_LABEL_X, y),
                        label, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))
        if value:
            page.insert_text(fitz.Point(HEADER_RIGHT_VALUE_X, y),
                            value, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))


def _draw_referral_row(page, data: DiaryData):
    """Draw the referral date / contact / inspected row."""

    # Thin line above
    page.draw_line(fitz.Point(LINE_LEFT_X, HEADER_LINE_Y),
                   fitz.Point(LINE_RIGHT_X, HEADER_LINE_Y),
                   color=(0, 0, 0), width=THIN_LINE_WIDTH)

    y = REFERRAL_ROW_Y + ASCENT_10  # baseline

    # "Referral Date" at x=56
    page.insert_text(fitz.Point(56.0, y),
                    "Referral Date", fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # "Date Insured Contacted:" at x=226.9
    page.insert_text(fitz.Point(226.9, y),
                    "Date Insured Contacted:", fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Contact date value at x=338.9
    if data.date_insured_contacted:
        page.insert_text(fitz.Point(338.9, y),
                        data.date_insured_contacted, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # "Date Loss Inspected:" at x=437.5
    page.insert_text(fitz.Point(437.5, y),
                    "Date Loss Inspected:", fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Inspected date value at x=534.8
    if data.date_loss_inspected:
        page.insert_text(fitz.Point(534.8, y + 0.6),  # slight offset per extraction
                        data.date_loss_inspected, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Thin line below
    page.draw_line(fitz.Point(LINE_LEFT_X, POST_REFERRAL_LINE_Y),
                   fitz.Point(LINE_RIGHT_X, POST_REFERRAL_LINE_Y),
                   color=(0, 0, 0), width=THIN_LINE_WIDTH)


def _draw_title(page):
    """Draw 'Activity Report' title and double separator line."""

    # Title — Helvetica-Bold 14pt
    page.insert_text(fitz.Point(TITLE_X, TITLE_Y + ASCENT_14),
                    "Activity Report", fontsize=14, fontname=FONT_BOLD, color=(0, 0, 0))

    # Double separator lines
    page.draw_line(fitz.Point(LINE_LEFT_X, DOUBLE_LINE_Y1),
                   fitz.Point(LINE_RIGHT_X, DOUBLE_LINE_Y1),
                   color=(0, 0, 0), width=THIN_LINE_WIDTH)
    page.draw_line(fitz.Point(LINE_LEFT_X, DOUBLE_LINE_Y2),
                   fitz.Point(LINE_RIGHT_X, DOUBLE_LINE_Y2),
                   color=(0, 0, 0), width=THIN_LINE_WIDTH)


def _draw_activity_entry(page, entry: ActivityEntry, slot_y: float):
    """Draw a single activity entry at the given y position."""

    baseline = slot_y + ASCENT_10  # text baseline from bbox top

    # "Activity" label
    page.insert_text(fitz.Point(ACTIVITY_LABEL_X, baseline),
                    "Activity", fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Activity type name
    page.insert_text(fitz.Point(ACTIVITY_NAME_X, baseline),
                    entry.activity_type, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # "Due:" label
    page.insert_text(fitz.Point(DUE_LABEL_X, baseline),
                    "Due:", fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Due date value
    page.insert_text(fitz.Point(DUE_DATE_X, baseline),
                    entry.due_date, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Status — Helvetica-BoldOblique
    page.insert_text(fitz.Point(STATUS_X, baseline),
                    entry.status, fontsize=10, fontname=FONT_BOLD_ITALIC, color=(0, 0, 0))

    # "Description:" label
    desc_baseline = baseline + DESC_OFFSET_Y
    page.insert_text(fitz.Point(DESCRIPTION_LABEL_X, desc_baseline),
                    "Description:", fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Description text
    if entry.description:
        page.insert_text(fitz.Point(DESCRIPTION_TEXT_X, desc_baseline),
                        entry.description, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))

    # Underline below description
    underline_y = slot_y + UNDERLINE_OFFSET_Y
    page.draw_line(fitz.Point(UNDERLINE_X_START, underline_y),
                   fitz.Point(UNDERLINE_X_END, underline_y),
                   color=(0, 0, 0), width=THICK_LINE_WIDTH)


def _draw_totals(page, data: DiaryData):
    """Draw the totals footer section on the last page."""

    # "Totals for completed activities" — Helvetica-Bold
    page.insert_text(fitz.Point(TOTALS_TITLE_X, TOTALS_TITLE_Y + ASCENT_10),
                    "Totals for completed activities",
                    fontsize=10, fontname=FONT_BOLD, color=(0, 0, 0))

    # Thin line
    page.draw_line(fitz.Point(LINE_LEFT_X, TOTALS_LINE_Y),
                   fitz.Point(LINE_RIGHT_X, TOTALS_LINE_Y),
                   color=(0, 0, 0), width=THIN_LINE_WIDTH)

    # Totals row — Times-Bold
    y = TOTALS_ROW_Y + ASCENT_10

    page.insert_text(fitz.Point(TOTALS_HOURS_LABEL_X, y),
                    "Total Hours:", fontsize=10, fontname=FONT_TIMES_BOLD, color=(0, 0, 0))
    page.insert_text(fitz.Point(TOTALS_HOURS_VALUE_X, y),
                    data.total_hours, fontsize=10, fontname=FONT_TIMES_BOLD, color=(0, 0, 0))

    page.insert_text(fitz.Point(TOTALS_EXPENSES_LABEL_X, y),
                    "Total Expenses:", fontsize=10, fontname=FONT_TIMES_BOLD, color=(0, 0, 0))
    page.insert_text(fitz.Point(TOTALS_EXPENSES_VALUE_X, y),
                    data.total_expenses, fontsize=10, fontname=FONT_TIMES_BOLD, color=(0, 0, 0))

    page.insert_text(fitz.Point(TOTALS_TRAVEL_LABEL_X, y),
                    "Total Travel:", fontsize=10, fontname=FONT_TIMES_BOLD, color=(0, 0, 0))
    page.insert_text(fitz.Point(TOTALS_TRAVEL_VALUE_X, y),
                    data.total_travel, fontsize=10, fontname=FONT_TIMES_BOLD, color=(0, 0, 0))


def _draw_footer(page, report_date: str, page_num: int):
    """Draw page footer — date and page number."""
    page.insert_text(fitz.Point(FOOTER_DATE_X, FOOTER_Y + ASCENT_10),
                    report_date, fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))
    page.insert_text(fitz.Point(FOOTER_PAGE_X, FOOTER_Y + ASCENT_10),
                    f"Page: {page_num}", fontsize=10, fontname=FONT_REGULAR, color=(0, 0, 0))


def generate_diary_report(data: DiaryData, output_path: str) -> str:
    """
    Generate a pixel-identical Activity Report (Diary) PDF.

    Returns the output path.
    """
    if not data.report_date:
        data.report_date = datetime.now().strftime("%-m/%d/%Y")

    doc = fitz.open()
    activities = data.activities or []
    total_pages = 1  # at minimum

    if len(activities) > MAX_ENTRIES_PAGE1:
        remaining = len(activities) - MAX_ENTRIES_PAGE1
        total_pages += (remaining + MAX_ENTRIES_CONTINUATION - 1) // MAX_ENTRIES_CONTINUATION

    entry_idx = 0
    for page_num in range(1, total_pages + 1):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)

        if page_num == 1:
            # Full header on page 1
            _draw_header(page, data)
            _draw_referral_row(page, data)
            _draw_title(page)

            # Activity entries on page 1
            entries_this_page = min(MAX_ENTRIES_PAGE1, len(activities) - entry_idx)
            for slot in range(entries_this_page):
                slot_y = FIRST_ACTIVITY_Y + (slot * ACTIVITY_SPACING)
                _draw_activity_entry(page, activities[entry_idx], slot_y)
                entry_idx += 1
        else:
            # Continuation pages — entries start near the top
            first_entry_y = 15.1  # from extraction: page 2 starts at y=15.1
            entries_this_page = min(MAX_ENTRIES_CONTINUATION, len(activities) - entry_idx)
            for slot in range(entries_this_page):
                slot_y = first_entry_y + (slot * ACTIVITY_SPACING)
                _draw_activity_entry(page, activities[entry_idx], slot_y)
                entry_idx += 1

        # Totals on last page only
        if page_num == total_pages:
            _draw_totals(page, data)

        # Page footer
        _draw_footer(page, data.report_date, page_num)

    doc.save(output_path)
    doc.close()
    return output_path


# --- Test ---
if __name__ == "__main__":
    import os

    test_data = DiaryData(
        insured_name="Caesar Brown/Michelle Brown",
        property_address="378 Brook Ave, North Plainfield, NJ 07062",
        mailing_address="378 Brook Ave, North Plainfield, NJ 07062",
        insured_tel="(973) 665-9276",
        policy_no="8008049002",
        date_of_loss="7/14/2025",
        catastrophe_no="",
        adj_file_no="FG151437",
        loss_amount="$185,883.36",
        referral_date="",
        date_insured_contacted="7/15/2025",
        date_loss_inspected="7/17/2025",
        report_date="9/12/2025",
        activities=[
            ActivityEntry("Log", "7/15/2025", "Not Completed", "Received Claim for processing"),
            ActivityEntry("Contact", "7/15/2025", "Not Completed", "Contact made with Insured"),
            ActivityEntry("Inspection/Scope", "7/17/2025", "Not Completed", "Risk/Loss inspection and scope"),
            ActivityEntry("Preliminary Report", "7/17/2025", "Not Completed", "Completion of Preliminary Report"),
            ActivityEntry("Follow-up", "7/31/2025", "Not Completed", "Follow-up call to Insured"),
            ActivityEntry("Flood Estimate", "8/12/2025", "Not Completed", "Estimate/Scope for Flood Loss"),
            ActivityEntry("Follow-up", "8/17/2025", "Not Completed", "Follow-up call to Insured"),
            ActivityEntry("30 Day Status", "8/18/2025", "Not Completed", "30 Day diary report"),
            ActivityEntry("Contact", "8/29/2025", "Not Completed", "Contact made with Insured"),
            ActivityEntry("Review", "9/8/2025", "Not Completed", "Final Closing Review"),
        ],
        total_hours="0.00",
        total_expenses="0.00",
        total_travel="0.00",
    )

    out_dir = os.path.join(os.path.dirname(__file__), "test_output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "diary_test.pdf")

    generate_diary_report(test_data, out_path)
    print(f"Generated: {out_path}")
