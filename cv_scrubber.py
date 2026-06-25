import streamlit as st
import fitz, re, io
from pdf2image import convert_from_bytes

st.set_page_config(page_title="PDF CV Scrubber", layout="wide")
st.title("Interactive PDF CV Contact Scrubber")
st.write("Upload your resume and use Auto-Tune or manual sliders.")

if "top_boundary_val" not in st.session_state: st.session_state.top_boundary_val = 88
if "h_limit_val" not in st.session_state: st.session_state.h_limit_val = 220
if "v_limit_val" not in st.session_state: st.session_state.v_limit_val = 260
if "active_layout" not in st.session_state: st.session_state.active_layout = "Standard Layout"

st.sidebar.header("Layout Settings")
layout_style = st.sidebar.selectbox("Select layout style:", options=["Standard Layout", "Two-Column Sidebar Layout"], key="layout_style_selection")

st.sidebar.markdown("---")
st.sidebar.header("Redaction Block Aesthetics")
mask_color_toggle = st.sidebar.checkbox("⬛ Use Solid Black Redaction Bars", value=False)
chosen_color = (0, 0, 0) if mask_color_toggle else (1, 1, 1)

if layout_style != st.session_state.active_layout:
    st.session_state.active_layout = layout_style
    if "Two-Column" in layout_style: st.session_state.top_boundary_val, st.session_state.h_limit_val, st.session_state.v_limit_val = 88, 220, 260
    else: st.session_state.top_boundary_val, st.session_state.h_limit_val, st.session_state.v_limit_val = 0, 15, 0

uploaded_file = st.file_uploader("Upload the PDF Resume", type=["pdf", "docx", "doc"])

if uploaded_file is not None and uploaded_file.name.lower().endswith((".docx", ".doc")):
    st.error("⚠️ Invalid File Type Detected!")
    st.markdown("Our CV Scrubber can only process **PDF files**.\n\n**How to convert your Word document:**\n1. Open file in Word.\n2. Click **File** -> **Save As**.\n3. Select **PDF (*.pdf)** from format list.\n4. Upload new PDF here.")
    st.stop()

def core_contact_check(text):
    text_lower = text.lower().strip()
    return (bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)) or bool(re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}', text)) or "linkedin.com" in text_lower or "/in/" in text_lower or "www." in text_lower or "http" in text_lower or "hotmail" in text_lower or "yahoo" in text_lower or "outlook" in text_lower)

if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    if st.sidebar.button("🔮 Auto-Tune to Fit Layout", type="primary"):
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_dict = doc[0].get_text("dict")
            contact_boxes, profile_x0 = [], None
            for block in page_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        txt = span["text"].upper().strip()
                        if core_contact_check(span["text"]): contact_boxes.append(fitz.Rect(span["bbox"]))
                        if txt in ["PROFILE", "EXPERIENCE", "EDUCATION"]: profile_x0 = span["bbox"]
            if "Two-Column" in layout_style:
                st.session_state.top_boundary_val, st.session_state.h_limit_val, st.session_state.v_limit_val = 85, (int(profile_x0[0]) if profile_x0 else 220), (int(max([r.y1 for r in contact_boxes])) + 15 if contact_boxes else 260)
            else: st.session_state.top_boundary_val, st.session_state.h_limit_val, st.session_state.v_limit_val = 0, 15, 0
            doc.close()
            st.sidebar.success("Auto-tuned successfully!")
        except Exception as e: st.sidebar.error(f"Auto-tune failed: {e}")

st.sidebar.markdown("---")
st.sidebar.header("Live Mask Adjustment")
top_boundary = st.sidebar.slider("Mask Top Boundary", 0, 200, st.session_state.top_boundary_val, 1, key="top_slider")
st.session_state.top_boundary_val = top_boundary

if "Two-Column" in layout_style:
    h_limit = st.sidebar.slider("Mask Width Barrier", 100, 300, st.session_state.h_limit_val, 1, key="h_slider_two")
    v_limit = st.sidebar.slider("Mask Height Ceiling", 100, 500, st.session_state.v_limit_val, 1, key="v_slider_two")
else:
    h_limit = st.sidebar.slider("Icon Extension Offset Left", 0, 150, st.session_state.h_limit_val, 1, key="h_slider_std")
    v_limit = st.sidebar.slider("Mask Extra Bottom Padding", 0, 50, st.session_state.v_limit_val, 1, key="v_slider_std")
