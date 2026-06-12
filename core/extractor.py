# =====================================================================
# AutoIndex - core/extractor.py
# Modul inti untuk ekstraksi kata kunci berbasis KeyBERT + Stanza
# =====================================================================

import re
import math
import pdfplumber
import wordninja
import stanza
from keybert import KeyBERT
from collections import Counter
from difflib import SequenceMatcher


# ─────────────────────────────────────────────
# KONSTANTA DEFAULT
# ─────────────────────────────────────────────
HEADER_MARGIN       = 50
FOOTER_MARGIN       = 50
SIMILARITY_THRESHOLD = 0.6   # Jaccard – redundancy filtering
MIN_WORDS            = 1
MAX_WORDS            = 3
CHUNK_SIZE           = 300


# ─────────────────────────────────────────────
# 1. DETEKSI NOMOR HALAMAN YANG DICETAK
# ─────────────────────────────────────────────
def detect_printed_page_number(page, physical_num,
                                header_margin=50, footer_margin=50):
    """
    Mencari nomor halaman asli yang tercetak di header/footer.
    Fallback ke nomor fisik jika tidak ditemukan.
    """
    h, w = page.height, page.width
    header_text = (page.crop((0, 0, w, header_margin)).extract_text() or "")
    footer_text  = (page.crop((0, h - footer_margin, w, h)).extract_text() or "")
    combined     = footer_text.strip() + "\n" + header_text.strip()
    numbers      = re.findall(r'\b\d+\b', combined)
    if numbers:
        return sorted(numbers, key=len)[0]
    return str(physical_num)


# ─────────────────────────────────────────────
# 2. EKSTRAKSI TEKS PER HALAMAN
# ─────────────────────────────────────────────
def extract_text_by_page(pdf_file_obj,
                          exclude_pages=None,
                          header_margin=HEADER_MARGIN,
                          footer_margin=FOOTER_MARGIN,
                          repeat_threshold=5):
    """
    Membaca PDF dari file-like object (BytesIO).
    Mengembalikan dict {printed_page_number: clean_text}.
    """
    if exclude_pages is None:
        exclude_pages = []

    # Pass 1 – kumpulkan semua baris untuk deteksi boilerplate
    all_lines = []
    with pdfplumber.open(pdf_file_obj) as pdf:
        for i, page in enumerate(pdf.pages):
            if (i + 1) in exclude_pages:
                continue
            h, w = page.height, page.width
            cropped   = page.crop((0, header_margin, w, h - footer_margin))
            page_text = cropped.extract_text() or ""
            for line in page_text.split('\n'):
                if line.strip():
                    all_lines.append(line.strip())

    line_counts   = Counter(all_lines)
    boilerplate   = {ln for ln, cnt in line_counts.items() if cnt >= repeat_threshold}

    # Pass 2 – ekstrak teks bersih
    pages_dict = {}
    with pdfplumber.open(pdf_file_obj) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            if page_num in exclude_pages:
                continue
            printed_num = detect_printed_page_number(
                page, page_num, header_margin, footer_margin)
            h, w  = page.height, page.width
            words = page.crop(
                (0, header_margin, w, h - footer_margin)).extract_words()
            page_text   = " ".join(w["text"] for w in words)
            clean_lines = [ln for ln in page_text.split('\n')
                           if ln.strip() not in boilerplate]
            page_clean  = clean_text(" ".join(clean_lines))
            if page_clean:
                pages_dict[printed_num] = page_clean

    return pages_dict


# ─────────────────────────────────────────────
# 3. CLEANING & NORMALISASI
# ─────────────────────────────────────────────
def split_merged_words(text, max_word_len=15):
    words  = text.split()
    result = []
    for w in words:
        if len(w) > max_word_len:
            result.extend(wordninja.split(w))
        else:
            result.append(w)
    return " ".join(result)


