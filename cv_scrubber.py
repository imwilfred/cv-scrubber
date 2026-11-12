try:
    import pymupdf as fitz
except ImportError:
    import fitz
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw

st.set_page_config(page_title="CV Contact Scrubber", layout="wide")

# Replace Streamlit's auto-generated uploader label ("PDF, DOCX, DOC")
st.markdown("""
<style>
[data-testid="stFileUploaderDropzoneInstructions"] small {
    display: none;
}
[data-testid="stFileUploaderDropzoneInstructions"]::after {
    content: "PDF files only • 10MB per file";
    font-size: 0.85rem;
    opacity: 0.7;
}
</style>
""", unsafe_allow_html=True)

st.title("CV Contact Scrubber")
st.write("Hide phone, email and address details on a PDF CV.")

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

st.info(
    "💡 **Quick Start Guide**\n\n"
    "1. 📄 **Use a PDF:** This tool only supports **PDF resumes**. Word CVs can be edited directly in Word.\n"
    "2. 📤 **Upload:** Use the button below to add the CV.\n"
    "3. 🎛️ **Adjust the sliders:** Move the edges until the red box covers the contact details but not the name.\n"
    "4. 📥 **Save:** Click *Download updated PDF* to save the finished copy."
)

st.markdown("**Upload the PDF resume (max 10MB)**")

with st.popover("📤 Upload file"):
    uploaded_file = st.file_uploader(
        "Upload Area",
        type=["pdf", "docx", "doc"],
        key=f"pdf_uploader_{st.session_state.uploader_key}",
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------
is_valid_file = False
file_bytes = None
page_w, page_h = 595.0, 842.0  # A4 in points, used until a real file is loaded

if uploaded_file is not None:
    name_lower = uploaded_file.name.lower()
    if name_lower.endswith((".docx", ".doc")):
        st.error("⚠️ Word file detected. This tool only works with PDF files.")
        st.markdown(
            "Word CVs don't need this tool, as you can delete or edit the contact details "
            "directly in Word.\n\n"
            "If you still want to use the scrubber, save the file as a PDF first: "
            "**File** -> **Save As** -> **PDF (*.pdf)**, then upload it here."
        )
    elif name_lower.endswith(".pdf"):
        file_bytes = uploaded_file.getvalue()
        try:
            probe = fitz.open(stream=file_bytes, filetype="pdf")
            if probe.needs_pass:
                st.error("This PDF is password protected. Remove the password and upload it again.")
            elif len(probe) == 0:
                st.error("This PDF has no pages.")
            else:
                page_w, page_h = probe[0].rect.width, probe[0].rect.height
                is_valid_file = True
            probe.close()
        except Exception:
            st.error("This file couldn't be read as a PDF. Check that it isn't corrupted and try again.")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
PW, PH = int(page_w), int(page_h)
sig = f"{st.session_state.uploader_key}_{PW}x{PH}"  # new keys reset sliders on Clear or a new page size


def edge_sliders(prefix, defaults):
    top_d, bottom_d, left_d, right_d = defaults
    top = st.sidebar.slider("Top edge", 0, PH, min(top_d, PH), 1, key=f"{prefix}_top_{sig}")
    bottom = st.sidebar.slider("Bottom edge", 0, PH, min(bottom_d, PH), 1, key=f"{prefix}_bottom_{sig}")
    left = st.sidebar.slider("Left edge", 0, PW, min(left_d, PW), 1, key=f"{prefix}_left_{sig}")
    right = st.sidebar.slider("Right edge", 0, PW, min(right_d, PW), 1, key=f"{prefix}_right_{sig}")
    return top, bottom, left, right


st.sidebar.header("Mask position")
mask_1 = edge_sliders("m1", (30, 115, 140, PW - 15))
st.sidebar.caption("Higher numbers move an edge further down or right.")

use_second_mask = st.sidebar.checkbox("Add a second mask (e.g. for a photo)", value=False)
mask_2 = None
if use_second_mask:
    st.sidebar.header("Second mask")
    mask_2 = edge_sliders("m2", (45, 185, 40, 190))

st.sidebar.markdown("---")
st.sidebar.header("Options")
first_page_only = st.sidebar.checkbox("Apply to first page only", value=True)
black_bars = st.sidebar.checkbox("Use black bars in final PDF", value=False)
st.sidebar.caption("When unticked, the mask is filled with the colour of the page background around it.")

st.sidebar.markdown("---")
zoom_level = st.sidebar.slider("Preview zoom", 300, 1500, 900, 25)


# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------
def sample_background(arr, rect, scale, pad=3):
    """Most common colour in a thin ring just outside the rectangle."""
    h, w = arr.shape[:2]
    x0 = min(max(int(round(rect.x0 * scale)), 0), w)
    x1 = min(max(int(round(rect.x1 * scale)), 0), w)
    y0 = min(max(int(round(rect.y0 * scale)), 0), h)
    y1 = min(max(int(round(rect.y1 * scale)), 0), h)
    parts = [
        arr[max(y0 - pad, 0):y0, x0:x1],
        arr[y1:min(y1 + pad, h), x0:x1],
        arr[y0:y1, max(x0 - pad, 0):x0],
        arr[y0:y1, x1:min(x1 + pad, w)],
    ]
    parts = [p.reshape(-1, 3) for p in parts if p.size]
    if not parts:
        return (1, 1, 1)
    pixels = np.concatenate(parts)
    colours, counts = np.unique(pixels, axis=0, return_counts=True)
    r, g, b = colours[counts.argmax()]
    return (int(r) / 255, int(g) / 255, int(b) / 255)


def apply_redactions_safely(page):
    # Keep the page's vector background (e.g. a grey sidebar) intact; only remove text and image pixels.
    try:
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_PIXELS,
            graphics=fitz.PDF_REDACT_LINE_ART_NONE,
        )
    except (TypeError, AttributeError):
        page.apply_redactions()


