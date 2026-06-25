# --- Layout Rendering UI ---
if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    original_name = uploaded_file.name
    
    if original_name.lower().endswith(".pdf"):
        base_name = original_name[:-4]
    else:
        base_name = original_name
    output_filename = f"{base_name}_Redacted.pdf"
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Control Actions")
        try:
            scrubbed_pdf, total_pages = redact_pdf(
                file_bytes, layout_style, h_limit, v_limit, top_boundary
            )
            st.success("Calculated successfully!")
            
            st.download_button(
                label="Download Redacted PDF",
                data=scrubbed_pdf,
                file_name=output_filename,
                mime="application/pdf",
                type="primary"
            )
            
            if total_pages > 1:
                st.markdown("---")
                preview_page = st.selectbox(
                    "Flip Preview Page:",
                    options=list(range(1, total_pages + 1)),
                    index=0
                )
            else:
                preview_page = 1
                
        except Exception as e:
            st.error(f"Error compiling document: {e}")
            scrubbed_pdf, total_pages, preview_page = None, 1, 1

    with col2:
        st.subheader("Live Document Preview")
        if scrubbed_pdf is not None:
            try:
                images = convert_from_bytes(
                    scrubbed_pdf, 
                    first_page=preview_page, 
                    last_page=preview_page
                )
                if images:
                    st.image(
                        images, 
                        caption=f"Page {preview_page} of {total_pages}", 
                        width=zoom_level
                    )
            except Exception as img_err:
                st.error(f"Visual preview error: {img_err}")