def clean_text(text):
    text = text.lower()
    text = re.sub(r'\b\d+\b', ' ', text)
    text = re.sub(r'[^a-z0-9\s\.\-]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = split_merged_words(text)
    return text.strip()


def normalize_keyword(kw):
    kw = kw.lower()
    kw = re.sub(r'[^a-z0-9\s\-]', ' ', kw)
    kw = re.sub(r'\s+', ' ', kw).strip()
    return kw


# ─────────────────────────────────────────────
# 4. KEYBERT SCORING (PER HALAMAN + CHUNKING)
# ─────────────────────────────────────────────
def process_keywords_by_pages(pages_dict, kw_model,
                               chunk_size=CHUNK_SIZE):
    """
    Menjalankan KeyBERT per chunk halaman dan menggabungkan skor.
    """
    keyword_scores = {}
    keyword_freqs  = Counter()

    for printed_num, text in pages_dict.items():
        words  = text.split()
        chunks = [" ".join(words[i:i + chunk_size])
                  for i in range(0, len(words), chunk_size)]
        for chunk in chunks:
            keywords = kw_model.extract_keywords(
                chunk,
                keyphrase_ngram_range=(MIN_WORDS, MAX_WORDS),
                stop_words=None,
                top_n=20
            )
            for kw, score in keywords:
                cnt = max(chunk.lower().count(kw.lower()), 1)
                keyword_freqs[kw] += cnt
                if kw not in keyword_scores or score > keyword_scores[kw]:
                    keyword_scores[kw] = score

    final_scores = {}
    for kw, max_score in keyword_scores.items():
        freq = keyword_freqs.get(kw, 1)
        final_scores[kw] = max_score * (1 + math.log10(freq))

    return sorted(final_scores.items(), key=lambda x: x[1], reverse=True)


# ─────────────────────────────────────────────
# 5. POS TAGGING – NOUN PHRASE FILTER (STANZA)
# ─────────────────────────────────────────────
def get_phrase_tag(kw, nlp_pipeline):
    doc = nlp_pipeline(kw)
    words_data = [(w.text, w.upos)
                  for sent in doc.sentences for w in sent.words]
    if not words_data:
        return False, "UNKNOWN"
    tags = [upos for _, upos in words_data]
    if tags[0] in ('NOUN', 'PROPN'):
        invalid = {'VERB', 'CCONJ', 'SCONJ', 'ADP', 'PRON'}
        found   = [t for t in invalid if t in tags]
        if not found:
            return True, "Noun Phrase (NP)"
        return False, f"Bukan NP ({found})"
    if 'VERB' in tags:
        return False, "Verb Phrase (VP)"
    if tags[0] == 'ADJ':
        return False, "Adjective Phrase (ADJP)"
    if tags[0] == 'ADV':
        return False, "Adverbial Phrase (ADVP)"
    return False, f"Other ({tags})"


# ─────────────────────────────────────────────
# 6. REDUNDANCY FILTERING (JACCARD)
# ─────────────────────────────────────────────
def jaccard_similarity(a, b):
    sa, sb = set(a.split()), set(b.split())
    union   = sa | sb
    return len(sa & sb) / len(union) if union else 0


def redundancy_filtering(keywords, threshold=SIMILARITY_THRESHOLD):
    final = []
    seen  = set()
    for kw, score, tag in keywords:
        if any(len(w) > 20 for w in kw.split()):
            continue
        if kw in seen:
            continue
        if any(jaccard_similarity(kw, prev) >= threshold for prev, _, _ in final):
            continue
        final.append((kw, score, tag))
        seen.add(kw)
    return final


# ─────────────────────────────────────────────
# 7. PENCARIAN HALAMAN KATA KUNCI
# ─────────────────────────────────────────────
def find_keyword_pages(keyword, pages_dict):
    norm_kw = normalize_keyword(keyword)
    matched = []
    for printed_num, text in pages_dict.items():
        if re.search(r'\b' + re.escape(norm_kw) + r'\b', text):
            try:
                matched.append(int(printed_num))
            except ValueError:
                matched.append(printed_num)
    return sorted(set(matched), key=lambda x: (isinstance(x, str), x))


# ─────────────────────────────────────────────
# 8. PIPELINE UTAMA – dipanggil dari UI
# ─────────────────────────────────────────────
def load_models():
    """Muat Stanza & KeyBERT (hanya sekali, di-cache oleh Streamlit)."""
    stanza.download("id", verbose=False)
    nlp = stanza.Pipeline("id", processors="tokenize,pos", verbose=False)
    kw_model = KeyBERT("paraphrase-multilingual-MiniLM-L12-v2")
    return nlp, kw_model


def run_extraction(pdf_bytes, top_n, nlp, kw_model,
                   progress_callback=None):
    """
    Menjalankan pipeline lengkap.
    progress_callback(step: int, total: int, msg: str) – opsional.

    Mengembalikan list of dict:
      [{"keyword": str, "score": float, "pages": str}, ...]
    Kini otomatis melewati (skip) kata kunci jika halamannya tidak ditemukan.
    """
    import io

    def _prog(step, total, msg):
        if progress_callback:
            progress_callback(step, total, msg)

    _prog(1, 5, "Mengekstrak teks dari PDF...")
    pages_dict = extract_text_by_page(io.BytesIO(pdf_bytes))

    _prog(2, 5, "Menjalankan KeyBERT...")
    raw_ranked = process_keywords_by_pages(pages_dict, kw_model)

    _prog(3, 5, "Memfilter Noun Phrase dengan Stanza...")
    phrase_candidates = []
    for kw, score in raw_ranked:
        is_np, label = get_phrase_tag(kw, nlp)
        if is_np:
            phrase_candidates.append((kw, score, label))

    _prog(4, 5, "Menghapus duplikat (Jaccard)...")
    filtered = redundancy_filtering(phrase_candidates)[:top_n + 10]  # buffer ekstra agar hasil akhir tetap top_n

    _prog(5, 5, "Memetakan halaman...")
    results = []
    for kw, score, _ in filtered:
        pages = find_keyword_pages(kw, pages_dict)
        
        # 1. Bersihkan elemen list dari karakter kosong atau strip bawaan pencarian
        pages = [p for p in pages if str(p).strip() and str(p).strip() != "-"]
        
        # 2. FILTER UTAMA: Jika setelah dibersihkan list-nya kosong, LANGSUNG SKIP!
        if not pages:
            continue
            
        # 3. Gabungkan nomor halaman menjadi string koma
        pages_str = ", ".join(map(str, pages))
        
        # 4. Filter lapisan terakhir: amankan jika string halaman entah bagaimana jadi kosong/strip
        if not pages_str.strip() or pages_str == "-":
            continue

        results.append({
            "keyword": kw,
            "score"  : round(score, 4),
            "pages"  : pages_str,
        })

    # Batasi ke top_n sebelum diurutkan (buffer sudah terpakai untuk antisipasi keyword tanpa halaman)
    results = results[:top_n]

    # Mengurutkan hasil berdasarkan abjad (A-Z) pada 'keyword'
    results.sort(key=lambda x: x["keyword"])

    return results