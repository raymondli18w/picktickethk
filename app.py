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

        barcode_width_pt = 300
        barcode_height_pt = 80

        right_edge = 612  # Letter width
        margin = 30
        left = right_edge - barcode_width_pt - margin
        right = right_edge - margin
        top = y - 25
        bottom = top + barcode_height_pt

        if left < 0:
            left = 0
            right = barcode_width_pt

        bg_margin = 15
        bg_rect = fitz.Rect(left - bg_margin, top - bg_margin, right + bg_margin, bottom + bg_margin)
        page.draw_rect(bg_rect, color=(1, 1, 1), fill=(1, 1, 1))

        buf = BytesIO()
        tmp_canvas = canvas.Canvas(buf, pagesize=(barcode_width_pt, barcode_height_pt))

        barcode = code128.Code128(
            item,
            barHeight=barcode_height_pt - 30,
            barWidth=1.5,  # ← your wide, readable style
            humanReadable=True
        )
        barcode_width_actual = barcode.width
        x_offset = (barcode_width_pt - barcode_width_actual) / 2
        barcode.drawOn(tmp_canvas, x_offset, 15)
        tmp_canvas.save()

        buf.seek(0)
        img_pdf = fitz.open("pdf", buf.read())
        target_rect = fitz.Rect(left, top, right, bottom)
        page.show_pdf_page(target_rect, img_pdf, 0)

    return pdf

def generate_clean_barcode_sheet(items):
    """
    Generate a clean, standalone PDF with one large barcode per item,
    using the SAME style as overlay_barcodes (barWidth=1.5, large size).
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 80
    y = height - 120  # Start near top

    for idx, (_, item, _, _) in enumerate(items):
        if y < 200:  # New page if not enough space
            c.showPage()
            y = height - 120

        # Draw item label
        c.setFont("Helvetica-Bold", 20)
        c.drawString(margin, y, f"Item: {item}")
        y -= 50

        # Draw LARGE barcode (same as overlay)
        barcode = code128.Code128(
            item,
            barHeight=80 - 30,  # matches overlay
            barWidth=1.5,       # ← critical: same wide bars
            humanReadable=True
        )
        barcode_width = 300
        barcode_height = 80
        x_pos = margin
        y_pos = y - 70  # position below label

        # Center or align left
        barcode.drawOn(c, x_pos, y_pos)
        y -= 120  # space to next item

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

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

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🖨️ Annotated Picking Ticket"):
                with st.spinner("Generating..."):
                    out_pdf = overlay_barcodes(pdf, items)
                    output = BytesIO()
                    out_pdf.save(output)
                    st.download_button(
                        "📥 Download Annotated PDF",
                        output.getvalue(),
                        "picking_ticket_with_barcodes.pdf",
                        "application/pdf"
                    )

        with col2:
            if st.button("📄 Barcodes Only (No Ticket)"):
                with st.spinner("Generating clean sheet..."):
                    clean_pdf = generate_clean_barcode_sheet(items)
                    st.download_button(
                        "📥 Download Barcodes Only",
                        clean_pdf,
                        "barcodes_only.pdf",
                        "application/pdf"
                    )

    pdf.close()
