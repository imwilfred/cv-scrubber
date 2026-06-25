import streamlit as st
import fitz  # PyMuPDF
import io

st.set_page_config(page_title="PDF CV Scrubber", page_icon="doc")

st.title("PDF CV Contact Information Scrubber")
st.write("Upload a PDF resume and adjust the sliders to invisibly wipe out the contact block zone.")

# --- Clean, Professional Sidebar Controls ---
st.sidebar.header("Masking Zone Settings")
st.sidebar.write("Adjust these sliders to completely cover the contact details without touching your body text.")

# Sliders to dynamically control the white-out box dimensions
box_width = st.sidebar.slider("Mask Width (Horizontal)", min_value=100, max_value=300, value=170, step=5,
                              help="Decrease this if it cuts into headers like 'PROFILE'.")
box_height = st.sidebar.slider("Mask Height (Vertical)", min_value=50, max_value=300, value=210, step=5)

uploaded_file = st.file_uploader("Choose a PDF resume", type="pdf")

def redact_pdf(file_bytes, width, height):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    for page in doc:
        # Draw a clean white box over the upper-left contact details zone
        # Starts safely at the left margin (x=15, y=85) and extends based on sliders
        contact_zone_rect = fitz.Rect(15, 85, width, height)
        
        # Apply pure white mask
        page.add_redact_annot(contact_zone_rect, fill=(1, 1, 1))
        page.apply_redactions()
        
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    doc.close()
    
    return output_buffer.getvalue()

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    if st.button("Clean PDF Document", type="primary"):
        with st.spinner("Erasing selected layout zone..."):
            try:
                scrubbed_pdf = redact_pdf(file_bytes, box_width, box_height)
                st.success("Document processed successfully!")
                
                st.download_button(
                    label="Download Redacted PDF",
                    data=scrubbed_pdf,
                    file_name="cleaned_resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not parse this specific PDF layout: {e}")
