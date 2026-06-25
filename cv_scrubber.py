import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to cleanly erase contact sections without damaging text or layout.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def redact_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    # Strict contact data patterns (No loose words like 'Singapore' or 'Asia')
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
    linkedin_pattern = r'(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9_/\-]+'
    linkedin_remnant_pattern = r'/in/[a-zA-Z0-9_\-]+/?'
    general_url_pattern = r'(https?://\S+|www\.\S+)'
    
    master_regex = re.compile(f"({email_pattern})|({linkedin_pattern})|({linkedin_remnant_pattern})|({phone_pattern})|({general_url_pattern})")
    
    # Strict headers to erase only when standing completely alone
    headers_to_erase = [
        "contact", "contact details", "contact info", "contact information",
        "socials", "links", "websites"
    ]
    
    redactions_found = 0
    
    for page in doc:
        page_text = page.get_text()
        unique_matches = set()
        
        # 1. Find direct contact info
        for match in master_regex.finditer(page_text):
            unique_matches.add(match.group(0).strip())
            
        # 2. Find explicit standalone contact headers
        for header in headers_to_erase:
            header_regex = re.compile(rf"^\s*{header}\s*$", re.IGNORECASE | re.MULTILINE)
            for match in header_regex.finditer(page_text):
                unique_matches.add(match.group(0).strip())
                
        # 3. Apply safe, tight white-out boxes
        for text_to_hide in unique_matches:
            if len(text_to_hide) >= 2:
                rect_list = page.search_for(text_to_hide)
                for rect in rect_list:
                    # Tighter, safer horizontal and vertical padding
                    # Prevents bleeding into university names or student names nearby
                    safe_rect = fitz.Rect(
                        rect.x0 - 18, 
                        rect.y0 - 2, 
                        rect.x1 + 2, 
                        rect.y1 + 2
                    )
                    page.add_redact_annot(safe_rect, fill=(1, 1, 1))
                    redactions_found += 1
                    
        # 4. Fallback pass for layout text remnants
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                safe_slug_rect = fitz.Rect(rect.x0 - 18, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
                page.add_redact_annot(safe_slug_rect, fill=(1, 1, 1))
                redactions_found += 1
                
        # Permanently execute redactions
        page.apply_redactions()
    
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_found

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Processing clean layout extraction..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes)
                
                if count == 0:
                    st.warning("No core contact channels detected.")
                else:
                    st.success("Successfully cleaned contact data layers cleanly!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
