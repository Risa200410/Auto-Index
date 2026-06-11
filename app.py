# =====================================================================
# AutoIndex - app.py
# =====================================================================

import io
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="AutoIndex",
    page_icon="📑",
    layout="centered",
    initial_sidebar_state="collapsed",
)

from ui.styles     import inject_css
from ui.components import (
    render_header, step_label,
    render_file_badge, StepProgress, render_stats, render_footer,
)

inject_css()


@st.cache_resource(show_spinner="⏳ Memuat model AI (hanya sekali)…")
def get_models():
    from core.extractor import load_models
    return load_models()


render_header()

# ── Session state ──────────────────────────────────────────────
for k, v in {
    "pdf_bytes": None, "pdf_name": "",
    "results": None, "export_ready": False, "export_bytes": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════
# LANGKAH 1 — Upload
# ══════════════════════════════════════════════════════════════
with st.container(border=True, key="step_card_1"):
    step_label(1, "Upload Dokumen", done=st.session_state.pdf_bytes is not None)
    st.markdown('<p class="step-title">Unggah File PDF</p>', unsafe_allow_html=True)
    st.markdown('<p class="step-desc">Sistem menerima dokumen PDF (skripsi, buku, laporan). Format lain tidak didukung.</p>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        label="Pilih file PDF",
        type=["pdf"],
        label_visibility="collapsed",
        accept_multiple_files=False,
    )

    if uploaded is not None:
        if not uploaded.name.lower().endswith(".pdf"):
            st.error("❌ Format file tidak didukung! Silakan unggah file berformat PDF.")
            st.session_state.pdf_bytes = None
        else:
            pdf_bytes = uploaded.read()
            if st.session_state.pdf_name != uploaded.name:
                st.session_state.results      = None
                st.session_state.export_ready = False
                st.session_state.export_bytes = None
                if "df_base" in st.session_state: del st.session_state["df_base"]
                if "kw_table" in st.session_state: del st.session_state["kw_table"]
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.pdf_name  = uploaded.name
            st.success("✅ File PDF berhasil diunggah.")


# ══════════════════════════════════════════════════════════════
# LANGKAH 2 — Konfigurasi & Ekstraksi
# ══════════════════════════════════════════════════════════════
if st.session_state.pdf_bytes:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True, key="step_card_2"):
        step_label(2, "Konfigurasi & Ekstraksi", done=st.session_state.results is not None)
        st.markdown('<p class="step-title">Pengaturan Ekstraksi</p>', unsafe_allow_html=True)
        st.markdown('<p class="step-desc">Tentukan jumlah kata kunci, lalu klik tombol untuk memulai proses.</p>', unsafe_allow_html=True)

        top_n = st.slider("Jumlah maksimum kata kunci (Top-N)", 10, 150, 62, 1)

        col_btn, _ = st.columns([1, 3])
        with col_btn:
            extract_clicked = st.button("🔍 Extract Keywords", use_container_width=True)

        if extract_clicked:
            nlp, kw_model = get_models()
            progress = StepProgress(total=5)
            with st.spinner(""):
                from core.extractor import run_extraction
                results = run_extraction(
                    pdf_bytes=st.session_state.pdf_bytes,
                    top_n=top_n, nlp=nlp, kw_model=kw_model,
                    progress_callback=lambda s, t, m: progress.update(s, m),
                )
            progress.done()
            st.session_state.results      = results
            st.session_state.export_ready = False
            st.session_state.export_bytes = None
            if "df_base" in st.session_state: del st.session_state["df_base"]
            if "kw_table" in st.session_state: del st.session_state["kw_table"]
            st.rerun()


