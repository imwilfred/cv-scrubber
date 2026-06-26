import streamlit as st
import fitz, io
from pdf2image import convert_from_bytes

st.set_page_config(page_title="PDF CV Scrubber", layout="wide")
st.title("Interactive PDF CV Contact Scrubber")
st.write("Upload your resume and use manual sliders to position masks perfectly.")

# Initialize session states safely with your target defaults
if "top_boundary_val" not in st.session_state: st.session_state.top_boundary_val = 30
if "h_limit_val" not in st.session_state: st.session_state.h_limit_val = 140
if "v_limit_val" not in st.session_state: st.session_state.v_limit_val = 115
if "active_layout" not in st.session_state: st.session_state.active_layout = "Standard Layout"

st.sidebar.header("Layout Settings")
layout_style = st.sidebar.selectbox("Select layout style:", options=["Standard Layout", "Two-Column Sidebar Layout"], key="layout_style_selection")

st.sidebar.markdown("---")
st.sidebar.header("Redaction Block Aesthetics")
mask_color_toggle = st.sidebar.checkbox("⬛ Use Solid Black Redaction Bars", value=False)
chosen_color = (0, 0, 0) if mask_color_toggle else (1, 1, 1)

if layout_style != st.session_state.active_layout:
    st.session_state.active_layout = layout_style
    if "Two-Column" in layout_style: 
        st.session_state.top_boundary_val, st.session_state.h_limit_val, st.session_state.v_limit_val = 88, 220, 260
    else: 
        st.session_state.top_boundary_val, st.session_state.h_limit_val, st.session_state.v_limit_val = 30, 140, 115

uploaded_file = st.file_uploader("Upload the PDF Resume", type=["pdf", "docx", "doc"])

if uploaded_file is not None and uploaded_file.name.lower().endswith((".docx", ".doc")):
    st.error("⚠️ Invalid File Type Detected!")
    st.markdown("Our CV Scrubber can only process **PDF files**.\n\n**How to convert your Word document:**\n1. Open file in Word.\n2. Click **File** -> **Save As**.\n3. Select **PDF (*.pdf)** from format list.\n4. Upload new PDF here.")
    st.stop()

if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)

st.sidebar.markdown("---")
st.sidebar.header("Live Mask Adjustment")
top_boundary = st.sidebar.slider("Mask Top Boundary (Vertical Start)", 0, 200, st.session_state.top_boundary_val, 1, key="top_slider")
st.session_state.top_boundary_val = top_boundary

if "Two-Column" in layout_style:
    h_limit = st.sidebar.slider("Mask Width Barrier", 100, 300, st.session_state.h_limit_val, 1, key="h_slider_two")
    v_limit = st.sidebar.slider("Mask Height Ceiling", 100, 500, st.session_state.v_limit_val, 1, key="v_slider_two")
else:
    h_limit = st.sidebar.slider("Right Mask Start Width", 10, 500, st.session_state.h_limit_val, 1, key="h_slider_std")
    v_limit = st.sidebar.slider("Right Mask Vertical Limit", 10, 500, st.session_state.v_limit_val, 1, key="v_slider_std")
st.session_state.h_limit_val, st.session_state.v_limit_val = h_limit, v_limit

st.sidebar.markdown("---")
zoom_level = st.sidebar.slider("Document Zoom Level", 300, 1500, 900, 25)

# --- CORE REDACTION ENGINE: Direct manual layout drawing matrix ---
def redact_pdf(f_bytes, layout_profile, w_barrier, h_ceiling, top_start, mask_color):
    doc = fitz.open(stream=f_bytes, filetype="pdf")
    for page in doc:
        page_width = page.rect.width
        if "Standard Layout" in layout_profile:
            # Unbreakable target box: locks cleanly onto your custom live slider configurations
            mask_box = fitz.Rect(w_barrier, top_start, page_width - 15, h_ceiling)
            page.add_redact_annot(mask_box, fill=mask_color)
        else:
            sidebar_mask = fitz.Rect(0, top_start, w_barrier, h_ceiling)
            page.add_redact_annot(sidebar_mask, fill=mask_color)
        page.apply_redactions()
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    total_pages = len(doc)
    doc.close()
    return output_buffer.getvalue(), total_pages

if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
    base_name = uploaded_file.name[:-4]
    output_filename = f"{base_name}_Redacted.pdf"
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Control Actions")
        try:
            # Passes all slider dimensions directly into the drawing engine cleanly
            scrubbed_pdf, total_pages = redact_pdf(file_bytes, layout_style, h_limit, v_limit, top_boundary, chosen_color)
            st.success("Calculated successfully!")
            st.download_button(label="Download Redacted PDF", data=scrubbed_pdf, file_name=output_filename, mime="application/pdf", type="primary")
            preview_page = st.selectbox("Flip Preview Page:", options=list(range(1, total_pages + 1)), index=0) if total_pages > 1 else 1
        except Exception as e: 
            st.error(f"Error compiling document: {e}")
            scrubbed_pdf, total_pages, preview_page = None, 1, 1
            
    st.markdown("---")
    if st.button("🧹 Clear Current File", use_container_width=True): 
        st.rerun()
        
    with col2:
        st.subheader("Live Document Preview")
        if scrubbed_pdf:
            try:
                images = convert_from_bytes(scrubbed_pdf, first_page=preview_page, last_page=preview_page)
                if images: st.image(images, caption=f"Page {preview_page} of {total_pages}", width=zoom_level)
            except Exception as img_err: 
                st.error(f"Visual preview error: {img_err}")
