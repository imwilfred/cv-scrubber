import streamlit as st
import fitz  # PyMuPDF
import re
import io
from pdf2image import convert_from_bytes

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc", layout="wide")

st.title("Interactive PDF CV Contact Scrubber")
st.write("Upload your resume and use Auto-Tune or manual sliders to frame your layout perfectly.")

# Initialize session state variables to track slider overrides dynamically
if "top_boundary_val" not in st.session_state: st.session_state.top_boundary_val = 88
if "h_limit_val" not in st.session_state: st.session_state.h_limit_val = 220
if "v_limit_val" not in st.session_state: st.session_state.v_limit_val = 260
if "active_layout" not in st.session_state: st.session_state.active_layout = "Standard Layout (Right-aligned Contact Text / No Sidebar Icons)"

# --- Sidebar Controls ---
st.sidebar.header("Layout Settings")
layout_style = st.sidebar.selectbox(
    "Select your CV's layout style:",
    options=[
        "Standard Layout (Right-aligned Contact Text / No Sidebar Icons)",
        "Two-Column Sidebar Layout (Vertical Stacked Icons on Left)"
    ],
    key="layout_style_selection"
)

# Reset defaults cleanly if user manually switches layout formats in dropdown
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

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def core_contact_check(text):
    text_lower = text.lower().strip()
    return (bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)) or
            bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text)) or
            "linkedin.com" in text_lower or "/in/" in text_lower or "com/in" in text_lower or
            "www." in text_lower or "http" in text_lower)

# --- AUTO-TUNE LOGIC BUTTON ---
if uploaded_file is not None:
    if st.sidebar.button("🔮 Auto-Tune to Fit Layout", type="primary", use_container_width=True):
        try:
            # Read bytes non-destructively to parse alignment matrices
            doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
            first_page = doc[0]
            page_dict = first_page.get_text("dict")
            page_width = first_page.rect.width
            
            contact_boxes = []
            profile_x0 = None
            
            # Map where contact anchors and main headers live
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                txt = span["text"].upper().strip()
                                if core_contact_check(span["text"]):
                                    contact_boxes.append(fitz.Rect(span["bbox"]))
                                if txt in ["PROFILE", "PROFESSIONAL EXPERIENCE", "EXPERIENCE"]:
                                    profile_x0 = span["bbox"][0]

            if "Two-Column" in layout_style:
                # Two-Column Tuning Parameters
                st.session_state.top_boundary_val = 85
                st.session_state.h_limit_val = int(profile_x0) if profile_x0 else 220
                if contact_boxes:
                    st.session_state.v_limit_val = int(max([r.y1 for r in contact_boxes])) + 15
                else:
                    st.session_state.v_limit_val = 260
            else:
                # Standard Layout Tuning Parameters
                st.session_state.top_boundary_val = 32
                if contact_boxes:
                    # Dynamically set width barrier right before the leftmost contact string element starts
                    st.session_state.h_limit_val = int(min([r.x0 for r in contact_boxes])) - 15
                    st.session_state.v_limit_val = int(max([r.y1 for r in contact_boxes])) + 5
                else:
                    st.session_state.h_limit_val = 310
                    st.session_state.v_limit_val = 115
                    
            doc.close()
            st.sidebar.success("Auto-tuned successfully! Look at preview.")
        except Exception as tune_err:
            st.sidebar.error(f"Auto-tune parsing failed: {tune_err}")

# --- Render Sliders Linked to Session State Management Matrix ---
st.sidebar.markdown("---")
st.sidebar.header("Live Mask Adjustment")

top_boundary = st.sidebar.slider(
    "Mask Top Boundary (Vertical Start)", min_value=0, max_value=200, 
    value=st.session_state.top_boundary_val, step=1, key="top_slider"
)
st.session_state.top_boundary_val = top_boundary

if "Two-Column" in layout_style:
    h_limit = st.sidebar.slider(
        "Mask Width Barrier", min_value=100, max_value=300, 
        value=st.session_state.h_limit_val, step=5, key="h_slider_two"
    )
    v_limit = st.sidebar.slider(
        "Mask Height Ceiling", min_value=100, max_value=500, 
        value=st.session_state.v_limit_val, step=5, key="v_slider_two"
    )
else:
    h_limit = st.sidebar.slider(
        "Right Mask Start Width", min_value=200, max_value=450, 
        value=st.session_state.h_limit_val, step=5, key="h_slider_std"
    )
    v_limit = st.sidebar.slider(
        "Right Mask Vertical Limit", min_value=50, max_value=250, 
        value=st.session_state.v_limit_val, step=5, key="v_slider_std"
    )

st.session_state.h_limit_val = h_limit
st.session_state.v_limit_val = v_limit

# --- Processing Pipeline Functions ---
def redact_pdf(file_bytes, layout_profile, width_barrier, height_ceiling, top_start):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        page_text = page.get_text()
        page_dict = page.get_text("dict")
        page_width = page.rect.width
        
        if "Standard Layout" in layout_profile:
            right_mask = fitz.Rect(width_barrier, top_start, page_width - 15, height_ceiling)
            page.add_redact_annot(right_mask, fill=(1, 1, 1))
            
            targets = set()
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_text)
            for e in emails: targets.add(e.strip())
            phones = re.findall(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', page_text)
            for p in phones: 
                if len(p.strip()) > 6: targets.add(p.strip())
                
            for target in targets:
                rect_list = page.search_for(target)
                for rect in rect_list:
                    tight_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 1, rect.x1 + 2, rect.y1 + 1)
                    page.add_redact_annot(tight_rect, fill=(1, 1, 1))
        else:
            main_column_left = float(width_barrier)
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                txt = span["text"].upper().strip()
                                if txt in ["PROFILE", "PROFESSIONAL EXPERIENCE", "EXPERIENCE"]:
                                    if width_barrier == 220:
                                        main_column_left = float(span["bbox"][0])
                                    break
            
            for block in page_dict.get("blocks", []):
                bx0, by0, bx1, by1 = block["bbox"]
                if bx1 < main_column_left and top_start < by0 < height_ceiling:
                    sidebar_mask = fitz.Rect(0, max(by0 - 4, top_start), main_column_left - 10, min(by1 + 4, height_ceiling))
                    page.add_redact_annot(sidebar_mask, fill=(1, 1, 1))
                    
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    return output_buffer.getvalue()

# --- Page Layout Rendering Matrix ---
if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Control Actions")
        try:
            scrubbed_pdf = redact_pdf(file_bytes, layout_style, h_limit, v_limit, top_boundary)
            st.success("Layout masks calculated successfully! Check preview on the right.")
            
            st.download_button(
                label="📥 Download Redacted PDF",
                data=scrubbed_pdf,
                file_name="cleaned_resume.pdf",
                mime="application/pdf",
                type="primary"
            )
        except Exception as e:
            st.error(f"Error compiling document matrix layout: {e}")
            scrubbed_pdf = None

    with col2:
        st.subheader("Live Document Preview")
        if scrubbed_pdf:
            try:
                images = convert_from_bytes(scrubbed_pdf, first_page=1, last_page=1)
                if images:
                    st.image(images, caption="Live Layout Map Preview", use_container_width=True)
            except Exception as img_err:
                st.info("Visual preview rendering engine configuration error.")
