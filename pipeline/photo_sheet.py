"""
Photo Sheet Generator for FloodStream Preliminary Reports.

Generates photo pages matching Fountain Group's format:
- Header: "Photo Sheet" title, FG address, Insured/Claim/Policy info
- 2 photos per page with label, date, taken by, and comment
- Footer: "Photo Sheet - [page] - [date]"

Uses ReportLab for PDF generation.
"""

import os
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import black, Color
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image


# Page dimensions
PAGE_W, PAGE_H = letter  # 612 x 792 points

# Fountain Group info (static)
FG_NAME = "FOUNTAIN GROUP ADJUSTERS, LLC"
FG_ADDR = "P.O. BOX 3998\nPINEVILLE, LA 71361\n(800)604-9509\nCLAIMS@FGCLAIMS.COM"

# Standard NFIP photo sequence
STANDARD_PHOTO_LABELS = [
    "FRONT OF RISK",
    "ADDRESS",
    "RIGHT SIDE",
    "LEFT SIDE",
    "REAR",
    "EXTERIOR WATER MARK",
    "INTERIOR WATER MARK",
    "INTERIOR DAMAGE 1",
    "INTERIOR DAMAGE 2",
    "INTERIOR DAMAGE 3",
]


@dataclass
class PhotoItem:
    """A single photo for the photo sheet."""
    image_path: str
    label: str = ""           # e.g. "FRONT OF RISK"
    date_taken: str = ""      # e.g. "10/23/2025"
    taken_by: str = "Adjuster"
    comment: str = ""


@dataclass
class ClaimInfo:
    """Claim-level info for the photo sheet header."""
    insured_name: str = ""
    date_of_report: str = ""   # MM/DD/YYYY
    location: str = ""         # Property address
    date_of_loss: str = ""     # MM/DD/YYYY
    policy_number: str = ""
    company: str = ""          # Carrier name
    claim_number: str = ""
    fg_file_number: str = ""
    adjuster_name: str = "Julio Lopez"


def generate_photo_sheet(
    claim: ClaimInfo,
    photos: list[PhotoItem],
    output_path: str,
) -> str:
    """
    Generate a photo sheet PDF.

    Args:
        claim: Claim-level info for the header
        photos: List of PhotoItems (will be arranged 2 per page)
        output_path: Where to save the PDF

    Returns:
        The output path
    """
    c = canvas.Canvas(output_path, pagesize=letter)

    # Process photos 2 per page
    total_pages = (len(photos) + 1) // 2
    report_date = claim.date_of_report or datetime.now().strftime("%m/%d/%Y")

    for page_idx in range(total_pages):
        if page_idx > 0:
            c.showPage()

        # Draw header
        _draw_header(c, claim)

        # Photo 1 (top half)
        photo_num = page_idx * 2
        if photo_num < len(photos):
            photo = photos[photo_num]
            _draw_photo(c, photo, photo_num + 1, position="top")

        # Photo 2 (bottom half)
        photo_num = page_idx * 2 + 1
        if photo_num < len(photos):
            photo = photos[photo_num]
            _draw_photo(c, photo, photo_num + 1, position="bottom")

        # Footer
        _draw_footer(c, page_idx + 1, report_date)

    c.save()
    return output_path


def _draw_header(c: canvas.Canvas, claim: ClaimInfo):
    """Draw the photo sheet header matching FG format."""
    y = PAGE_H - 0.4 * inch

    # "Photo Sheet" title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.5 * inch, y, "Photo Sheet")
    y -= 0.2 * inch

    # FG company info (left side)
    c.setFont("Helvetica", 7)
    c.drawString(0.5 * inch, y, FG_NAME)
    y_fg = y
    for line in FG_ADDR.split("\n"):
        y_fg -= 0.12 * inch
        c.drawString(0.5 * inch, y_fg, line)

    # Claim info (right side)
    right_x = 4.2 * inch
    label_x = right_x
    value_x = right_x + 0.7 * inch
    y_info = PAGE_H - 0.4 * inch

    info_fields = [
        ("Insured:", claim.insured_name),
        ("Claim #:", claim.claim_number),
        ("Policy #:", claim.policy_number),
    ]

    c.setFont("Helvetica", 8)
    for label, value in info_fields:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(label_x, y_info, label)
        c.setFont("Helvetica", 8)
        c.drawString(value_x, y_info, value)
        y_info -= 0.16 * inch

    # Divider line
    y_div = PAGE_H - 1.0 * inch
    c.setStrokeColor(Color(0.8, 0.8, 0.8))
    c.setLineWidth(0.5)
    c.line(0.5 * inch, y_div, PAGE_W - 0.5 * inch, y_div)


