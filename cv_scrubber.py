import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload any PDF resume format to cleanly erase contact data, labels, and icons instantly.")

# --- Layout Selector Sidebar ---
st.sidebar.header("Layout Profile Selector")
layout_style = st.sidebar.selectbox(
    "Select your CV's layout style:",
    options=[
        "Standard Layout (Right-aligned Contact Text / No Sidebar Icons)",
        "Two-Column Sidebar Layout (Vertical Stacked Icons on Left)"
    ],
    help="Select 'Standard Layout' for plain horizontal headers. Select 'Two-Column Sidebar Layout' if you have a column of circular icons on the far left."
)

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def core_contact_check(text):
    """Returns True ONLY for unmistakable contact data streams."""
    text_lower = text.lower().strip()
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower or "com/in" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    
    return has_email or has_phone or has_linkedin or has_generic_url

def redact_pdf(file_bytes, layout_profile):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        page_dict = page.get_text("dict")
        page_width = page.rect.width
        
        # Pass 1: Find the exact locations of the contact elements
        contact_rects = []
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            if core_contact_check(span["text"]):
                                contact_rects.append(fitz.Rect(span["bbox"]))
                                
        # --- PASS 2: EXECUTE DYNAMIC, HOODED REDACTION MASKS ---
        if "Standard Layout" in layout_profile:
            # Locate the exact vertical lines where the contact items are sitting
            if contact_rects:
                for r in contact_rects:
                    # Draw a box only around the exact height of the contact row on the right side
                    # Starts safely past your name (x=300) and extends to the page edge
                    row_mask = fitz.Rect(300, r.y0 - 2, page_width - 10, r.y1 + 2)
                    page.add_redact_annot(row_mask, fill=(1, 1, 1))
                    redactions_applied += 1
            else:
                # Absolute fallback safety box if strings are corrupted (covers the far upper right text area only)
                fallback_mask = fitz.Rect(350, 45, page_width - 10, 80)
                page.add_redact_annot(fallback_mask, fill=(1, 1, 1))
                redactions_applied += 1
                
        else:
            # Two-Column Sidebar Layout Profile
            if contact_rects:
                # Find the boundaries of the contact information column on the left side
                min_y = min([r.y0 for r in contact_rects]) - 5
                max_y = max([r.y1 for r in contact_rects]) + 15
                
                # Keep the sidebar box narrow (x=10 to x=185) so it never touches the main body column text
                sidebar_mask = fitz.Rect(10, min_y, 185, max_y)
                page.add_redact_annot(sidebar_mask, fill=(1, 1, 1))
                
                # Drop an extra narrow track mask to wipe out the vertical circular icons cleanly
                icon_track = fitz.Rect(10, min_y - 20, 45, max_y)
                page.add_redact_annot(icon_track, fill=(1, 1, 1))
                redactions_applied += 2
            else:
                # Hard fallback for the left column layout structure if text parsing is heavily segmented
                left_fallback = fitz.Rect(10, 85, 180, 220)
                page.add_redact_annot(left_fallback, fill=(1, 1, 1))
                redactions_applied += 1

        # Commit redactions permanently onto the current page layout
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_applied

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Executing layout-isolated masking pipeline..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, layout_style)
                
                if count == 0:
                    st.warning("No target details matched your active layout profile.")
                else:
                    st.success("Document scrubbed cleanly! Layout integrity preserved.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
