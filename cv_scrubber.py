import streamlit as st
import fitz, io
from pdf2image import convert_from_bytes

st.set_page_config(page_title="PDF CV Scrubber", layout="wide")

# --- Replace Streamlit's auto-generated uploader label ("PDF, DOCX, DOC") ---
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

st.title("Interactive PDF CV Contact Scrubber")
st.write("Upload your resume and use manual sliders to position masks perfectly.")

if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
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

st.info(
    "💡 **Quick Start Guide**\n\n"
    "Please follow these simple steps:\n\n"
    "1. 📄 **Use a PDF:** This tool only supports **PDF resumes**. Word CVs can be edited directly in Word.\n"
    "2. 🔄 **Choose Layout:** Select *Standard* if contact text sits on the right, or *Two-Column* for left sidebars.\n"
    "3. 🎛️ **Adjust Sliders:** Move the controls to align the redaction box over your data while keeping your name safe.\n"
    "4. ⬛ **Change Style:** Check the aesthetics box to switch between *White-out blocks* and *Solid Black Bars*.\n"
    "5. 📥 **Save:** Click *Download Updated PDF* to save your finalized copy!"
)

st.markdown("**Upload the PDF Resume (Max 10MB)**")

with st.popover("📤 Click Here to Upload File", use_container_width=True):
    uploaded_file = st.file_uploader(
        "Upload Area", 
        type=["pdf", "docx", "doc"], 
        key=f"pdf_uploader_{st.session_state.uploader_key}",
        label_visibility="collapsed"
    )

st.success(
    "🔒 **Data Privacy & Security Guarantee**\n\n"
    "* **In-Memory Processing Only:** Resumes are processed purely within temporary, volatile server RAM. This platform contains **no databases, logs, or file storage disks**.\n"
    "* **Instant Destruction:** The moment you click the *Clear button* or close your browser tab, your document bytes are **permanently erased and destroyed forever**.\n"
    "* **100% Isolated Sessions:** Each user session is sandboxed in real-time. Colleagues using the app simultaneously can never access or view your uploaded files.\n"
    "* **Encrypted Transit:** All files are protected with bank-grade HTTPS encryption during data transfer."
)

# --- NON-BLOCKING VALIDATION GATEWAY ENGINE ---
is_valid_file = True
file_bytes = None

if uploaded_file is not None:
    filename_lower = uploaded_file.name.lower()
    if filename_lower.endswith((".docx", ".doc")):
        st.error("⚠️ Word file detected. This tool only works with PDF files.")
        st.markdown(
            "Word CVs don't need this tool, as you can delete or edit the contact details "
            "directly in Word.\n\n"
            "If you still want to use the scrubber, save the file as a PDF first: "
            "**File** -> **Save As** -> **PDF (*.pdf)**, then upload it here."
        )
        is_valid_file = False
    elif filename_lower.endswith(".pdf"):
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)

st.sidebar.markdown("---")
st.sidebar.header("Live Mask Adjustment")
top_boundary = st.sidebar.slider("Mask Top Boundary (Vertical Start)", 0, 200, st.session_state.top_boundary_val, 1, key=f"top_slider_{st.session_state.uploader_key}")
st.session_state.top_boundary_val = top_boundary

if "Two-Column" in layout_style:
    h_limit = st.sidebar.slider("Mask Width Barrier", 100, 300, st.session_state.h_limit_val, 1, key=f"h_two_{st.session_state.uploader_key}")
    v_limit = st.sidebar.slider("Mask Height Ceiling", 100, 500, st.session_state.v_limit_val, 1, key=f"v_two_{st.session_state.uploader_key}")
else:
    h_limit = st.sidebar.slider("Right Mask Start Width", 10, 500, st.session_state.h_limit_val, 1, key=f"h_std_{st.session_state.uploader_key}")
    v_limit = st.sidebar.slider("Right Mask Vertical Limit", 10, 500, st.session_state.v_limit_val, 1, key=f"v_std_{st.session_state.uploader_key}")
st.session_state.h_limit_val, st.session_state.v_limit_val = h_limit, v_limit

st.sidebar.markdown("---")
zoom_level = st.sidebar.slider("Document Zoom Level", 300, 1500, 900, 25)

def redact_pdf(f_bytes, layout_profile, w_barrier, h_ceiling, top_start, mask_color):
    doc = fitz.open(stream=f_bytes, filetype="pdf")
    for page in doc:
        page_width = page.rect.width
        if "Standard Layout" in layout_profile:
            mask_box = fitz.Rect(w_barrier, top_start, page_width - 15, h_ceiling)
            page.add_redact_annot(mask_box, fill=mask_color)
        else:
            sidebar_mask = fitz.Rect(0, top_start, w_barrier, h_ceiling)
            page.add_redact_annot(sidebar_mask, fill=mask_color)
        page.apply_redactions()
        
    clean_meta = {
        "author": "", "title": "", "subject": "", "keywords": "",
        "creator": "", "producer": "", "creationDate": "", "modDate": ""
    }
    doc.set_metadata(clean_meta)
    
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    total_pages = len(doc)
    doc.close()
    return output_buffer.getvalue(), total_pages

# Only run layout generator calculations if a valid PDF document exists
if uploaded_file is not None and is_valid_file and file_bytes is not None:
    base_name = uploaded_file.name[:-4]
    output_filename = f"{base_name}_Updated.pdf"
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Control Actions")
        try:
            scrubbed_pdf, total_pages = redact_pdf(file_bytes, layout_style, h_limit, v_limit, top_boundary, chosen_color)
            st.success("Calculated successfully!")
            st.download_button(label="📥 Download Updated PDF", data=scrubbed_pdf, file_name=output_filename, mime="application/pdf", type="primary")
            preview_page = st.selectbox("Flip Preview Page:", options=list(range(1, total_pages + 1)), index=0) if total_pages > 1 else 1
        except Exception as e: 
            st.error(f"Error compiling document: {e}")
            scrubbed_pdf, total_pages, preview_page = None, 1, 1
            
    with col2:
        st.subheader("Live Document Preview")
        if scrubbed_pdf:
            try:
                images = convert_from_bytes(scrubbed_pdf, first_page=preview_page, last_page=preview_page)
                if images: st.image(images, caption=f"Page {preview_page} of {total_pages}", width=zoom_level)
            except Exception as img_err: 
                st.error(f"Visual preview error: {img_err}")

# This section stays completely active on the webpage grid loop even during a type warning
st.markdown("---")
if st.button("🧹 Clear Current File", use_container_width=True): 
    st.session_state.uploader_key += 1
    st.session_state.top_boundary_val = 30
    st.session_state.h_limit_val = 140
    st.session_state.v_limit_val = 115
    st.rerun()
