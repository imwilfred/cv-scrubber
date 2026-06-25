import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload any PDF resume format to cleanly erase contact data and icons while completely safeguarding your name.")

# --- Layout Selector Sidebar ---
st.sidebar.header("Layout Profile Selector")
icon_alignment = st.sidebar.selectbox(
    "Select your CV's layout style:",
    options=[
        "Standard Layout (Right-aligned Contact Text / No Sidebar Icons)",
        "Two-Column Sidebar Layout (Vertical Stacked Icons on Left)"
    ],
    help="Select 'Standard Layout' for plain horizontal headers. Select 'Two-Column Sidebar Layout' if you have a column of circular icons on the far left."
)

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def core_contact_check(text):
    """Returns True ONLY for unmistakable contact data streams."""
    text_lower = text.lower().strip()
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    has_phone = bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text))
    has_linkedin = "linkedin.com" in text_lower or "/in/" in text_lower
    has_generic_url = "www." in text_lower or "http" in text_lower
    
    return has_email or has_phone or has_linkedin or has_generic_url

def should_scrub_labels(text):
    """Matches standalone introductory structural labels."""
    text_lower = text.lower().strip()
    clean_word = re.sub(r'[^a-z]', '', text_lower).strip()
    contact_labels = {"mobile", "phone", "email", "linkedin", "socials", "links", "website", "contact"}
    return clean_word in contact_labels and len(text_lower) < 15

def redact_pdf(file_bytes, layout_style):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    # Precise regex patterns to isolate specific sequences character-by-character
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    phone_pattern = re.compile(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}')
    
    for page in doc:
        page_dict = page.get_text("dict")
        is_sidebar_mode = "Two-Column Sidebar Layout" in layout_style
        contact_y_positions = []
        
        # Phase 1: Micro-targeted character cleaning
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            span_text = span["text"]
                            
                            # Find and isolate emails inside any text block
                            for email_match in email_pattern.finditer(span_text):
                                email_str = email_match.group(0)
                                rect_list = page.search_for(email_str)
                                for r in rect_list:
                                    # Laser cut: only cover the exact characters of the email
                                    tight_r = fitz.Rect(r.x0, r.y0 - 1, r.x1, r.y1 + 1)
                                    page.add_redact_annot(tight_r, fill=(1, 1, 1))
                                    redactions_applied += 1
                                    contact_y_positions.append(r.y0)
                                    
                            # Find and isolate phone numbers inside any text block
                            for phone_match in phone_pattern.finditer(span_text):
                                phone_str = phone_match.group(0)
                                rect_list = page.search_for(phone_str)
                                for r in rect_list:
                                    # Laser cut: only cover the exact characters of the phone number
                                    tight_r = fitz.Rect(r.x0, r.y0 - 1, r.x1, r.y1 + 1)
                                    page.add_redact_annot(tight_r, fill=(1, 1, 1))
                                    redactions_applied += 1
                                    contact_y_positions.append(r.y0)
                                    
                            # Remove standalone labels safely (like "Mobile:" or "Email:")
                            if should_scrub_labels(span_text):
                                rect = fitz.Rect(span["bbox"])
                                tight_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 1, rect.x1 + 2, rect.y1 + 1)
                                page.add_redact_annot(tight_rect, fill=(1, 1, 1))
                                redactions_applied += 1
                                contact_y_positions.append(rect.y0)

        # Phase 2: Target local, nearby Location markers safely (Protects University headings)
        if is_sidebar_mode and contact_y_positions:
            min_contact_y = min(contact_y_positions) - 40
            max_contact_y = max(contact_y_positions) + 60
            
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                span_text = span["text"]
                                rect = fitz.Rect(span["bbox"])
                                
                                if min_contact_y <= rect.y0 <= max_contact_y:
                                    is_location = bool(re.search(r'\b(singapore|asia|malaysia|usa|uk|london|address|location)\b', span_text.lower()))
                                    if is_location or len(span_text.strip()) < 3: 
                                        tight_rect = fitz.Rect(rect.x0 - 4, rect.y0 - 2, rect.x1 + 4, rect.y1 + 2)
                                        page.add_redact_annot(tight_rect, fill=(1, 1, 1))
                                        redactions_applied += 1

        # Phase 3: Targeted Sidebar Icon Column Erasing Channel
        if is_sidebar_mode:
            # Clears the vertical icon track column cleanly without moving upward into header boundaries
            icon_strip_zone = fitz.Rect(12, 85, 42, 195)
            page.add_redact_annot(icon_strip_zone, fill=(1, 1, 1))
            redactions_applied += 1
            
        # Fallback pass for layout text vanity handles
        page_text = page.get_text()
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                safe_slug_rect = fitz.Rect(rect.x0 - 4, rect.y0 - 2, rect.x1 + 4, rect.y1 + 2)
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
        with st.spinner("Executing layout-isolated masking pipeline..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, icon_alignment)
                
                if count == 0:
                    st.warning("No target details matched your active layout profile.")
                else:
                    st.success("Document scrubbed cleanly! Name and layout text are fully preserved.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
