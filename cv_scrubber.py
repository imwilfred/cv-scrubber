import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to cleanly erase contact layers with adjustable padding controls.")

# --- Interactive Sidebar Sliders ---
st.sidebar.header("Custom Redaction Padding")
st.sidebar.write("Adjust these sliders if you see leftover icons or sliced shapes.")

left_pad = st.sidebar.slider("Left Extension (To cover icons)", min_value=0, max_value=120, value=65, step=5)
right_pad = st.sidebar.slider("Right Extension", min_value=0, max_value=30, value=5, step=1)
vertical_pad = st.sidebar.slider("Vertical Height Extension", min_value=0, max_value=30, value=12, step=1)

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def should_scrub_text(text):
    """Returns True if the text segment contains contact data or specific labels."""
    text_lower = text.lower().strip()
    
    # Core data patterns
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    has_location = bool(re.search(r'\b(singapore|asia|malaysia|usa|uk|london|new york)\b', text_lower))
    
    if has_email or has_phone or has_linkedin or has_generic_url or has_location:
        return True
        
    # Match standalone labels
    clean_word = re.sub(r'[^a-z]', '', text_lower).strip()
    contact_labels = {"mobile", "phone", "email", "linkedin", "socials", "links", "website", "contact", "location", "address"}
    
    if clean_word in contact_labels:
        return True
        
    return False

def redact_pdf(file_bytes, l_ext, r_ext, v_ext):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        page_dict = page.get_text("dict")
        
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            span_text = span["text"]
                            
                            if should_scrub_text(span_text):
                                rect = fitz.Rect(span["bbox"])
                                
                                # Apply the dynamic values directly from the web sliders
                                safe_rect = fitz.Rect(
                                    rect.x0 - l_ext, 
                                    rect.y0 - v_ext, 
                                    rect.x1 + r_ext, 
                                    rect.y1 + v_ext
                                )
                                
                                page.add_redact_annot(safe_rect, fill=(1, 1, 1))
                                redactions_applied += 1
                                
        # Fallback pass for layout text remnants
        page_text = page.get_text()
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                safe_slug_rect = fitz.Rect(rect.x0 - l_ext, rect.y0 - v_ext, rect.x1 + r_ext, rect.y1 + v_ext)
                page.add_redact_annot(safe_slug_rect, fill=(1, 1, 1))
                redactions_applied += 1
                
        # Permanently execute redactions
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_applied

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Processing custom layout rules..."):
            try:
                # Pass your custom slider variables into the function
                scrubbed_pdf, count = redact_pdf(file_bytes, left_pad, right_pad, vertical_pad)
                
                if count == 0:
                    st.warning("No contact elements matched the active layout criteria.")
                else:
                    st.success(f"Successfully processed! Adjusted boxes with {left_pad}px left margin.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
