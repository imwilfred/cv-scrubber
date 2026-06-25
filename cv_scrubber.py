import streamlit as st
import fitz  # PyMuPDF
import re
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload any PDF resume format to cleanly erase contact layers, labels, and icons instantly.")

# --- Clean Layout Selector Sidebar ---
st.sidebar.header("Layout Profile Selector")
layout_style = st.sidebar.selectbox(
    "Select your CV's layout style:",
    options=[
        "Standard Layout (Right-aligned Contact Text / No Sidebar Icons)",
        "Two-Column Sidebar Layout (Vertical Stacked Icons on Left)"
    ],
    help="Select 'Standard Layout' for plain horizontal headers. Select 'Two-Column Sidebar Layout' if you have a column of circular icons on the far left."
)

def redact_pdf(file_bytes, layout_profile):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        page_text = page.get_text()
        page_dict = page.get_text("dict")
        
        if "Standard Layout" in layout_profile:
            # --- STRATEGY 1: LASER SUBSTRING SEARCH (Protects Right-Aligned Names) ---
            targets = set()
            
            # Find structural emails
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_text)
            for e in emails: targets.add(e.strip())
            
            # Find structural phone numbers
            phones = re.findall(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', page_text)
            for p in phones: 
                if len(p.strip()) > 6:
                    targets.add(p.strip())
            
            # Target structural labels
            labels = ["Mobile:", "Email:", "Phone:", "Web:", "Website:", "Contact:"]
            for label in labels:
                if label in page_text:
                    targets.add(label)
            
            # White out ONLY the precise character coordinates of identified targets
            for target in targets:
                rect_list = page.search_for(target)
                for rect in rect_list:
                    tight_rect = fitz.Rect(rect.x0 - 2, rect.y0 - 1, rect.x1 + 2, rect.y1 + 1)
                    page.add_redact_annot(tight_rect, fill=(1, 1, 1))
                    redactions_applied += 1
            
            # Isolate and remove the standalone formatting slash separator in the header zone
            slashes = page.search_for("/")
            for s_rect in slashes:
                if s_rect.y0 < 120 and s_rect.x0 > 250:
                    page.add_redact_annot(s_rect, fill=(1, 1, 1))
                    redactions_applied += 1
                    
        else:
            # --- STRATEGY 2: DYNAMIC SIDEBAR BOUNDARY WALL (Protects Column Text) ---
            # Automatically find the exact coordinate where the main column starts
            main_column_left = 220  # Safe default fallback
            
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line:
                            for span in line["spans"]:
                                txt = span["text"].upper().strip()
                                if txt in ["PROFILE", "PROFESSIONAL EXPERIENCE", "EXPERIENCE"]:
                                    main_column_left = span["bbox"][0]
                                    break
            
            # White out all content containers on the left side of the calculated wall boundary
            for block in page_dict.get("blocks", []):
                bx0, by0, bx1, by1 = block["bbox"]
                
                # If the block belongs to the sidebar zone below the top header title area
                if bx1 < main_column_left and by0 > 70:
                    # Extend mask to the far left edge to swallow icons, but lock it before the text wall
                    sidebar_mask = fitz.Rect(0, by0 - 4, main_column_left - 10, by1 + 4)
                    page.add_redact_annot(sidebar_mask, fill=(1, 1, 1))
                    redactions_applied += 1
                    
        # Commit redactions permanently onto the current page layout
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue(), redactions_applied

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Executing layout-isolated masking pipeline..."):
            try:
                scrubbed_pdf, count = redact_pdf(file_bytes, layout_style)
                
                if count == 0:
                    st.warning("No target details matched your active layout profile.")
                else:
                    st.success("Document scrubbed cleanly! Layout integrity preserved.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
