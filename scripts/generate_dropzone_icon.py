from PIL import Image, ImageDraw

def create_dropzone_icon(output_path="app/assets/dropzone_upload.png", size=128):
    # High-DPI 128x128 transparent RGBA canvas
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient colors: Cyan to Blue
    c_primary = (0, 242, 254, 240)      # #00F2FE
    c_dark = (2, 132, 199, 255)         # #0284C7
    c_glow = (0, 242, 254, 40)
    c_bg = (15, 23, 42, 180)            # #0F172A

    # 1. Subtle ambient circle glow behind
    draw.ellipse([14, 14, 114, 114], fill=c_glow)

    # 2. Main document shape with folded corner
    # Document bounds: (28, 20) to (100, 108)
    doc_left, doc_top, doc_right, doc_bottom = 32, 22, 96, 106
    fold = 20

    # Document body (polygon excluding top-right fold)
    doc_points = [
        (doc_left, doc_top),
        (doc_right - fold, doc_top),
        (doc_right, doc_top + fold),
        (doc_right, doc_bottom),
        (doc_left, doc_bottom),
    ]
    draw.polygon(doc_points, fill=c_bg, outline=c_dark, width=3)

    # Folded corner triangle
    fold_poly = [
        (doc_right - fold, doc_top),
        (doc_right - fold, doc_top + fold),
        (doc_right, doc_top + fold),
    ]
    draw.polygon(fold_poly, fill=(2, 132, 199, 120), outline=c_primary, width=2)

    # Decorative horizontal document lines
    draw.line([(42, 42), (68, 42)], fill=(100, 116, 139, 180), width=3)
    draw.line([(42, 54), (86, 54)], fill=(100, 116, 139, 140), width=3)

    # 3. Floating Download / Upload Arrow (Cyan glowing badge)
    # Downward arrow centered at (64, 76)
    arrow_poly = [
        (64, 96),   # Arrow tip
        (48, 78),   # Left wing
        (56, 78),   # Left stem in
        (56, 62),   # Left stem top
        (72, 62),   # Right stem top
        (72, 78),   # Right stem in
        (80, 78),   # Right wing
    ]
    draw.polygon(arrow_poly, fill=c_primary, outline=(255, 255, 255, 220), width=2)

    img.save(output_path, "PNG")
    print(f"Created {output_path} successfully ({size}x{size})")

if __name__ == "__main__":
    create_dropzone_icon()
