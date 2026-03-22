"""
Photo Sheet Generator for FloodStream Preliminary Reports.

Generates photo pages matching Fountain Group's Venue format:
- Header: Bordered box with FG logo, claim info, report info
- 1 photo per page with Photo ID label, date, taken by, and comment
- Footer: "Photo Sheet - [page] - [date]"
- Photos are compressed before embedding (max 1200px, JPEG quality 65)

Uses ReportLab for PDF generation.
"""

import io
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
FG_MAILING = "P.O. BOX 3998"
FG_CITY_STATE_ZIP = "PINEVILLE, LA 71361"
FG_PHONE = "(800) 604-9509"
FG_EMAIL = "CLAIMS@FGCLAIMS.COM"

# Logo path
FG_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "fg_logo.jpg")

# Photo compression settings
MAX_PHOTO_PX = 1200   # Max dimension (width or height)
JPEG_QUALITY = 65      # JPEG compression quality

# Standard NFIP photo sequence
STANDARD_PHOTO_LABELS = [
    "Front of Risk",
    "Address",
    "Right Side",
    "Left Side",
    "Rear",
    "Exterior Water Mark",
    "Interior Water Mark",
    "Interior Damage 1",
    "Interior Damage 2",
    "Interior Damage 3",
]


@dataclass
class PhotoItem:
    """A single photo for the photo sheet."""
    image_path: str
    label: str = ""           # e.g. "Front of Risk"
    date_taken: str = ""      # e.g. "03/12/2026"
    taken_by: str = "Adjuster"
    comment: str = ""


@dataclass
class ClaimInfo:
    """Claim-level info for the photo sheet header."""
    insured_name: str = ""
    date_of_report: str = ""   # MM/DD/YYYY
    location: str = ""         # Full property address line 1
    location_csz: str = ""     # City,State,ZIP (e.g. "Chester,PA,19013")
    date_of_loss: str = ""     # MM/DD/YYYY
    policy_number: str = ""
    claim_number: str = ""
    company: str = ""          # Carrier name (e.g. "NFIP Direct")
    company_address: str = ""  # Carrier mailing address (multi-line, from NOL)
    fg_file_number: str = ""
    adjuster_name: str = "Julio Lopez"


def compress_photo(image_path: str) -> ImageReader:
    """
    Compress a photo for PDF embedding.
    Resizes to max MAX_PHOTO_PX on longest side, JPEG quality JPEG_QUALITY.
    Returns a ReportLab ImageReader from an in-memory buffer.
    """
    img = Image.open(image_path)

    # Convert RGBA/palette to RGB for JPEG
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    # Resize if larger than max
    w, h = img.size
    if max(w, h) > MAX_PHOTO_PX:
        if w > h:
            new_w = MAX_PHOTO_PX
            new_h = int(h * MAX_PHOTO_PX / w)
        else:
            new_h = MAX_PHOTO_PX
            new_w = int(w * MAX_PHOTO_PX / h)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Compress to JPEG in memory
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    buf.seek(0)
    return ImageReader(buf), img.size


def generate_photo_sheet(
    claim: ClaimInfo,
    photos: list[PhotoItem],
    output_path: str,
) -> str:
    """
    Generate a photo sheet PDF.

    Args:
        claim: Claim-level info for the header
        photos: List of PhotoItems (1 per page, matching Venue format)
        output_path: Where to save the PDF

    Returns:
        The output path
    """
    c = canvas.Canvas(output_path, pagesize=letter)
    report_date = claim.date_of_report or datetime.now().strftime("%m/%d/%Y")

    for page_idx, photo in enumerate(photos):
        if page_idx > 0:
            c.showPage()

        # Draw bordered header with logo
        header_bottom = _draw_header(c, claim)

        # Draw the photo with info panel
        _draw_photo(c, photo, page_idx + 1, header_bottom)

        # Footer
        _draw_footer(c, page_idx + 1, report_date)

    c.save()
    return output_path


