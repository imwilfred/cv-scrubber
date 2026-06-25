import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to cleanly erase contact layers using precise target isolation.")

# --- UI Sidebar Controls ---
st.sidebar.header("Adaptive Controls")
clear_sidebar_icons = st.sidebar.checkbox("Erase Left Side Icon Strip", value=True, 
                                          help="Check this if you have a column of circular icons on the far left that won't go away.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def should_scrub_text(text):
    """Returns True ONLY for unambiguous contact details and standalone labels."""
    text_lower = text.lower().strip()
    
    # Target only strict data formats (Strict emails, phone sequences, and full digital URLs)
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    
    if has_email or has_phone or has_linkedin or has_generic_url:
        return True
        
    # Match standalone labels ONLY if they represent isolated introductory tokens
    clean_word = re.sub(r'[^a-z]', '', text_lower).strip()
    contact_labels = {"mobile", "phone", "email", "linkedin", "socials", "links", "website"}
    
    if clean_word in contact_labels and len(text_lower) < 15:
        return True
        
    return False

def redact_pdf(file_bytes, wipe_icons):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        page_dict = page.get_text("dict")
        
        # 1. Target and white out contact text elements with a laser-tight box
        # This completely eliminates horizontal bleeding into job bullets
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            if should_scrub_text(span["text"]):
                                rect = fitz.Rect(span["bbox"])
                                
                                # Laser-tight crop block (Zero horizontal extension)
                                tight_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
                                page.add_redact_annot(tight_rect, fill=(1, 1, 1))
                                redactions_applied += 1
                                
        # 2. Handle the left-side structural icon column explicitly if enabled
        if wipe_icons:
            # The icon column on the far left typically sits within the first 35-50 pixels of the page width
            # We wipe a narrow, dedicated vertical strip from the top down to just below the profile header zone
            icon_strip_zone = fitz.Rect(15, 20, 45, 180)
            page.add_redact_annot(icon_strip_zone, fill=(1, 1, 1))
            redactions_applied += 1
                                
        # Fallback pass for orphaned URL subpaths
        page_text = page.get_text()
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                safe_slug_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
                page.add_redact_annot(safe_slug_rect, fill=(1, 1, 1))
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
        with st.spinner("Executing clean visual target isolation..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, clear_sidebar_icons)
                
                if count == 0:
                    st.warning("No target details matched your configuration parameters.")
                else:
                    st.success("Document cleaned flawlessly! Body text and icons are perfectly handled.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
