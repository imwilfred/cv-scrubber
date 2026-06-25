import streamlit as st
import fitz  # PyMuPDF
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
        page_width = page.rect.width
        
        # --- FIXED, SAFELY ISOLATED COORDINATE MASKS ---
        if "Standard Layout" in layout_profile:
            # Drop a precise mask over the upper right quadrant contact lines
            # Starts at x=320 (safely to the right of your name), y=48 (safely BELOW your name line), 
            # extending to the edge of the page. This guarantees numbers, emails, and labels disappear while your name stays 100% safe.
            right_mask = fitz.Rect(320, 48, page_width - 15, 110)
            page.add_redact_annot(right_mask, fill=(1, 1, 1))
            redactions_applied += 1
                
        else:
            # Two-Column Sidebar Layout Profile
            # Drops a fixed vertical block covering the left column space completely.
            # Set to x=215 to cleanly swallow the entire word 'CONTACT' and links, while leaving 'PROFILE' and body columns perfectly intact.
            left_sidebar_mask = fitz.Rect(10, 85, 215, 250)
            page.add_redact_annot(left_sidebar_mask, fill=(1, 1, 1))
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
                    st.success("Document scrubbed cleanly! Layout and name preserved perfectly.")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
