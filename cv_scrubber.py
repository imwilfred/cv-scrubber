import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to cleanly erase contact zones using absolute layout coordinate isolation.")

# --- UI Sidebar Controls ---
st.sidebar.header("Resume Template Selector")
template_type = st.sidebar.selectbox(
    "Choose Resume Layout",
    options=["Two-Column Sidebar Layout (Sabrina)", "Single Column / Standard Horizontal Layout"],
    help="Select the Two-Column layout to cleanly wipe out the dedicated contact block zone on the upper left."
)

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def should_scrub_text_standard(text):
    """Fallback text scraper for standard horizontal layouts."""
    text_lower = text.lower().strip()
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    
    if has_email or has_phone or has_linkedin or has_generic_url:
        return True
    return False

def redact_pdf(file_bytes, layout_style):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        if "Two-Column" in layout_style:
            # OPTION 1: Two-Column Sidebar Layout
            # We draw a single, precise white box over the entire upper-left contact area.
            # This zone starts from the left edge (x=15) to just before the profile text (x=195),
            # and vertically covers from below the green banner (y=85) down to just above Education (y=210).
            # This wipes out "CONTACT", the icons, details, and location instantly without touching body text.
            contact_zone_rect = fitz.Rect(15, 85, 195, 210)
            page.add_redact_annot(contact_zone_rect, fill=(1, 1, 1))
            redactions_applied += 1
            
        else:
            # OPTION 2: Standard Horizontal Layout (Fallback Laser-tight text matching)
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                if should_scrub_text_standard(span["text"]):
                                    rect = fitz.Rect(span["bbox"])
                                    tight_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
                                    page.add_redact_annot(tight_rect, fill=(1, 1, 1))
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
        with st.spinner("Executing layout-isolated coordinate cleanup..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, template_type)
                
                if count == 0:
                    st.warning("No areas matched the active configuration rules.")
                else:
                    st.success("Document scrubbed cleanly! Layout boundaries preserved perfectly.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
