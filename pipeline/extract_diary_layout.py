"""
Extract exact text positions, fonts, sizes, and line coordinates from the
Diary Sample PDF. Used to build the pixel-identical diary generator.

Run: python extract_diary_layout.py
"""
import json
import fitz  # PyMuPDF

PDF_PATH = r"C:\Users\neill\Downloads\Diary Sample.pdf"

doc = fitz.open(PDF_PATH)

for page_num in range(len(doc)):
    page = doc[page_num]
    print(f"\n{'='*80}")
    print(f"PAGE {page_num + 1}  (width={page.rect.width}, height={page.rect.height})")
    print(f"{'='*80}")

    # Extract text with exact positions
    print("\n--- TEXT BLOCKS (dict mode) ---")
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    for block in blocks["blocks"]:
        if block["type"] == 0:  # text block
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if text:
                        bbox = span["bbox"]
                        print(f"  x={bbox[0]:.1f} y={bbox[1]:.1f} x1={bbox[2]:.1f} y1={bbox[3]:.1f} "
                              f"size={span['size']:.2f} font='{span['font']}' "
                              f"flags={span['flags']} color=#{span['color']:06x} "
                              f"text='{text}'")

    # Extract drawings (lines, rectangles)
    print("\n--- DRAWINGS ---")
    paths = page.get_drawings()
    for i, path in enumerate(paths):
        for item in path["items"]:
            op = item[0]
            if op == "l":  # line
                p1, p2 = item[1], item[2]
                print(f"  LINE: ({p1.x:.1f}, {p1.y:.1f}) -> ({p2.x:.1f}, {p2.y:.1f}) "
                      f"width={path.get('width', 1):.2f} color={path.get('color')}")
            elif op == "re":  # rectangle
                rect = item[1]
                print(f"  RECT: ({rect.x0:.1f}, {rect.y0:.1f}, {rect.x1:.1f}, {rect.y1:.1f}) "
                      f"width={path.get('width', 1):.2f} color={path.get('color')}")
            elif op == "c":  # curve
                print(f"  CURVE: {item[1:]}")
            elif op == "qu":  # quad
                print(f"  QUAD: {item[1]}")

doc.close()
print("\n\nDone.")
