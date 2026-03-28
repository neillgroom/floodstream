"""
Photo sheet generator — pixel-identical to accepted Venue submissions.

Layout per page:
- Header: FG logo (left) + claim info (center) + dates/IDs (right)
- 2 photos per page
- Each photo: image on left (~400pt wide), metadata on right
- Photo ID label above each photo
- Standard order: Front of Risk, Address, Left, Right, Rear, Ext WM, Int WM
- Footer: "Page: X" bottom right

All coordinates extracted from actual accepted submission.
"""

import io
import os
from dataclasses import dataclass
from datetime import datetime

import fitz  # PyMuPDF
from PIL import Image

PAGE_W = 612
PAGE_H = 842

# FG logo path
LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "fg_logo_extracted.png")
# Fallback to original logo if extracted doesn't exist
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "fg_logo.png")

# Standard NFIP photo labels in order
MAX_PHOTO_BYTES = 500 * 1024  # 500KB target per photo
MAX_PHOTO_DIMENSION = 1200  # max width or height in pixels


def _compress_photo(image_path: str) -> bytes:
    """Compress a photo to ~500KB JPEG. Returns bytes."""
    img = Image.open(image_path)

    # Convert RGBA/palette to RGB
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    # Resize if larger than max dimension
    w, h = img.size
    if max(w, h) > MAX_PHOTO_DIMENSION:
        ratio = MAX_PHOTO_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # JPEG compress — start at quality 75, lower if still too big
    for quality in [75, 60, 45, 30]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_PHOTO_BYTES:
            return buf.getvalue()
        buf.close()

    # Return whatever we got at lowest quality
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=30, optimize=True)
    return buf.getvalue()


STANDARD_LABELS = [
    "Front of Risk",
    "Address",
    "Left",
    "Right",
    "Rear",
    "Ext WM",
    "Int WM",
    "Interior 1",
    "Interior 2",
    "Interior 3",
]


@dataclass
class PhotoItem:
    image_path: str
    label: str = ""
    date_taken: str = ""
    taken_by: str = "Adjuster"
    comment: str = ""


def _draw_header(page, logo_path, insured_name, location_line1, location_line2,
                 company, company_addr1, company_addr2,
                 date_of_report, date_of_loss, policy_number,
                 claim_number, file_number, adjuster_name):
    """Draw the photo sheet header — pixel-identical to actual submission."""

    # FG Logo (top left)
    if os.path.exists(logo_path):
        logo_rect = fitz.Rect(21, 18, 96, 86)
        page.insert_image(logo_rect, filename=logo_path)

    # Left column — labels
    labels_x = 145.4
    values_x = 211.1
    y_start = 26
    y_step = 14

    labels = ["Insured", "LOCATION:", "", "COMPANY:", "", ""]
    values = [insured_name, location_line1, location_line2,
              company, company_addr1, company_addr2]

    for i, (label, value) in enumerate(zip(labels, values)):
        y = y_start + (i * y_step)
        if label:
            page.insert_text(fitz.Point(labels_x, y), label,
                           fontsize=7, fontname="helv", color=(0, 0, 0))
        if value:
            page.insert_text(fitz.Point(values_x, y), value,
                           fontsize=7, fontname="helv", color=(0, 0, 0))

    # Right column — labels and values
    rlabels_x = 399.2
    rvalues_x = 510.2

    right_labels = ["DATE OF REPORT:", "DATE OF LOSS:", "POLICY NUMBER:",
                    "CLAIM NUMBER:", "OUR FILE NUMBER:", "ADJUSTER NAME:"]
    right_values = [date_of_report, date_of_loss, policy_number,
                    claim_number, file_number, adjuster_name]

    for i, (label, value) in enumerate(zip(right_labels, right_values)):
        y = y_start + (i * y_step)
        page.insert_text(fitz.Point(rlabels_x, y), label,
                       fontsize=7, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(rvalues_x, y), value,
                       fontsize=7, fontname="helv", color=(0, 0, 0))

    # Header box — 4 lines forming a rectangle
    page.draw_line(fitz.Point(18, 15.5), fitz.Point(577, 15.5), color=(0, 0, 0), width=1.0)   # top
    page.draw_line(fitz.Point(18, 100.5), fitz.Point(577, 100.5), color=(0, 0, 0), width=1.0) # bottom
    page.draw_line(fitz.Point(18.5, 15.5), fitz.Point(18.5, 100.5), color=(0, 0, 0), width=1.0)  # left
    page.draw_line(fitz.Point(576.5, 15.5), fitz.Point(576.5, 100.5), color=(0, 0, 0), width=1.0) # right


