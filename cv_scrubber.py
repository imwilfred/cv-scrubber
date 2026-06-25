import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to cleanly wipe contact layout data while locking your text boundaries.")

# --- UI Sidebar Controls ---
st.sidebar.header("Adaptive Controls")
icon_clearance = st.sidebar.slider("Icon Strip Clearance Width", min_value=10, max_value=150, value=75, step=5,
                                  help="Increase this ONLY if sidebar icons are still partially showing.")

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def should_scrub_text(text):
    """Returns True if the text segment contains contact data or specific labels."""
    text_lower = text.lower().strip()
    
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    has_location = bool(re.search(r'\b(singapore|asia|malaysia|usa|uk|london|new york)\b', text_lower))
    
    if has_email or has_phone or has_linkedin or has_generic_url or has_location:
        return True
        
    clean_word = re.sub(r'[^a-z]', '', text_lower).strip()
    contact_labels = {"mobile", "phone", "email", "linkedin", "socials", "links", "website", "contact", "location", "address"}
    
    if clean_word in contact_labels:
        return True
        
    return False

def redact_pdf(file_bytes, icon_pad):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        page_dict = page.get_text("dict")
        page_width = page.rect.width
        
        # Define a safe boundary: usually contact sidebars live in the first 40% of the page width
        sidebar_threshold = page_width * 0.40 
        
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            span_text = span["text"]
                            
                            if should_scrub_text(span_text):
                                rect = fitz.Rect(span["bbox"])
                                
                                # CRITICAL CHECK: Is this text actually inside the sidebar zone?
                                if rect.x0 < sidebar_threshold:
                                    # Safe to apply wide horizontal layout clearance to swallow icons
                                    safe_rect = fitz.Rect(
                                        rect.x0 - icon_pad, 
                                        rect.y0 - 8, 
                                        rect.x1 + 5, 
                                        rect.y1 + 8
                                    )
                                else:
                                    # It's in the main body area (like work history)! 
                                    # Use a microscopic laser-tight crop so it NEVER bleeds left into descriptions
                                    safe_rect = fitz.Rect(
                                        rect.x0 - 2, 
                                        rect.y0 - 1, 
                                        rect.x1 + 2, 
                                        rect.y1 + 1
                                    )
                                
                                page.add_redact_annot(safe_rect, fill=(1, 1, 1))
                                redactions_applied += 1
                                
        # Fallback pass for layout text remnants
        page_text = page.get_text()
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                # Apply the same coordinate checks to vanity path loops
                if rect.x0 < sidebar_threshold:
                    safe_slug_rect = fitz.Rect(rect.x0 - icon_pad, rect.y0 - 8, rect.x1 + 5, rect.y1 + 8)
                else:
                    safe_slug_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 1, rect.x1 + 2, rect.y1 + 1)
                page.add_redact_annot(safe_slug_rect, fill=(1, 1, 1))
                redactions_applied += 1
                
        # Apply the visual masks and erase target fields
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_applied

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Executing coordinate-isolated cleanup..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, icon_clearance)
                
                if count == 0:
                    st.warning("No target elements matched your layout configuration parameters.")
                else:
                    st.success(f"Successfully cleaned layout fields without leaking into text columns!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