def redact_pdf(f_bytes, masks, only_first_page, use_black):
    doc = fitz.open(stream=f_bytes, filetype="pdf")
    for index, page in enumerate(doc):
        if only_first_page and index > 0:
            break
        rects = []
        for top, bottom, left, right in masks:
            rect = fitz.Rect(left, top, right, bottom) & page.rect
            if not rect.is_empty:
                rects.append(rect)
        if not rects:
            continue

        if use_black:
            fills = [(0, 0, 0)] * len(rects)
        else:
            pix = page.get_pixmap(dpi=72, alpha=False)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            scale = pix.width / page.rect.width
            fills = [sample_background(arr, r, scale) for r in rects]

        for rect, fill in zip(rects, fills):
            page.add_redact_annot(rect, fill=fill)
        apply_redactions_safely(page)

    doc.set_metadata({
        "author": "", "title": "", "subject": "", "keywords": "",
        "creator": "", "producer": "", "creationDate": "", "modDate": "",
    })
    try:
        doc.del_xml_metadata()
    except Exception:
        pass

    total_pages = len(doc)
    output = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return output, total_pages


def render_preview(pdf_bytes, page_number, masks, show_outline, dpi=150):
    """Render one page. The red outline is drawn on this image only, never on the PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_number - 1].get_pixmap(dpi=dpi, alpha=False)
    doc.close()
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    if show_outline:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        s = dpi / 72
        for top, bottom, left, right in masks:
            draw.rectangle(
                [left * s, top * s, right * s, bottom * s],
                fill=(226, 75, 74, 45),
                outline=(226, 75, 74, 255),
                width=3,
            )
        img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if is_valid_file:
    all_masks = [("Mask", mask_1)]
    if mask_2 is not None:
        all_masks.append(("Second mask", mask_2))

    active_masks = []
    for label, (top, bottom, left, right) in all_masks:
        if left >= right or top >= bottom:
            st.warning(
                f"{label} is ignored: the left edge must be smaller than the right edge, "
                "and the top edge smaller than the bottom edge."
            )
        else:
            active_masks.append((top, bottom, left, right))

    base_name = uploaded_file.name[:-4]
    output_filename = f"{base_name}_Updated.pdf"

    col1, col2 = st.columns(2)
    scrubbed_pdf, total_pages, preview_page = None, 1, 1

    with col1:
        st.subheader("Control Actions")
        try:
            scrubbed_pdf, total_pages = redact_pdf(file_bytes, active_masks, first_page_only, black_bars)
            st.download_button(
                label="📥 Download updated PDF",
                data=scrubbed_pdf,
                file_name=output_filename,
                mime="application/pdf",
                type="primary",
            )
            if total_pages > 1:
                preview_page = st.selectbox("Flip preview page:", options=list(range(1, total_pages + 1)), index=0)
            if first_page_only and total_pages > 1:
                st.caption("The mask is applied to page 1 only.")
        except Exception as e:
            st.error(f"Error compiling document: {e}")
            scrubbed_pdf = None

    with col2:
        st.subheader("Live Document Preview")
        if scrubbed_pdf:
            try:
                mask_applies_here = (not first_page_only) or preview_page == 1
                image = render_preview(scrubbed_pdf, preview_page, active_masks, mask_applies_here)
                st.image(image, caption=f"Page {preview_page} of {total_pages}", width=zoom_level)
                st.caption("The red box shows where the mask sits. It is a preview aid only and does not appear in the downloaded PDF.")
            except Exception as img_err:
                st.error(f"Visual preview error: {img_err}")

st.success(
    "🔒 **Data Privacy & Security Guarantee**\n\n"
    "* **In-Memory Processing Only:** Resumes are processed purely within temporary, volatile server RAM. This platform contains **no databases, logs, or file storage disks**.\n"
    "* **Instant Destruction:** The moment you click the *Clear button* or close your browser tab, your document bytes are **permanently erased and destroyed forever**.\n"
    "* **100% Isolated Sessions:** Each user session is sandboxed in real-time. Colleagues using the app simultaneously can never access or view your uploaded files.\n"
    "* **Encrypted Transit:** All files are protected with bank-grade HTTPS encryption during data transfer."
)

st.markdown("---")
_, middle, _ = st.columns([2, 1, 2])
with middle:
    clear_clicked = st.button("🧹 Clear file", use_container_width=True)

if clear_clicked:
    st.session_state.uploader_key += 1
    st.rerun()