st.session_state.h_limit_val, st.session_state.v_limit_val = h_limit, v_limit

st.sidebar.markdown("---")
zoom_level = st.sidebar.slider("Document Zoom Level", 300, 1200, 750, 25)

def redact_pdf(file_bytes, layout_profile, w_barrier, h_ceiling, top_start, mask_color):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        page_text, page_dict = page.get_text(), page.get_text("dict")
        protected_words = set()
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["bbox"][1] < 60 and not core_contact_check(span["text"]):
                        if span["text"].upper().strip() not in ["EDUCATION", "EXPERIENCE", "PROFILE"]:
                            for token in span["text"].lower().split(): protected_words.add(token.strip(":,.-_"))
        if "Standard Layout" in layout_profile:
            targets = set()
            for e in re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_text): targets.add(e.strip())
            for p in re.findall(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{3,4}', page_text):
                if len(p.strip()) > 6: targets.add(p.strip())
            for word in ["mobile:", "email:", "phone:", "website:", "linkedin:", "hotmail", "yahoo", "outlook", "today", "cna"]:
                if word in page_text.lower(): targets.add(word)
            for link in page.get_links():
                if link["from"][1] < 130: page.add_redact_annot(fitz.Rect(link["from"][0] - w_barrier, link["from"][1] - 6, link["from"][2] + 30, link["from"][3] + h_ceiling), fill=mask_color)
            for target in targets:
                for rect in page.search_for(target):
                    if rect.y0 > 130: continue
                    is_p = any(w[4].lower().strip(":,.-_") in protected_words for w in page.get_text("words", clip=rect) if w[4].lower().strip(":,.-_") not in ["today", "cna", "hotmail"])
                    if not is_p: page.add_redact_annot(fitz.Rect(rect.x0 - w_barrier, rect.y0 - 6, rect.x1 + 30, rect.y1 + h_ceiling), fill=mask_color)
            for s_rect in page.search_for("/"):
                if s_rect.y0 < 130 and s_rect.x0 > 150: page.add_redact_annot(fitz.Rect(s_rect.x0 - 4, s_rect.y0 - 4, s_rect.x1 + 4, s_rect.y1 + 4), fill=mask_color)
        else:
            main_col = float(w_barrier)
            for block in page_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span["text"].upper().strip() in ["PROFILE", "EXPERIENCE", "EDUCATION"] and w_barrier == 220: main_col = float(span["bbox"][0])
            for block in page_dict.get("blocks", []):
                if block["bbox"][2] < main_col and top_start < block["bbox"][1] < h_ceiling: page.add_redact_annot(fitz.Rect(0, max(block["bbox"][1] - 4, top_start), main_col - 10, min(block["bbox"][3] + 4, h_ceiling)), fill=mask_color)
        page.apply_redactions()
    output_buffer = io.BytesIO()
    doc.save(output_buffer, garbage=4, deflate=True)
    total_pages = len(doc)
    doc.close()
    return output_buffer.getvalue(), total_pages

if uploaded_file is not None and uploaded_file.name.lower().endswith(".pdf"):
    base_name = uploaded_file.name[:-4]
    output_filename = f"{base_name}_Redacted.pdf"
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Control Actions")
        try:
            scrubbed_pdf, total_pages = redact_pdf(file_bytes, layout_style, h_limit, v_limit, top_boundary, chosen_color)
            st.success("Calculated successfully!")
            st.download_button(label="Download Redacted PDF", data=scrubbed_pdf, file_name=output_filename, mime="application/pdf", type="primary")
            preview_page = st.selectbox("Flip Preview Page:", options=list(range(1, total_pages + 1)), index=0) if total_pages > 1 else 1
        except Exception as e: st.error(f"Error compiling document: {e}"); scrubbed_pdf, total_pages, preview_page = None, 1, 1
    st.markdown("---")
    if st.button("🧹 Clear Current File", use_container_width=True): st.rerun()
    with col2:
        st.subheader("Live Document Preview")
        if scrubbed_pdf:
            try:
                images = convert_from_bytes(scrubbed_pdf, first_page=preview_page, last_page=preview_page)
                if images: st.image(images, caption=f"Page {preview_page} of {total_pages}", width=zoom_level)
            except Exception as img_err: st.error(f"Visual preview error: {img_err}")
