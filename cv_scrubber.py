import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to completely erase contact info and section headers smoothly.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def redact_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    # Precise contact data patterns
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
    linkedin_pattern = r'(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9_/\-]+'
    linkedin_remnant_pattern = r'/in/[a-zA-Z0-9_\-]+/?'
    general_url_pattern = r'(https?://\S+|www\.\S+)'
    
    # Combined data regex
    master_regex = re.compile(f"({email_pattern})|({linkedin_pattern})|({linkedin_remnant_pattern})|({phone_pattern})|({general_url_pattern})")
    
    # Specific headers to look for and wipe out completely (case-insensitive)
    headers_to_erase = [
        "contact", "contact details", "contact info", "contact information",
        "phone", "mobile", "telephone", "email", "e-mail", "linkedin", "socials",
        "links", "websites"
    ]
    
    redactions_found = 0
    
    for page in doc:
        page_text = page.get_text()
        unique_matches = set()
        
        # 1. Gather all regex matches for the raw details
        for match in master_regex.finditer(page_text):
            unique_matches.add(match.group(0).strip())
            
        # 2. Gather specific layout section headers
        for header in headers_to_erase:
            # Use regex boundaries to find exact word/phrase matches
            header_regex = re.compile(rf"\b{header}\b", re.IGNORECASE)
            for match in header_regex.finditer(page_text):
                unique_matches.add(match.group(0).strip())
                
        # 3. Apply White-Out Redactions
        for text_to_hide in unique_matches:
            if len(text_to_hide) >= 2:
                rect_list = page.search_for(text_to_hide)
                for rect in rect_list:
                    # fill=(1, 1, 1) creates a pure white box over the text layout
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    redactions_found += 1
                    
        # Secondary targeted pass for the lingering username path structure
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                page.add_redact_annot(rect, fill=(1, 1, 1))
                redactions_found += 1
                
        # Permanently purge the text layer data and apply the visual white mask
        page.apply_redactions()
    
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_found

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Erasing layout segments invisibly..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes)
                
                if count == 0:
                    st.warning("No contact fragments or standard headings detected.")
                else:
                    st.success("Successfully whited out contact structures!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
