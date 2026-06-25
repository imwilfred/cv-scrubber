import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume to cleanly erase contact layers using strict vertical column bounding walls.")

# --- UI Sidebar Controls ---
st.sidebar.header("Adaptive Controls")
icon_clearance = st.sidebar.slider("Icon Strip Clearance Width", min_value=10, max_value=150, value=60, step=5,
                                  help="Increase this ONLY if contact icons are still partially showing.")

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
        
        # FIRST PASS: Locate the exact vertical column coordinates where contact text lives
        contact_columns = []
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            if should_scrub_text(span["text"]):
                                # Record the absolute physical left-and-right edges of this text column block
                                contact_columns.append((block["bbox"][0], block["bbox"][2]))
        
        # SECOND PASS: Apply walled redactions
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            span_text = span["text"]
                            
                            if should_scrub_text(span_text):
                                rect = fitz.Rect(span["bbox"])
                                block_x0, block_x1 = block["bbox"][0], block["bbox"][2]
                                
                                # Check if expanding left passes the outer structural boundary of the contact block itself
                                # If expanding by icon_pad hits another column's starting space, we lock it down.
                                is_isolated_column_start = True
                                for cx0, cx1 in contact_columns:
                                    # If there's text found to the left that belongs to a separate block structure
                                    if block_x0 > cx1:
                                        is_isolated_column_start = False
                                        break
                                
                                if not is_isolated_column_start or (rect.x0 - block_x0) < 5:
                                    # Alternate check: If the text is sharing a block line with regular phrases
                                    # Use a laser tight horizontal boundary line to protect adjacent text columns
                                    safe_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
                                else:
                                    # Truly isolated column area! Expand confidently to mask the icon graphic.
                                    safe_rect = fitz.Rect(rect.x0 - icon_pad, rect.y0 - 8, rect.x1 + 5, rect.y1 + 8)
                                
                                page.add_redact_annot(safe_rect, fill=(1, 1, 1))
                                redactions_applied += 1
                                
        # Fallback pass for orphaned text remnants
        page_text = page.get_text()
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                # Laser crop by default to guarantee structural work history safety
                safe_slug_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
                page.add_redact_annot(safe_slug_rect, fill=(1, 1, 1))
                redactions_applied += 1
                
        # Commit redactions permanently onto the current page layout
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_applied

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Executing absolute column barrier protection..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, icon_clearance)
                
                if count == 0:
                    st.warning("No target fields matched your layout constraints.")
                else:
                    st.success("Successfully cleared contact layers with absolute column safety walls!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