def _draw_photo(page, photo: PhotoItem, photo_num: int, slot: int):
    """
    Draw a photo in the given slot (0 = top, 1 = bottom).

    Top photo: image at y=142, metadata at right
    Bottom photo: image at y=527, metadata at right
    """
    if slot == 0:
        label_y = 137
        img_y0 = 142
        img_y1 = 442
        meta_x = 428
        meta_y = 151
    else:
        label_y = 519
        img_y0 = 527
        img_y1 = 827
        meta_x = 438
        meta_y = 565

    label_x = 20 if slot == 0 else 18
    img_x0 = 20 if slot == 0 else 18
    img_x1 = 420 if slot == 0 else 418

    # Photo ID label above image
    page.insert_text(fitz.Point(label_x, label_y),
                    f"Photo ID: {photo.label}",
                    fontsize=7, fontname="helv", color=(0, 0, 0))

    # Insert compressed photo
    if os.path.exists(photo.image_path):
        img_rect = fitz.Rect(img_x0, img_y0, img_x1, img_y1)
        try:
            compressed = _compress_photo(photo.image_path)
            page.insert_image(img_rect, stream=compressed, keep_proportion=True)
        except Exception:
            page.draw_rect(img_rect, color=(0.8, 0.8, 0.8), fill=(0.95, 0.95, 0.95))
            page.insert_text(fitz.Point(img_x0 + 150, img_y0 + 150),
                           "Photo unavailable", fontsize=10, fontname="helv")

    # Metadata on right side
    date_str = photo.date_taken or datetime.now().strftime("%m/%d/%Y")

    y_cursor = meta_y
    for line in [f"Photo ID: {photo_num}", f"Date: {date_str}", f"Taken By: {photo.taken_by}"]:
        page.insert_text(fitz.Point(meta_x, y_cursor), line,
                       fontsize=7, fontname="helv", color=(0, 0, 0))
        y_cursor += 10.5

    # Comment with word wrapping (max ~150pt width = ~43 chars at 7pt Helvetica)
    comment_text = f"Comment: {photo.comment}" if photo.comment else "Comment:"
    max_chars = 43
    words = comment_text.split()
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        if len(test) <= max_chars:
            current_line = test
        else:
            page.insert_text(fitz.Point(meta_x, y_cursor), current_line,
                           fontsize=7, fontname="helv", color=(0, 0, 0))
            y_cursor += 10.5
            current_line = word
    if current_line:
        page.insert_text(fitz.Point(meta_x, y_cursor), current_line,
                       fontsize=7, fontname="helv", color=(0, 0, 0))


def generate_photo_sheets(
    photos: list[PhotoItem],
    output_path: str,
    insured_name: str = "",
    location_line1: str = "",
    location_line2: str = "",
    company: str = "",
    company_addr1: str = "",
    company_addr2: str = "",
    date_of_report: str = "",
    date_of_loss: str = "",
    policy_number: str = "",
    claim_number: str = "",
    file_number: str = "",
    adjuster_name: str = "Julio Lopez",
) -> str:
    """
    Generate photo sheet pages — 2 photos per page with claim header.

    Returns path to the generated PDF.
    """
    if not photos:
        return ""

    doc = fitz.open()

    # Process photos 2 at a time
    for page_idx in range(0, len(photos), 2):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)

        # Draw header on every page
        _draw_header(
            page, LOGO_PATH,
            insured_name, location_line1, location_line2,
            company, company_addr1, company_addr2,
            date_of_report, date_of_loss, policy_number,
            claim_number, file_number, adjuster_name,
        )

        # Top photo (slot 0)
        photo1 = photos[page_idx]
        _draw_photo(page, photo1, page_idx + 1, slot=0)

        # Bottom photo (slot 1) if exists
        if page_idx + 1 < len(photos):
            photo2 = photos[page_idx + 1]
            _draw_photo(page, photo2, page_idx + 2, slot=1)

        # Page footer
        page_num = (page_idx // 2) + 1
        page.insert_text(fitz.Point(532, 831),
                        f"Page: {page_num}",
                        fontsize=7, fontname="helv", color=(0, 0, 0))

    doc.save(output_path)
    doc.close()
    return output_path


# --- Test ---
if __name__ == "__main__":
    test_photos = []
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "fcn_card.png")

    for i, label in enumerate(STANDARD_LABELS[:7]):
        test_photos.append(PhotoItem(
            image_path=logo_path,
            label=label,
            date_taken="11/08/2024",
            taken_by="Adjuster",
            comment=f"Test comment for {label}" if i == 0 else "",
        ))

    out = os.path.join(os.path.dirname(__file__), "test_output", "photo_sheet_test.pdf")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    generate_photo_sheets(
        test_photos, out,
        insured_name="HAHNS  KANODE",
        location_line1="301 S GULF BLVD UNIT 417,",
        location_line2="PLACIDA,FL,33946",
        company="First Community Insurance Company",
        company_addr1="PO Box 33061,",
        company_addr2="St Peteresburg,FL,33733",
        date_of_report="11/10/2024",
        date_of_loss="10/09/2024",
        policy_number="6820579039",
        claim_number="567121",
        file_number="FG149855",
    )
    print(f"Generated: {out}")
