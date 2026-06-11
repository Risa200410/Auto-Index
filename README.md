# AutoIndex 
**Sistem Ekstraksi Kata Kunci & Pembuat Indeks Buku Otomatis**

Aplikasi web berbasis Streamlit untuk skripsi — mengekstrak kata kunci dari dokumen PDF menggunakan KeyBERT + Stanza, lalu menghasilkan halaman indeks yang digabungkan ke PDF asli.

---

## Struktur Proyek

```
autoindex/
├── app.py                  ← Entry point Streamlit
├── requirements.txt
├── README.md
├── core/
│   ├── __init__.py
│   ├── extractor.py        ← Pipeline NLP (KeyBERT + Stanza)
│   └── pdf_builder.py      ← Buat & gabungkan halaman indeks
└── ui/
    ├── __init__.py
    ├── styles.py           ← CSS kustom
    └── components.py       ← Komponen UI reusable
```

---

## Cara Instalasi & Menjalankan

### 1. Buat Virtual Environment
```bash
python -m venv venv

# Windows (CMD)
venv\Scripts\activate.bat

# Windows (PowerShell) — jika ada error execution policy:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
venv\Scripts\Activate.ps1

# Mac/Linux
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Jalankan Aplikasi
```bash
streamlit run app.py
```

---

## Alur Penggunaan

| Langkah | Aksi | Keterangan |
|---------|------|-----------|
| 1 | Upload PDF | Validasi format otomatis, non-PDF ditolak |
| 2 | Atur Top-N & Klik Extract | Proses NLP berjalan (progress bar) |
| 3 | Review tabel kata kunci | Centang/uncentang kata kunci yang diinginkan |
| 4 | Klik Export & Download | PDF final dengan halaman indeks A-Z |

---

## Komponen Teknis

### `core/extractor.py`
- **`extract_text_by_page()`** — Ekstrak teks per halaman, hapus header/footer boilerplate, deteksi nomor halaman cetak
- **`process_keywords_by_pages()`** — KeyBERT scoring dengan chunking per 300 kata, weighted score = `max_score × (1 + log10(frekuensi))`
- **`get_phrase_tag()`** — Filter Noun Phrase via Stanza POS tagger Bahasa Indonesia
- **`redundancy_filtering()`** — Hapus duplikat semantik dengan Jaccard similarity
- **`run_extraction()`** — Pipeline lengkap dengan progress callback untuk Streamlit

### `core/pdf_builder.py`
- **`build_index_pdf()`** — Buat halaman indeks A-Z menggunakan ReportLab, dikelompokkan per huruf awal
- **`merge_index_to_pdf()`** — Gabungkan halaman indeks ke akhir PDF asli via PyMuPDF

### `ui/styles.py`
- Injeksi CSS kustom: font DM Sans/DM Mono, color scheme bersih, card layout, button styling

### `ui/components.py`
- `render_header()`, `step_label()`, `card_open/close()`, `StepProgress`, `render_stats()`, `render_footer()`

---

## Catatan
- Model Stanza & KeyBERT di-cache dengan `@st.cache_resource` → hanya dimuat sekali selama sesi
- Pastikan koneksi internet aktif saat pertama kali dijalankan (untuk download model Stanza `id`)