def _draw_header(c: canvas.Canvas, claim: ClaimInfo) -> float:
    """
    Draw the photo sheet header matching Venue's bordered box layout.

    ┌──────────┬─────────────────────┬──────────────────────┐
    │  [LOGO]  │ Insured: ...        │ DATE OF REPORT: ...  │
    │          │ LOCATION: ...       │ DATE OF LOSS: ...    │
    │          │ COMPANY: ...        │ POLICY NUMBER: ...   │
    │          │   carrier addr...   │ CLAIM NUMBER: ...    │
    │          │                     │ OUR FILE NUMBER: ... │
    │          │                     │ ADJUSTER NAME: ...   │
    └──────────┴─────────────────────┴──────────────────────┘

    Returns the Y coordinate of the bottom of the header box.
    """
    # Box dimensions
    box_left = 0.4 * inch
    box_right = PAGE_W - 0.4 * inch
    box_top = PAGE_H - 0.3 * inch
    box_height = 1.15 * inch
    box_bottom = box_top - box_height

    # Draw outer border
    c.setStrokeColor(black)
    c.setLineWidth(1)
    c.rect(box_left, box_bottom, box_right - box_left, box_height)

    # --- Logo (left column, ~1.3" wide) ---
    logo_col_right = box_left + 1.3 * inch
    # Vertical divider
    c.setLineWidth(0.5)
    c.line(logo_col_right, box_bottom, logo_col_right, box_top)

    if os.path.exists(FG_LOGO_PATH):
        # Center logo in the left column with padding
        logo_w = 1.0 * inch
        logo_h = 0.85 * inch
        logo_x = box_left + (logo_col_right - box_left - logo_w) / 2
        logo_y = box_bottom + (box_height - logo_h) / 2
        try:
            c.drawImage(
                FG_LOGO_PATH, logo_x, logo_y, logo_w, logo_h,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            c.setFont("Helvetica-Bold", 7)
            c.drawString(box_left + 0.1 * inch, box_bottom + 0.5 * inch, "FOUNTAIN GROUP")
            c.drawString(box_left + 0.1 * inch, box_bottom + 0.35 * inch, "ADJUSTERS")

    # --- Right info column divider ---
    right_col_left = box_left + 4.2 * inch
    c.line(right_col_left, box_bottom, right_col_left, box_top)

    # --- Middle column: Insured, Location, Company ---
    mid_x = logo_col_right + 0.1 * inch
    y = box_top - 0.18 * inch
    line_h = 0.14 * inch

    def mid_field(label, value):
        nonlocal y
        c.setFont("Courier-Bold", 7)
        c.drawString(mid_x, y, label)
        label_w = c.stringWidth(label, "Courier-Bold", 7)
        c.setFont("Courier", 7)
        c.drawString(mid_x + label_w + 4, y, str(value))
        y -= line_h

    mid_field("Insured", claim.insured_name.upper())
    mid_field("LOCATION:", claim.location.upper())
    if claim.location_csz:
        c.setFont("Courier", 7)
        c.drawString(mid_x + c.stringWidth("LOCATION:", "Courier-Bold", 7) + 4, y + line_h * 0, "")
        # Second line of location
        c.drawString(mid_x + 0.55 * inch, y, claim.location_csz)
        y -= line_h
    mid_field("COMPANY:", claim.company.upper())
    # Carrier address (may be multi-line)
    if claim.company_address:
        for addr_line in claim.company_address.split("\n"):
            c.setFont("Courier", 7)
            c.drawString(mid_x + 0.55 * inch, y, addr_line.strip().upper())
            y -= line_h

    # --- Right column: Report details ---
    rx = right_col_left + 0.08 * inch
    ry = box_top - 0.18 * inch
    rv_x = rx + 1.15 * inch  # value column

    def right_field(label, value):
        nonlocal ry
        c.setFont("Courier-Bold", 7)
        c.drawString(rx, ry, label)
        c.setFont("Courier", 7)
        c.drawRightString(box_right - 0.1 * inch, ry, str(value))
        ry -= line_h

    right_field("DATE OF REPORT:", claim.date_of_report)
    right_field("DATE OF LOSS:", claim.date_of_loss)
    right_field("POLICY NUMBER:", claim.policy_number)
    right_field("CLAIM NUMBER:", claim.claim_number)
    right_field("OUR FILE NUMBER:", claim.fg_file_number)
    right_field("ADJUSTER NAME:", claim.adjuster_name)

    return box_bottom


def _draw_photo(
    c: canvas.Canvas,
    photo: PhotoItem,
    photo_number: int,
    header_bottom: float,
):
    """Draw a single photo with its info panel (1 per page, below header)."""

    # "Photo ID: [label]" title line above the photo
    label = photo.label or (
        STANDARD_PHOTO_LABELS[photo_number - 1]
        if photo_number <= len(STANDARD_PHOTO_LABELS)
        else f"Photo {photo_number}"
    )
    y_title = header_bottom - 0.25 * inch
    c.setFont("Helvetica", 9)
    c.setFillColor(black)
    c.drawString(0.5 * inch, y_title, f"Photo ID: {label}")

    # Photo area (left side) — ~4.2" wide x 3.8" tall
    photo_x = 0.5 * inch
    photo_w = 4.2 * inch
    photo_h = 3.8 * inch
    photo_y = y_title - 0.15 * inch - photo_h

    # Draw the actual photo
    if os.path.exists(photo.image_path):
        try:
            img_reader, (img_w, img_h) = compress_photo(photo.image_path)
            aspect = img_w / img_h

            # Fit within the box maintaining aspect ratio
            if aspect > 1:  # Landscape
                draw_w = photo_w
                draw_h = draw_w / aspect
                if draw_h > photo_h:
                    draw_h = photo_h
                    draw_w = draw_h * aspect
            else:  # Portrait
                draw_h = photo_h
                draw_w = draw_h * aspect
                if draw_w > photo_w:
                    draw_w = photo_w
                    draw_h = draw_w / aspect

            # Align top-left
            draw_x = photo_x
            draw_y = photo_y + (photo_h - draw_h)

            c.drawImage(
                img_reader,
                draw_x, draw_y, draw_w, draw_h,
                preserveAspectRatio=True,
            )
        except Exception as e:
            # Placeholder if image fails
            c.setStrokeColor(Color(0.85, 0.85, 0.85))
            c.setLineWidth(0.5)
            c.rect(photo_x, photo_y, photo_w, photo_h)
            c.setFont("Helvetica", 9)
            c.setFillColor(Color(0.5, 0.5, 0.5))
            c.drawString(
                photo_x + 10, photo_y + photo_h / 2,
                f"[Image: {os.path.basename(photo.image_path)}]",
            )
            c.setFillColor(black)

    # --- Info panel (right side) ---
    info_x = 5.0 * inch
    info_y = y_title - 0.15 * inch

    c.setFont("Courier-Bold", 8)
    c.setFillColor(black)
    c.drawString(info_x, info_y, f"Photo ID: {photo_number}")
    info_y -= 0.18 * inch

    c.setFont("Courier", 8)
    c.drawString(info_x, info_y, f"Date: {photo.date_taken}")
    info_y -= 0.18 * inch

    c.drawString(info_x, info_y, f"Taken By: {photo.taken_by}")
    info_y -= 0.22 * inch

    # Comment (word wrap in narrow column)
    if photo.comment:
        c.setFont("Courier", 7)
        max_w = PAGE_W - info_x - 0.4 * inch
        words = photo.comment.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if c.stringWidth(test, "Courier", 7) > max_w:
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

    claim = ClaimInfo(
        insured_name="JYL CAPITAL INVESTORS LLC",
        date_of_report="3/13/2026",
        location="811 ELSINORE PL,",
        location_csz="Chester,PA,19013",
        date_of_loss="02/23/2026",
        policy_number="5000025672",
        company="NFIP Direct",
        company_address="6330 SPRING PARKWAY, SUITE 450\nOVERLAND PARK, KS, 66211",
        claim_number="N999920260107",
        fg_file_number="FG152134",
        adjuster_name="Julio Lopez",
    )

    # Use FCN card as placeholder photo
    test_img = os.path.join(os.path.dirname(__file__), "assets", "fcn_card.png")

    photos = []
    for i, label in enumerate(STANDARD_PHOTO_LABELS[:6]):
        comment = ""
        if i == 0:
            comment = (
                "Risk is a single family, tenant occupied, pre firm, "
                "non elevated over a basement and located in risk zone AE. "
                'Ext wm 1". Int wm -80" in the basement. Duration 24 hours. '
                "Advance payment discussed, however insured will advise later."
            )
        photos.append(PhotoItem(
            image_path=test_img,
            label=label,
            date_taken="03/12/2026",
            taken_by="Adjuster",
            comment=comment,
        ))

    out = os.path.join(os.path.dirname(__file__), "test_photo_sheet.pdf")
    generate_photo_sheet(claim, photos, out)
    print(f"Generated: {out} ({len(photos)} photos, {len(photos)} pages)")
