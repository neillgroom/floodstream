"""
Photo labeling via Haiku vision.

Labels each photo with:
- Room/location name (Bathroom, Kitchen, Front of Risk, etc.)
- Short damage description: "Damage from flood to [items bottom to top]"

Generic, factual, no adjectives. Can't nitpick what isn't there.
"""

import base64
import os

import httpx

from photo_sheet import _compress_photo

# Load API key
def _get_api_key():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get("ANTHROPIC_API_KEY", "")


# Standard exterior labels — applied in order for first 7 photos
STANDARD_EXTERIOR_LABELS = [
    "Front of Risk",
    "Address",
    "Left",
    "Right",
    "Rear",
    "Ext WM",
    "Int WM",
]


def label_single_photo(image_path: str, hint: str = "") -> dict:
    """
    Label a single photo using Haiku vision.

    Args:
        image_path: Path to the photo
        hint: Optional hint like "Front of Risk" or "Bathroom"

    Returns:
        dict with 'label' (room/location) and 'comment' (damage description)
    """
    api_key = _get_api_key()
    if not api_key:
        return {"label": hint or "Unknown", "comment": ""}

    compressed = _compress_photo(image_path)
    b64 = base64.b64encode(compressed).decode()

    hint_text = f" This photo is labeled: {hint}." if hint else ""

    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 80,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": (
                        "NFIP flood claim photo. Respond with exactly 2 lines, nothing else.\n"
                        "Line 1: Room or location name (e.g. Bathroom, Kitchen, Front of Risk, Garage)\n"
                        "Line 2: 'Damage from flood to ' then list items visible in the photo from floor up. "
                        "Use generic terms: tile floor, laminate floor, carpet, baseboards, drywall walls, "
                        "painted trim, doors, cabinets, vanity, toilet, appliances. "
                        "Keep it under 15 words. No adjectives, no speculation."
                        f"{hint_text}"
                    )},
                ],
            }],
        },
        timeout=30,
    )

    data = resp.json()
    text = data["content"][0]["text"].strip()
    lines = text.split("\n")

    label = lines[0].strip().rstrip(".") if lines else (hint or "Interior")
    comment = lines[1].strip() if len(lines) > 1 else ""

    # Clean up label — remove numbering, "Line 1:", etc.
    for prefix in ["Line 1:", "Line 2:", "1.", "2.", "Room:", "Location:"]:
        label = label.replace(prefix, "").strip()
        comment = comment.replace(prefix, "").strip()

    return {"label": label, "comment": comment}


def label_photos(photo_paths: list[str], standard_labels: list[str] = None) -> list[dict]:
    """
    Label a batch of photos.

    Args:
        photo_paths: List of image file paths
        standard_labels: Optional pre-set labels for first N photos (exterior sequence)

    Returns:
        List of dicts with 'label' and 'comment' for each photo
    """
    if standard_labels is None:
        standard_labels = STANDARD_EXTERIOR_LABELS

    results = []
    for i, path in enumerate(photo_paths):
        hint = standard_labels[i] if i < len(standard_labels) else ""

        try:
            result = label_single_photo(path, hint=hint)
        except Exception:
            result = {"label": hint or f"Interior {i - len(standard_labels) + 1}", "comment": ""}

        results.append(result)

    return results
