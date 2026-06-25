import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to cleanly erase contact layers based on your document's layout style.")

# --- UI Layout Controls ---
st.sidebar.header("Layout Settings")
scrub_mode = st.sidebar.selectbox(
    "Select CV Layout Style",
    options=["Precision Mode (Name on same line)", "Column Mode (Stacked icons/Vertical block)"],
    help="Choose Precision Mode if your name is right next to your email/phone. Choose Column Mode if contact info is in a separate sidebar or block."
)

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def should_scrub_text(text):
    """Returns True if the text segment contains contact data or specific labels."""
    text_lower = text.lower().strip()
    
    # Core data patterns
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    
    # Catch location keywords explicitly for the vertical stack layout
    has_location = bool(re.search(r'\b(singapore|asia|malaysia|usa|uk|london|new york)\b', text_lower))
    
    if has_email or has_phone or has_linkedin or has_generic_url or has_location:
        return True
        
    # Match standalone labels
    clean_word = re.sub(r'[^a-z]', '', text_lower).strip()
    contact_labels = {"mobile", "phone", "email", "linkedin", "socials", "links", "website", "contact", "location", "address"}
    
    if clean_word in contact_labels:
        return True
        
    return False

def redact_pdf(file_bytes, mode):
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
                                
                                # Apply adaptive padding dimensions based on user-selected layout mode
                                if "Precision Mode" in mode:
                                    # Ultra-safe padding configuration for tight horizontal text lines
                                    safe_rect = fitz.Rect(
                                        rect.x0 - 15, 
                                        rect.y0 - 1, 
                                        rect.x1 + 1, 
                                        rect.y1 + 1
                                    )
                                else:
                                    # Aggressive vertical and horizontal padding to consume whole stacked icon clusters cleanly
                                    safe_rect = fitz.Rect(
                                        rect.x0 - 45, 
                                        rect.y0 - 12, 
                                        rect.x1 + 5, 
                                        rect.y1 + 12
                                    )
                                
                                page.add_redact_annot(safe_rect, fill=(1, 1, 1))
                                redactions_applied += 1
                                
        # Fallback pass specifically targeting orphaned vanity path fragments (e.g. /sabrinalamjingwen/)
        page_text = page.get_text()
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                if "Precision Mode" in mode:
                    safe_slug_rect = fitz.Rect(rect.x0 - 15, rect.y0 - 1, rect.x1 + 1, rect.y1 + 1)
                else:
                    safe_slug_rect = fitz.Rect(rect.x0 - 45, rect.y0 - 12, rect.x1 + 5, rect.y1 + 12)
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
        with st.spinner("Processing selected layout rules..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, scrub_mode)
                
                if count == 0:
                    st.warning("No contact elements matched the active layout criteria.")
                else:
                    st.success(f"Successfully processed using {scrub_mode}!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