# ══════════════════════════════════════════════════════════════
# LANGKAH 3 — Tabel hasil
# ══════════════════════════════════════════════════════════════
if st.session_state.results:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True, key="step_card_3"):
        step_label(3, "Hasil Ekstraksi", done=True)
        st.markdown('<p class="step-title">Kata Kunci yang Diekstrak</p>', unsafe_allow_html=True)
        st.markdown('<p class="step-desc">Secara default, tidak ada kata kunci yang dicentang. Centang kata kunci yang ingin dimasukkan ke dalam indeks, atau gunakan tombol di bawah.</p>', unsafe_allow_html=True)

        results = st.session_state.results
        all_pages = set()
        for r in results:
            for p in r["pages"].split(","):
                p = p.strip()
                if p and p != "-":
                    all_pages.add(p)
        render_stats(len(results), len(all_pages))
        st.markdown("<br>", unsafe_allow_html=True)

        if "df_base" not in st.session_state:
            st.session_state.df_base = pd.DataFrame({
                "Pilih"      : [False] * len(results),
                "Kata Kunci" : [r["keyword"] for r in results],
                "Skor Bobot" : [r["score"]   for r in results],
                "Halaman"    : [r["pages"]   for r in results],
            })

        col_all, col_none, _ = st.columns([1, 1, 1.5])
        with col_all:
            if st.button("☑️ Centang Semua", use_container_width=True):
                st.session_state.df_base["Pilih"] = True
                if "kw_table" in st.session_state: del st.session_state["kw_table"]
                st.rerun()
        with col_none:
            if st.button("☐ Kosongkan Pilihan", use_container_width=True):
                st.session_state.df_base["Pilih"] = False
                if "kw_table" in st.session_state: del st.session_state["kw_table"]
                st.rerun()

        edited_df = st.data_editor(
            st.session_state.df_base,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Pilih"      : st.column_config.CheckboxColumn("Pilih", width="small"),
                "Kata Kunci" : st.column_config.TextColumn("Kata Kunci", disabled=True, width="large"),
                "Skor Bobot" : st.column_config.NumberColumn("Skor Bobot", disabled=True, format="%.4f", width="small"),
                "Halaman"    : st.column_config.TextColumn("Halaman", disabled=True, width="medium"),
            },
            key="kw_table",
        )

        n_selected = int(edited_df["Pilih"].sum())
        if n_selected == 0:
            st.warning("Belum ada kata kunci yang dipilih.")
        else:
            st.caption(f"{n_selected} dari {len(results)} kata kunci dipilih.")

    # ════════════════════════════════════════════════════════
    # LANGKAH 4 — Export
    # ════════════════════════════════════════════════════════
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True, key="step_card_4"):
        step_label(4, "Export Indeks ke PDF", done=st.session_state.export_ready)
        st.markdown('<p class="step-title">Buat &amp; Unduh PDF dengan Halaman Indeks</p>', unsafe_allow_html=True)
        st.markdown('<p class="step-desc">Sistem membuat halaman indeks A-Z dan menggabungkannya ke akhir PDF asli.</p>', unsafe_allow_html=True)

        col_exp, col_dl = st.columns([1, 2])
        with col_exp:
            export_clicked = st.button("ExportPDF", disabled=(n_selected == 0), use_container_width=True)

        if export_clicked and n_selected > 0:
            selected = edited_df[edited_df["Pilih"] == True]
            kw_list  = [{"keyword": r["Kata Kunci"], "pages": r["Halaman"]} for _, r in selected.iterrows()]
            with st.spinner("🔧 Membuat halaman indeks…"):
                from core.pdf_builder import build_index_pdf, merge_index_to_pdf
                merged = merge_index_to_pdf(st.session_state.pdf_bytes, build_index_pdf(kw_list))
            st.session_state.export_bytes = merged
            st.session_state.export_ready = True
            st.success(f"PDF berhasil dibuat dengan {n_selected} kata kunci!")
            st.rerun()

        if st.session_state.export_ready and st.session_state.export_bytes:
            out_name = st.session_state.pdf_name.replace(".pdf", "_indexed.pdf")
            with col_dl:
                st.download_button(
                    label="Download PDF Final",
                    data=st.session_state.export_bytes,
                    file_name=out_name,
                    mime="application/pdf",
                    use_container_width=True,
                )

render_footer()

import streamlit.components.v1 as components
components.html("""
<script>
// Run after a slight delay to ensure Streamlit DOM is fully rendered
setTimeout(() => {
    const parent = window.parent.document;
    const labels = parent.querySelectorAll('.step-label');
    labels.forEach(label => {
        // Find the closest border wrapper or vertical block that acts as the card container
        let container = label.closest('[data-testid="stVerticalBlockBorderWrapper"]');
        if (!container) {
            // Fallback for different Streamlit versions
            let stBlock = label.closest('[data-testid="stVerticalBlock"]');
            if (stBlock && stBlock.parentElement && stBlock.parentElement.className.includes('st-emotion-cache')) {
                container = stBlock.parentElement;
            } else {
                container = stBlock;
            }
        }
        
        if (container) {
            container.style.setProperty('background-color', '#FFFFFF', 'important');
            container.style.setProperty('border', 'none', 'important');
            container.style.setProperty('border-left', '5px solid #4F46E5', 'important');
            container.style.setProperty('border-radius', '16px', 'important');
            container.style.setProperty('padding', '1.5rem 1.75rem', 'important');
            container.style.setProperty('margin-bottom', '1rem', 'important');
            container.style.setProperty('box-shadow', '0 4px 20px rgba(79,70,229,.08)', 'important');
        }
    });
}, 100);
</script>
""", height=0, width=0)
