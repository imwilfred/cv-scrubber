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
    
    # Powerful regex list targeting contact details across formatting boundaries
    patterns = [
        # Match standard email structures
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        
        # Match mobile/phone numbers with international codes, spaces, or brackets
        r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
        
        # Match LinkedIn URLs specifically (with or without http/www/slashes)
        r'(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?',
        
        # General backup URL rule for profiles (GitHub, portfolios)
        r'(https?://\S+|www\.\S+)'
    ]
    
    redactions_found = 0
    
    for page in doc:
        for pattern in patterns:
            # page.search_for allows flag=1 for full regex evaluation across bounding boxes
            matches = page.search_for(pattern, use_regex=True)
            
            for rect in matches:
                # Add a black redaction bar over the match coordinates
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
                
                # Render button cleanly without structural emojis
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="redacted_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
