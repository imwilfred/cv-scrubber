import streamlit as st
import fitz  # PyMuPDF
import re
import io
from pdf2image import convert_from_bytes  # Handles the live layout preview generation

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc", layout="wide")

st.title("Interactive PDF CV Contact Scrubber")
st.write("Upload your resume and watch the redaction zones update on screen in real time before you download.")

# --- Interactive Sidebar Interface Controls ---
st.sidebar.header("Layout Settings")
layout_style = st.sidebar.selectbox(
    "Select your CV's layout style:",
    options=[
        "Standard Layout (Right-aligned Contact Text / No Sidebar Icons)",
        "Two-Column Sidebar Layout (Vertical Stacked Icons on Left)"
    ]
)

st.sidebar.markdown("---")
st.sidebar.header("Live Mask Adjustment")

# These sliders let you visually expand or shrink the masks with immediate screen updates
if "Two-Column" in layout_style:
    h_limit = st.sidebar.slider("Mask Width Barrier", min_value=100, max_value=300, value=220, step=5,
                                help="Adjust horizontally to frame 'PROFILE' or 'EXPERIENCE' perfectly.")
    v_limit = st.sidebar.slider("Mask Height Ceiling", min_value=100, max_value=500, value=260, step=5,
                                help="Slide up or down to cover contact details without touching Awards or Skills.")
else:
    # Safe horizontal boundary adjustments for the standard horizontal quadrant block
    h_limit = st.sidebar.slider("Right Mask Start Width", min_value=200, max_value=450, value=320, step=5,
                                help="Move left or right to align cleanly next to your name column.")
    v_limit = st.sidebar.slider("Right Mask Vertical Limit", min_value=50, max_value=250, value=110, step=5,
                                help="Move up or down to cover details without overlapping lower sections.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def redact_pdf(file_bytes, layout_profile, width_barrier, height_ceiling):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    for page in doc:
        page_text = page.get_text()
        page_dict = page.get_text("dict")
        page_width = page.rect.width
        
        if "Standard Layout" in layout_profile:
            # --- STRATEGY 1: INTERACTIVE RIGHT QUADRANT MASK ---
            # Targets the region based directly on your live sidebar slider adjustments
            right_mask = fitz.Rect(width_barrier, 48, page_width - 15, height_ceiling)
            page.add_redact_annot(right_mask, fill=(1, 1, 1))
            
            # Substring cleanup remains operational behind the scenes for localized safety
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
            # --- STRATEGY 2: INTERACTIVE CEILING-LOCKED SIDEBAR MASK ---
            # Automatically senses the main body text starting anchor line
            main_column_left = width_barrier
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                txt = span["text"].upper().strip()
                                if txt in ["PROFILE", "PROFESSIONAL EXPERIENCE", "EXPERIENCE"]:
                                    # Fallback option if slider value is left at default layout settings
                                    if width_barrier == 220:
                                        main_column_left = span["bbox"]
                                    break
            
            # Apply redactions strictly inside the container block coordinates restricted by your sliders
            for block in page_dict.get("blocks", []):
                bx0, by0, bx1, by1 = block["bbox"]
                if bx1 < main_column_left and 70 < by0 < height_ceiling:
                    sidebar_mask = fitz.Rect(0, by0 - 4, main_column_left - 10, min(by1 + 4, height_ceiling))
                    page.add_redact_annot(sidebar_mask, fill=(1, 1, 1))
                    
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    return output_buffer.getvalue()

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    # Split the screen into two clean columns: Sliders on Left, Interactive Preview on Right
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Control Actions")
        # Real-time document process trigger linked to the slider state matrices
        try:
            scrubbed_pdf = redact_pdf(file_bytes, layout_style, h_limit, v_limit)
            st.success("Layout masks calculated successfully! Check preview on the right.")
            
            st.download_button(
                label="?? Download Redacted PDF",
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
                # Convert the modified memory buffer into a rendering display picture instantly
                images = convert_from_bytes(scrubbed_pdf, first_page=1, last_page=1)
                if images:
                    st.image(images[0], caption="First Page Visual Map Preview (Adjust sliders to reposition white-out masks)", use_container_width=True)
            except Exception as img_err:
                st.info("Visual preview rendering engine requires poppler to be installed on your terminal ecosystem.")
