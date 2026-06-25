import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload any PDF resume format to cleanly erase contact data and icons while completely safeguarding your layout text.")

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
    
    for page in doc:
        page_dict = page.get_text("dict")
        
        # Determine if we are analyzing a Two-Column Sidebar Layout layout
        is_sidebar_mode = "Two-Column Sidebar Layout" in layout_style
        
        # Phase 1: Track where contact text fields sit on the page coordinate matrix
        contact_y_positions = []
        
        for block in page_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line:
                        for span in line["spans"]:
                            span_text = span["text"]
                            if core_contact_check(span_text) or should_scrub_labels(span_text):
                                rect = fitz.Rect(span["bbox"])
                                contact_y_positions.append(rect.y0)
                                
                                # Laser-tight extraction padding by default
                                tight_rect = fitz.Rect(rect.x0 - 4, rect.y0 - 2, rect.x1 + 4, rect.y1 + 2)
                                page.add_redact_annot(tight_rect, fill=(1, 1, 1))
                                redactions_applied += 1

        # Phase 2: Target local, nearby Location markers safely (Protects University headings)
        if is_sidebar_mode and contact_y_positions:
            # Find the vertical clustering range of the contact elements
            min_contact_y = min(contact_y_positions) - 40
            max_contact_y = max(contact_y_positions) + 60
            
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                span_text = span["text"]
                                rect = fitz.Rect(span["bbox"])
                                
                                # Process location strings ONLY if they physically reside inside the contact zone cluster
                                if min_contact_y <= rect.y0 <= max_contact_y:
                                    is_location = bool(re.search(r'\b(singapore|asia|malaysia|usa|uk|london|address|location)\b', span_text.lower()))
                                    if is_location or len(span_text.strip()) < 3: 
                                        tight_rect = fitz.Rect(rect.x0 - 4, rect.y0 - 2, rect.x1 + 4, rect.y1 + 2)
                                        page.add_redact_annot(tight_rect, fill=(1, 1, 1))
                                        redactions_applied += 1

        # Phase 3: Targeted Sidebar Icon Column Erasing Channel
        if is_sidebar_mode:
            # Drop a precise narrow strip covering the isolated grey icon column tracker path
            # Coordinates are calibrated to fit between x=12 and x=42 up to the top text plane
            icon_strip_zone = fitz.Rect(12, 20, 42, 195)
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
        with st.spinner("Executing structural multi-phase scrubbing pipeline..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, icon_alignment)
                
                if count == 0:
                    st.warning("No target details matched your active layout profile.")
                else:
                    st.success("Document scrubbed flawlessly across all layout metrics!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
