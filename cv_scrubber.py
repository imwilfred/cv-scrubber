import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="??")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to instantly mask emails, phone numbers, and URLs with black bars.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def redact_pdf(file_bytes):
    # Open document from memory stream
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    # Precise regex patterns
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
    url_pattern = r'(https?://\S+|www\.\S+|[a-zA-Z0-9.-]+\.(com|org|net|edu|gov|io|co|me)\b)'
    
    combined_pattern = re.compile(f"({email_pattern})|({phone_pattern})|({url_pattern})")
    
    redactions_found = 0
    
    for page in doc:
        # Get individual text words with their precise box coordinates
        text_instances = page.get_text("words") 
        # text_instances structure: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        
        for inst in text_instances:
            word = inst[4]
            # Check if this specific word matches our criteria
            if combined_pattern.search(word):
                rect = fitz.Rect(inst[0], inst[1], inst[2], inst[3])
                # Add a black redaction annotation box
                page.add_redact_annot(rect, fill=(0, 0, 0))
                redactions_found += 1
                
        # Permanently apply the redactions on this page
        page.apply_redactions()
    
    # Save the cleaned PDF into a memory buffer
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_found

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Scrub PDF Document", type="primary"):
        with st.spinner("Processing document layout..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes)
                
                if count == 0:
                    st.warning("No matches found for emails, phone numbers, or standard URLs.")
                else:
                    st.success(f"Scrubbing Complete! Covered {count} sensitive items.")
                
                # Provide download button for the new PDF
                st.download_button(
                    label="?? Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="redacted_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not redact this specific PDF layout: {e}")
