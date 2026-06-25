import streamlit as st
import fitz  # PyMuPDF
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload any PDF resume format to cleanly erase contact layers, labels, and icons instantly.")

# --- Layout Selector Sidebar ---
st.sidebar.header("Layout Profile Selector")
layout_style = st.sidebar.selectbox(
    "Select your CV's layout style:",
    options=[
        "Standard Layout (Right-aligned Contact Text / No Sidebar Icons)",
        "Two-Column Sidebar Layout (Vertical Stacked Icons on Left)"
    ],
    help="Select 'Standard Layout' for plain horizontal headers. Select 'Two-Column Sidebar Layout' if you have a column of circular icons on the far left."
)

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def redact_pdf(file_bytes, layout_profile):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    redactions_applied = 0
    
    for page in doc:
        page_width = page.rect.width
        
        # --- EXECUTE LAYOUT-BASED COORDINATE MASKS ---
        if "Standard Layout" in layout_profile:
            # Drop an absolute masking rectangle over the upper right quadrant
            # Starts at x=300 (safely to the right of your name), y=35 (below your name top line), 
            # extending to the edge of the page. This completely whites out 'Mobile:', '/', and invisible email segments.
            right_mask = fitz.Rect(300, 32, page_width - 15, 80)
            page.add_redact_annot(right_mask, fill=(1, 1, 1))
            redactions_applied += 1
                
        else:
            # Two-Column Sidebar Layout Profile
            # Drops a vertical block covering the entire left column space up to the profile dividing line.
            # This completely cleans out fragmented data blocks like 'com/in', addresses, and vertical icon strips.
            left_sidebar_mask = fitz.Rect(10, 85, 290, 350)
            page.add_redact_annot(left_sidebar_mask, fill=(1, 1, 1))
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
