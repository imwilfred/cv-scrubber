import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload any PDF resume format to cleanly erase contact data and icons while completely safeguarding your layout text.")

# --- Professional, Layout-Agnostic Sidebar Controls ---
st.sidebar.header("Layout Settings")
icon_alignment = st.sidebar.selectbox(
    "Where are the contact icons located?",
    options=[
        "No Sidebar Icons (Standard / Right-aligned Contact Info)",
        "Icons are directly to the LEFT of the contact text",
        "Icons are directly to the RIGHT of the contact text"
    ],
    help="Select 'No Sidebar Icons' for standard horizontal formats like your current uploaded view. Choose 'LEFT' for vertical stacked layouts with icons."
)

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def should_scrub_text(text):
    """Returns True ONLY for strict contact details and direct labels, preventing false positives."""
    text_lower = text.lower().strip()
    
    # Precise regex checks for actual data formats (no loose geographical keywords)
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    
    if has_email or has_phone or has_linkedin or has_generic_url:
        return True
        
    # Match standalone labels only if they act as small introductory tags
    clean_word = re.sub(r'[^a-z]', '', text_lower).strip()
    contact_labels = {"mobile", "phone", "email", "linkedin", "socials", "links", "website", "contact"}
    
    if clean_word in contact_labels and len(text_lower) < 15:
        return True
        
    return False

def redact_pdf(file_bytes, icon_style):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        # Extract the deep word span objects with their native, pinpoint coordinates
        page_dict = page.get_text("dict")
        
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            if should_scrub_text(span["text"]):
                                rect = fitz.Rect(span["bbox"])
                                
                                # Dynamic box padding calculation based on your selected icon orientation
                                if "LEFT" in icon_style:
                                    # Extends to the left to swallow the sidebar icons smoothly
                                    safe_rect = fitz.Rect(rect.x0 - 55, rect.y0 - 6, rect.x1 + 2, rect.y1 + 6)
                                elif "RIGHT" in icon_style:
                                    # Extends to the right if icons follow the text
                                    safe_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 6, rect.x1 + 55, rect.y1 + 6)
                                else:
                                    # Standard / No Sidebar Icons: Laser-focused mask to protect nearby university/name lines
                                    safe_rect = fitz.Rect(rect.x0 - 4, rect.y0 - 1, rect.x1 + 4, rect.y1 + 1)
                                
                                # Cover with an invisible white mask
                                page.add_redact_annot(safe_rect, fill=(1, 1, 1))
                                redactions_applied += 1
                                
        # Fallback pass for layout text remnants or subpaths
        page_text = page.get_text()
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                if "LEFT" in icon_style:
                    safe_slug_rect = fitz.Rect(rect.x0 - 55, rect.y0 - 6, rect.x1 + 2, rect.y1 + 6)
                elif "RIGHT" in icon_style:
                    safe_slug_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 6, rect.x1 + 55, rect.y1 + 6)
                else:
                    safe_slug_rect = fitz.Rect(rect.x0 - 4, rect.y0 - 1, rect.x1 + 4, rect.y1 + 1)
                page.add_redact_annot(safe_slug_rect, fill=(1, 1, 1))
                redactions_applied += 1
                
        # Permanently apply the redactions on the current page layout
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_applied

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Executing layout-isolated cleanup..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, icon_alignment)
                
                if count == 0:
                    st.warning("No target details matched your active layout configuration parameters.")
                else:
                    st.success("Successfully cleaned contact data layers seamlessly!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
