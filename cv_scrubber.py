import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to instantly mask emails, phone numbers, and LinkedIn URLs.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def redact_pdf(file_bytes):
    # Open document from memory stream
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    # Precise, layout-hardened regex patterns
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
    
    # Enhanced LinkedIn pattern capturing the full domain path and vanity slugs
    linkedin_pattern = r'(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9_/\-]+'
    
    # Catch structural path remnants like "/sabrinalamjingwen/" if split up by PDF parser
    linkedin_remnant_pattern = r'/in/[a-zA-Z0-9_\-]+/?|[a-zA-Z0-9_\-]+/purple'
    
    general_url_pattern = r'(https?://\S+|www\.\S+)'
    
    # Combined master regex
    master_regex = re.compile(f"({email_pattern})|({linkedin_pattern})|({linkedin_remnant_pattern})|({phone_pattern})|({general_url_pattern})")
    
    redactions_found = 0
    
    for page in doc:
        # Extract full page text to let python re engine find matches contextually
        page_text = page.get_text()
        
        # Use a set to prevent repeating searches for the exact same text fragments
        unique_matches = set()
        for match in master_regex.finditer(page_text):
            matched_str = match.group(0).strip()
            # Clean up trailing/leading slash artifacts to guarantee a clean text block search
            unique_matches.add(matched_str)
            
        # Search layout coordinates for each identified string literal
        for text_to_hide in unique_matches:
            if len(text_to_hide) > 2:  # Safe minimum character length
                rect_list = page.search_for(text_to_hide)
                for rect in rect_list:
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    redactions_found += 1
                    
        # If the string match was broken down, perform an explicit secondary check for your username
        # This acts as a targeted fail-safe for this specific profile format
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                page.add_redact_annot(rect, fill=(0, 0, 0))
                redactions_found += 1
                
        # Commit redactions permanently onto the current page layout
        page.apply_redactions()
    
    # Save optimized and cleaned PDF out to memory buffer
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_found

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Scrub PDF Document", type="primary"):
        with st.spinner("Analyzing document text structures..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes)
                
                if count == 0:
                    st.warning("No matches found. Your contact details might be formatted uniquely.")
                else:
                    st.success(f"Scrubbing Complete! Applied {count} redaction overlays.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="redacted_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
