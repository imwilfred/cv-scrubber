import streamlit as st
import fitz
import re
import io
from pdf2image import convert_from_bytes

st.set_page_config(
    page_title="PDF CV Scrubber", 
    page_icon="doc", 
    layout="wide"
)

st.title("Interactive PDF CV Contact Scrubber")
st.write("Upload your resume and use Auto-Tune or manual sliders.")

# --- Session States ---
if "top_boundary_val" not in st.session_state:
    st.session_state.top_boundary_val = 88
if "h_limit_val" not in st.session_state:
    st.session_state.h_limit_val = 220
if "v_limit_val" not in st.session_state:
    st.session_state.v_limit_val = 260
if "active_layout" not in st.session_state:
    st.session_state.active_layout = "Standard Layout"

# --- Sidebar ---
st.sidebar.header("Layout Settings")
layout_style = st.sidebar.selectbox(
    "Select your CV's layout style:",
    options=["Standard Layout", "Two-Column Sidebar Layout"],
    key="layout_style_selection"
)

if layout_style != st.session_state.active_layout:
    st.session_state.active_layout = layout_style
    if "Two-Column" in layout_style:
        st.session_state.top_boundary_val = 88
        st.session_state.h_limit_val = 220
        st.session_state.v_limit_val = 260
    else:
        st.session_state.top_boundary_val = 32
        st.session_state.h_limit_val = 310
        st.session_state.v_limit_val = 115

# --- File Uploader and Extension Warning Gate ---
uploaded_file = st.file_uploader(
    "Choose a PDF resume", 
    type=["pdf", "docx", "doc"]
)

if uploaded_file is not None:
    filename_lower = uploaded_file.name.lower()
    
    if filename_lower.endswith((".docx", ".doc")):
        st.error("⚠️ Invalid File Type Detected!")
        
        msg = "Our CV Scrubber can only process **PDF files**.\n\n"
        msg += "**How to convert your Word document:**\n"
        msg += "1. Open your document in Microsoft Word.\n"
        msg += "2. Click **File** -> **Save As** (or **Export**).\n"
        msg += "3. Select **PDF (*.pdf)** from the file format dropdown list.\n"
        msg += "4. Upload your new PDF file here."
        
        st.markdown(msg)
        st.stop()

def core_contact_check(text):
    text_lower = text.lower().strip()
    has_e = bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text))
    has_p = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}', text))
    has_l = "linkedin.com" in text_lower or "/in/" in text_lower
    has_w = "www." in text_lower or "http" in text_lower
    return has_e or has_p or has_l or has_w

# --- AUTO-TUNE LOGIC ---
if uploaded_file is not None:
    if st.sidebar.button("🔮 Auto-Tune to Fit Layout", type="primary"):
        try:
            doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
            first_page = doc
            page_dict = first_page.get_text("dict")
            
            contact_boxes = []
            profile_x0 = None
            
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                txt = span["text"].upper().strip()
                                if core_contact_check(span["text"]):
                                    contact_boxes.append(fitz.Rect(span["bbox"]))
                                if txt in ["PROFILE", "EXPERIENCE"]:
                                    profile_x0 = span["bbox"]

            if "Two-Column" in layout_style:
                st.session_state.top_boundary_val = 85
                st.session_state.h_limit_val = int(profile_x0) if profile_x0 else 220
                if contact_boxes:
                    st.session_state.v_limit_val = int(max([r.y1 for r in contact_boxes])) + 15
                else:
                    st.session_state.v_limit_val = 260
            else:
                st.session_state.top_boundary_val = 32
                if contact_boxes:
                    st.session_state.h_limit_val = int(min([r.x0 for r in contact_boxes])) - 15
                    st.session_state.v_limit_val = int(max([r.y1 for r in contact_boxes])) + 5
                else:
                    st.session_state.h_limit_val = 310
                    st.session_state.v_limit_val = 115
                    
            doc.close()
            st.sidebar.success("Auto-tuned successfully!")
        except Exception as tune_err:
            st.sidebar.error(f"Auto-tune failed: {tune_err}")

# --- Sliders Control Section ---
st.sidebar.markdown("---")
st.sidebar.header("Live Mask Adjustment")

top_boundary = st.sidebar.slider(
    "Mask Top Boundary", min_value=0, max_value=200, 
    value=st.session_state.top_boundary_val, step=1, key="top_slider"
)
st.session_state.top_boundary_val = top_boundary

