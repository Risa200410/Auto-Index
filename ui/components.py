# =====================================================================
# AutoIndex - ui/components.py
# =====================================================================

import streamlit as st


def render_header():
    st.markdown("""
    <div class="app-header">
        <div class="logo">📑</div>
        <div>
            <h1>AutoIndex</h1>
            <p>Sistem Ekstraksi Kata Kunci &amp; Pembuat Indeks Buku Otomatis</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def step_label(num: int, text: str, done: bool = False):
    cls = "done" if done else ""
    st.markdown(f"""
    <div class="step-label">
        <span class="num {cls}">{num}</span>
        {text}
    </div>
    """, unsafe_allow_html=True)


def card_open():
    st.markdown('<div class="card-wrap">', unsafe_allow_html=True)


def card_close():
    st.markdown('</div>', unsafe_allow_html=True)


def render_file_badge(name: str, size_kb: float):
    st.markdown(f"""
    <div class="file-badge">
        ✅ &nbsp;<strong>{name}</strong> &nbsp;·&nbsp; {size_kb:.1f} KB
    </div>
    """, unsafe_allow_html=True)


class StepProgress:
    def __init__(self, total: int):
        self.total   = total
        self._bar    = st.progress(0, text="Memulai…")
        self._status = st.empty()

    def update(self, step: int, msg: str):
        pct = int(step / self.total * 100)
        self._bar.progress(pct, text=f"**Langkah {step}/{self.total}** — {msg}")
        self._status.caption(f"⚙️ {msg}")

    def done(self):
        self._bar.progress(100, text="Selesai!")
        self._status.empty()


def render_stats(n_keywords: int, n_pages_covered: int):
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Kata Kunci Diekstrak", n_keywords)
    with c2:
        st.metric("Halaman Tercakup", n_pages_covered)


def render_footer():
    st.markdown("""
    <div class="app-footer">
        <strong>AutoIndex</strong>
    </div>
    """, unsafe_allow_html=True)