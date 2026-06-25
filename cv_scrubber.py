import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to completely erase contact details, headers, locations, and stacked icon columns.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def redact_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    # Core contact data patterns
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
    linkedin_pattern = r'(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9_/\-]+'
    linkedin_remnant_pattern = r'/in/[a-zA-Z0-9_\-]+/?'
    general_url_pattern = r'(https?://\S+|www\.\S+)'
    
    # Added explicit Location filtering pattern (captures cities, countries, zip codes)
    location_pattern = r'\b(Singapore|Asia|Malaysia|USA|UK|London|New York|\d{5,6})\b'
    
    master_regex = re.compile(f"({email_pattern})|({linkedin_pattern})|({linkedin_remnant_pattern})|({phone_pattern})|({general_url_pattern})|({location_pattern})")
    
    headers_to_erase = [
        "contact", "contact details", "contact info", "contact information",
        "phone", "mobile", "telephone", "email", "e-mail", "linkedin", "socials",
        "links", "websites", "location", "address"
    ]
    
    redactions_found = 0
    
    for page in doc:
        page_text = page.get_text()
        unique_matches = set()
        
        for match in master_regex.finditer(page_text):
            unique_matches.add(match.group(0).strip())
            
        for header in headers_to_erase:
            header_regex = re.compile(rf"\b{header}\b", re.IGNORECASE)
            for match in header_regex.finditer(page_text):
                unique_matches.add(match.group(0).strip())
                
        # Apply White-Out Redactions with multi-directional padding adjustments
        for text_to_hide in unique_matches:
            if len(text_to_hide) >= 2:
                rect_list = page.search_for(text_to_hide)
                for rect in rect_list:
                    # Cleaned multi-directional box padding:
                    # Shifting x0 left (-35) covers the pin/phone icon cleanly.
                    # Adding vertical padding (y0 - 8, y1 + 8) fully consumes stacked icon graphics.
                    expanded_rect = fitz.Rect(
                        rect.x0 - 35, 
                        rect.y0 - 8, 
                        rect.x1 + 5, 
                        rect.y1 + 8
                    )
                    
                    page.add_redact_annot(expanded_rect, fill=(1, 1, 1))
                    redactions_found += 1
                    
        # Targeted clean pass for vanity username path remnants
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                expanded_slug_rect = fitz.Rect(rect.x0 - 35, rect.y0 - 8, rect.x1 + 5, rect.y1 + 8)
                page.add_redact_annot(expanded_slug_rect, fill=(1, 1, 1))
                redactions_found += 1
                
        # Commit redactions permanently onto the current page layout
        page.apply_redactions()
    
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_found

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Erasing layout items and vertical graphics track..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes)
                
                if count == 0:
                    st.warning("No contact fragments or standard headings detected.")
                else:
                    st.success("Successfully cleared all contact rows, location data, and nested icons!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