if "Two-Column" in layout_style:
    h_limit = st.sidebar.slider(
        "Mask Width Barrier", min_value=100, max_value=300, 
        value=st.session_state.h_limit_val, step=1, key="h_slider_two"
    )
    v_limit = st.sidebar.slider(
        "Mask Height Ceiling", min_value=100, max_value=500, 
        value=st.session_state.v_limit_val, step=1, key="v_slider_two"
    )
else:
    h_limit = st.sidebar.slider(
        "Right Mask Start Width", min_value=200, max_value=450, 
        value=st.session_state.h_limit_val, step=1, key="h_slider_std"
    )
    v_limit = st.sidebar.slider(
        "Right Mask Vertical Limit", min_value=50, max_value=250, 
        value=st.session_state.v_limit_val, step=1, key="v_slider_std"
    )

st.session_state.h_limit_val = h_limit
st.session_state.v_limit_val = v_limit

st.sidebar.markdown("---")
st.sidebar.header("Preview Scale Settings")
zoom_level = st.sidebar.slider(
    "Document Zoom Level", min_value=300, max_value=1200, 
    value=750, step=25
)

# --- Core Redaction Engine Pipeline ---
def redact_pdf(file_bytes, layout_profile, w_barrier, h_ceiling, top_start):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    for page in doc:
        page_text = page.get_text()
        page_dict = page.get_text("dict")
        page_width = page.rect.width
        
        if "Standard Layout" in layout_profile:
            right_mask = fitz.Rect(w_barrier, top_start, page_width - 15, h_ceiling)
            page.add_redact_annot(right_mask, fill=(1, 1, 1))
            
            targets = set()
            emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_text)
            for e in emails: targets.add(e.strip())
            phones = re.findall(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}', page_text)
            for p in phones:
                if len(p.strip()) > 6: targets.add(p.strip())
                
            for target in targets:
                rect_list = page.search_for(target)
                for rect in rect_list:
                    tight_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 1, rect.x1 + 2, rect.y1 + 1)
                    page.add_redact_annot(tight_rect, fill=(1, 1, 1))
        else:
            main_column_left = float(w_barrier)
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                txt = span["text"].upper().strip()
                                if txt in ["PROFILE", "EXPERIENCE"]:
                                    if w_barrier == 220:
                                        main_column_left = float(span["bbox"])
                                    break
            
            for block in page_dict.get("blocks", []):
                bx0, by0, bx1, by1 = block["bbox"]
                if bx1 < main_column_left and top_start < by0 < h_ceiling:
                    sidebar_mask = fitz.Rect(0, max(by0 - 4, top_start), main_column_left - 10, min(by1 + 4, h_ceiling))
                    page.add_redact_annot(sidebar_mask, fill=(1, 1, 1))
                    
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    total_pages = len(doc)
    doc.close()
    return output_buffer.getvalue(), total_pages

# --- Layout Rendering UI ---
if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    original_name = uploaded_file.name
    
    if original_name.lower().endswith(".pdf"):
        base_name = original_name[:-4]
    else:
        base_name = original_name
    output_filename = f"{base_name}_Redacted.pdf"
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Control Actions")
        try:
            scrubbed_pdf, total_pages = redact_pdf(
                file_bytes, layout_style, h_limit, v_limit, top_boundary
            )
            st.success("Calculated successfully!")
            
            st.download_button(
                label="Download Redacted PDF",
                data=scrubbed_pdf,
                file_name=output_filename,
                mime="application/pdf",
                type="primary"
            )
            
            if total_pages > 1:
                st.markdown("---")
                preview_page = st.selectbox(
                    "Flip Preview Page:",
                    options=list(range(1, total_pages + 1)),
                    index=0
                )
            else:
                preview_page = 1
                
        except Exception as e:
            st.error(f"Error compiling document: {e}")
            scrubbed_pdf, total_pages, preview_page = None, 1, 1

     with col2:
        st.subheader("Live Document Preview")
        if scrubbed_pdf:
            try:
                images = convert_from_bytes(
                    scrubbed_pdf, 
                    first_page=preview_page, 
                    last_page=preview_page
                )
                if images:
                    st.image(
                        images[0], 
                        caption=f"Page {preview_page} of {total_pages}", 
                        use_container_width=False,
                        width=zoom_level
                    )
            except Exception as img_err:
                st.error(f"Visual preview rendering error: {img_err}")
