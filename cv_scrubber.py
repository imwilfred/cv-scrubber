import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to erase contact details and labels while completely preserving your name.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def should_scrub_text(text):
    """Returns True if the text segment contains contact data or specific labels."""
    text_lower = text.lower().strip()
    
    # 1. Regex checks for direct contact data
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    
    if has_email or has_phone or has_linkedin or has_generic_url:
        return True
        
    # 2. Match exact contact label triggers (case-insensitive)
    # Clean punctuation to catch "Mobile:", "Email:", "Phone -"
    clean_word = re.sub(r'[^a-z]', '', text_lower).strip()
    contact_labels = {"mobile", "phone", "email", "linkedin", "socials", "links", "website"}
    
    if clean_word in contact_labels:
        return True
        
    return False

def redact_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        # Extract deep layout structures down to the text span level
        page_dict = page.get_text("dict")
        
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            span_text = span["text"]
                            
                            # Check each specific text slice instead of the entire line
                            if should_scrub_text(span_text):
                                rect = fitz.Rect(span["bbox"])
                                
                                # Use minimal, tight padding so it never touches neighboring text/names
                                safe_rect = fitz.Rect(
                                    rect.x0 - 15,  # Slight left shift to catch standard inline icons
                                    rect.y0 - 1, 
                                    rect.x1 + 1, 
                                    rect.y1 + 1
                                )
                                
                                # Cover with pure white mask
                                page.add_redact_annot(safe_rect, fill=(1, 1, 1))
                                redactions_applied += 1
                                
        # Permanently execute the structural redactions on this page
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_applied

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Executing targeted text span cleaning..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes)
                
                if count == 0:
                    st.warning("No contact channels or inline labels were found.")
                else:
                    st.success("Successfully removed contact data while retaining your name layout!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
