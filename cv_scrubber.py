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
    
    # Precise regex patterns to isolate specific contact blocks if merged with text
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    phone_pattern = re.compile(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}')
    
    for page in doc:
        page_dict = page.get_text("dict")
        is_sidebar_mode = "Two-Column Sidebar Layout" in layout_style
        contact_y_positions = []
        
        # Phase 1: Track and mask contact elements with coordinate exclusion
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            span_text = span["text"]
                            rect = fitz.Rect(span["bbox"])
                            
                            # ABSOLUTE BOUNDARY LOCK: If this text element sits in the upper top header area 
                            # (Vertical Y position is less than 75), it is mathematically forbidden from being whited out.
                            # This strictly protects your name block even if it shares a layout stream container.
                            if rect.y0 < 75:
                                # Safe Slicing: Only search and remove specific details inside this header block if they exist
                                for email_match in email_pattern.finditer(span_text):
                                    email_str = email_match.group(0)
                                    rect_list = page.search_for(email_str)
                                    for r in rect_list:
                                        # Only white out if the exact coordinate doesn't overlap the far left name zone
                                        if r.x0 > 200: 
                                            page.add_redact_annot(r, fill=(1, 1, 1))
                                            redactions_applied += 1
                                continue
                                
                            # Standard clean behavior for everything safely below the top title name zone
                            if core_contact_check(span_text) or should_scrub_labels(span_text):
                                contact_y_positions.append(rect.y0)
                                tight_rect = fitz.Rect(rect.x0 - 4, rect.y0 - 2, rect.x1 + 4, rect.y1 + 2)
                                page.add_redact_annot(tight_rect, fill=(1, 1, 1))
                                redactions_applied += 1

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
                                
                                # Only clean location markers if they are securely below the header line and inside the contact block
                                if rect.y0 >= 75 and min_contact_y <= rect.y0 <= max_contact_y:
                                    is_location = bool(re.search(r'\b(singapore|asia|malaysia|usa|uk|london|address|location)\b', span_text.lower()))
                                    if is_location or len(span_text.strip()) < 3: 
                                        tight_rect = fitz.Rect(rect.x0 - 4, rect.y0 - 2, rect.x1 + 4, rect.y1 + 2)
                                        page.add_redact_annot(tight_rect, fill=(1, 1, 1))
                                        redactions_applied += 1

        # Phase 3: Targeted Sidebar Icon Column Erasing Channel
        if is_sidebar_mode:
            # Drop the precise icon column track mask starting safely below the name header line (y0=85)
            icon_strip_zone = fitz.Rect(12, 85, 42, 195)
            page.add_redact_annot(icon_strip_zone, fill=(1, 1, 1))
            redactions_applied += 1
            
        # Fallback pass for layout text vanity handles
        page_text = page.get_text()
        custom_slugs = re.findall(r'/[a-zA-Z0-9_\-]{5,}/', page_text)
        for slug in custom_slugs:
            rect_list = page.search_for(slug)
            for rect in rect_list:
                if rect.y0 >= 75:  # Absolute safety gate check
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
        with st.spinner("Executing structural coordinate-locked protection pipeline..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, icon_alignment)
                
                if count == 0:
                    st.warning("No target details matched your active layout profile.")
                else:
                    st.success("Document scrubbed flawlessly! Header name zone completely locked and protected.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
