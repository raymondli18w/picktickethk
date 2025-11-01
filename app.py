import streamlit as st
import fitz  # PyMuPDF
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import letter

def find_item_coordinates(pdf):
    """Find 7–9 digit item numbers starting with 3 in the left margin (x < 200)."""
    coords = []
    for i, page in enumerate(pdf):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t = span["text"].strip()
                    if (
                        t.isdigit()
                        and t.startswith("3")
                        and 7 <= len(t) <= 9
                        and span["bbox"][0] < 200
                    ):
                        coords.append((i, t, span["bbox"][0], span["bbox"][1]))
    return coords

def overlay_barcodes(pdf, items):
    """
    Draw high-quality, wide, light Code128 barcodes on the right side,
    mimicking the clean style of the original top-right barcode.
    """
    for page_index, item, x, y in items:
        page = pdf[page_index]

        # --- Target placement: right side, same vertical level as item
        # We'll place barcode centered around x=500 with breathing room
        # Use a larger width and height to mimic the native barcode's size and spacing

        barcode_width_pt = 300  # Increased width for more quiet zone and readability
        barcode_height_pt = 80  # Increased height for better scanning

        # Place the barcode with a generous margin from the right edge
        right_edge = 612  # Letter size page width
        margin = 30  # 30pt margin from the right edge
        left = right_edge - barcode_width_pt - margin
        right = right_edge - margin
        top = y - 25  # Adjust vertical position for better alignment
        bottom = top + barcode_height_pt

        # Ensure it doesn't go off-page
        if left < 0:
            left = 0
            right = barcode_width_pt

        # --- White background (larger than barcode for ample quiet zone) ---
        bg_margin = 15  # Extra margin for the white background
        bg_rect = fitz.Rect(left - bg_margin, top - bg_margin, right + bg_margin, bottom + bg_margin)
        page.draw_rect(bg_rect, color=(1, 1, 1), fill=(1, 1, 1))

        # --- Generate barcode as a separate high-res PDF ---
        buf = BytesIO()
        tmp_canvas = canvas.Canvas(buf, pagesize=(barcode_width_pt, barcode_height_pt))

        # Create barcode with much wider bars for high readability
        barcode = code128.Code128(
            item,
            barHeight=barcode_height_pt - 30,  # leave margin at top and bottom
            barWidth=1.5,                      # Significantly wider bars for better scanning
            humanReadable=True                 # optional: show number below
        )
        # Center the barcode horizontally in its canvas
        barcode_width_actual = barcode.width
        x_offset = (barcode_width_pt - barcode_width_actual) / 2
        barcode.drawOn(tmp_canvas, x_offset, 15)  # Add margin at bottom
        tmp_canvas.save()

        buf.seek(0)
        img_pdf = fitz.open("pdf", buf.read())

        # --- Embed barcode PDF into main page ---
        target_rect = fitz.Rect(left, top, right, bottom)
        page.show_pdf_page(target_rect, img_pdf, 0)

    return pdf

# --- Streamlit UI ---
st.set_page_config(page_title="Picking Ticket Barcode Generator", layout="centered")
st.title("📦 Picking Ticket Barcode Generator")
st.write(
    """
    Upload a **Picking Ticket PDF** (18 Wheels format).  
    This tool detects item numbers (starting with **3**) and adds **wide, high-quality, readable Code 128 barcodes** 
    on the right side — styled like the original top-right barcode for optimal scanning.
    """
)

uploaded_file = st.file_uploader("Upload Picking Ticket PDF", type=["pdf"])

if uploaded_file:
    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    with st.spinner("🔍 Analyzing picking ticket..."):
        items = find_item_coordinates(pdf)

    if not items:
        st.error("❌ No valid item numbers found (7–9 digits, starting with '3', in left margin).")
    else:
        st.success(f"✅ Found {len(items)} item number(s).")
        if st.checkbox("Show detected item numbers"):
            st.write([i[1] for i in items])

        if st.button("🖨️ Generate Barcode PDF"):
            with st.spinner("🖨️ Generating high-quality barcodes..."):
                out_pdf = overlay_barcodes(pdf, items)
                output = BytesIO()
                out_pdf.save(output)
                output.seek(0)

            st.success("✅ Ready to download!")
            st.download_button(
                "📥 Download PDF with Barcodes",
                data=output,
                file_name="picking_ticket_with_barcodes.pdf",
                mime="application/pdf"
            )

    pdf.close()