def _draw_photo(
    c: canvas.Canvas,
    photo: PhotoItem,
    photo_number: int,
    position: str,  # "top" or "bottom"
):
    """Draw a single photo with its info panel."""
    # Vertical positioning
    if position == "top":
        y_start = PAGE_H - 1.2 * inch
    else:
        y_start = PAGE_H - 5.0 * inch

    # Photo area (left side) — max 3.2" wide x 3.2" tall
    photo_x = 0.5 * inch
    photo_w = 3.2 * inch
    photo_h = 3.2 * inch
    photo_y = y_start - photo_h

    # Draw photo border
    c.setStrokeColor(Color(0.85, 0.85, 0.85))
    c.setLineWidth(0.5)
    c.rect(photo_x, photo_y, photo_w, photo_h)

    # Draw the actual photo
    if os.path.exists(photo.image_path):
        try:
            img = Image.open(photo.image_path)
            img_w, img_h = img.size
            aspect = img_w / img_h

            # Fit within the box maintaining aspect ratio
            if aspect > 1:  # Landscape
                draw_w = photo_w - 4
                draw_h = draw_w / aspect
            else:  # Portrait
                draw_h = photo_h - 4
                draw_w = draw_h * aspect

            # Center in the box
            draw_x = photo_x + (photo_w - draw_w) / 2
            draw_y = photo_y + (photo_h - draw_h) / 2

            c.drawImage(
                ImageReader(photo.image_path),
                draw_x, draw_y, draw_w, draw_h,
                preserveAspectRatio=True,
            )
        except Exception as e:
            # Draw placeholder text if image fails
            c.setFont("Helvetica", 9)
            c.setFillColor(Color(0.5, 0.5, 0.5))
            c.drawString(photo_x + 10, photo_y + photo_h / 2, f"[Image: {os.path.basename(photo.image_path)}]")
            c.setFillColor(black)

    # Info panel (right side)
    info_x = 4.0 * inch
    info_y = y_start - 0.1 * inch

    # Label
    label = photo.label or (STANDARD_PHOTO_LABELS[photo_number - 1]
                            if photo_number <= len(STANDARD_PHOTO_LABELS)
                            else f"PHOTO {photo_number}")

    c.setFont("Helvetica-Bold", 9)
    c.drawString(info_x, info_y, f"Preliminary - {photo_number}-{label}")
    info_y -= 0.2 * inch

    # Date taken
    c.setFont("Helvetica", 8)
    c.setFillColor(Color(0.4, 0.4, 0.4))
    c.drawString(info_x, info_y, f"Date Taken: {photo.date_taken}")
    info_y -= 0.16 * inch

    # Taken by
    c.drawString(info_x, info_y, f"Taken By:   {photo.taken_by}")
    info_y -= 0.2 * inch

    # Comment (word wrap)
    c.setFillColor(black)
    c.setFont("Helvetica", 7.5)
    if photo.comment:
        max_w = PAGE_W - info_x - 0.5 * inch
        words = photo.comment.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if c.stringWidth(test, "Helvetica", 7.5) > max_w:
                c.drawString(info_x, info_y, line)
                info_y -= 0.13 * inch
                line = word
            else:
                line = test
        if line:
            c.drawString(info_x, info_y, line)


def _draw_footer(c: canvas.Canvas, page_num: int, date: str):
    """Draw the footer line."""
    y = 0.4 * inch
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(Color(0.5, 0.5, 0.5))
    c.drawString(0.5 * inch, y, "Photo Sheet")
    c.drawCentredString(PAGE_W / 2, y, f"- {page_num} -")
    c.drawRightString(PAGE_W - 0.5 * inch, y, date)
    c.setFillColor(black)


# --- Quick test ---
if __name__ == "__main__":
    import sys

    # Generate a test photo sheet with placeholder images
    claim = ClaimInfo(
        insured_name="DAGAN HARRIS",
        date_of_report="10/4/2024",
        location="1914 COVE LN, CLEARWATER, FL 33764",
        date_of_loss="09/26/2024",
        policy_number="FLD322815",
        company="PROGRESSIVE",
        claim_number="23714241001",
        fg_file_number="FG141034",
    )

    # Use the example photo page image as a test photo
    test_img = os.path.join(os.path.dirname(__file__), "assets", "fcn_card.png")

    photos = []
    for i, label in enumerate(STANDARD_PHOTO_LABELS[:6]):
        photos.append(PhotoItem(
            image_path=test_img,
            label=label,
            date_taken="10/1/2024",
            taken_by="Adjuster",
            comment=f"Test photo {i+1} — {label.lower()} view of the property." if i == 0 else "",
        ))

    out = os.path.join(os.path.dirname(__file__), "test_photo_sheet.pdf")
    generate_photo_sheet(claim, photos, out)
    print(f"Generated: {out} ({len(photos)} photos, {(len(photos)+1)//2} pages)")
