# =====================================================================
# POS (Stanza) + KeyBERT Keyword Extraction — Modul Ekstraktor Bersih
# Bahasa Indonesia | Frasa 1–3 Kata | Input: path file PDF / BytesIO
# =====================================================================

import pdfplumber
import stanza
import re
import wordninja
import math
import io
from keybert import KeyBERT
from collections import Counter
from difflib import SequenceMatcher

# ─────────────────────────────────────────────────────────────────────
# KONFIGURASI DEFAULT
# ─────────────────────────────────────────────────────────────────────
TOP_N = None  
MIN_WORDS = 1
MAX_WORDS = 3

HEADER_MARGIN = 50
FOOTER_MARGIN = 50
SIMILARITY_THRESHOLD = 0.6    
FUZZY_THRESHOLD = 0.85   

INVALID_NP_POS = {"VERB", "CCONJ", "SCONJ", "ADP", "PRON"}
HEAD_POS = {"NOUN", "PROPN"}


# =====================================================================
# BAGIAN 1 — EKSTRAKSI TEKS PDF (PER HALAMAN + NOMOR CETAK)
# =====================================================================

def detect_printed_page_number(page, physical_num, header_margin=50, footer_margin=50):
    """
    Membaca angka di area header/footer untuk menemukan nomor halaman
    yang sebenarnya tercetak di buku (bukan urutan fisik PDF).
    """
    h, w = page.height, page.width
    header_text = (page.crop((0, 0, w, header_margin)).extract_text() or "")
    footer_text = (page.crop((0, h - footer_margin, w, h)).extract_text() or "")
    combined = footer_text.strip() + "\n" + header_text.strip()
    numbers = re.findall(r'\b\d+\b', combined)
    if numbers:
        return sorted(numbers, key=len)[0]   
    return str(physical_num)


def extract_text_by_page(pdf_path, exclude_pages=None,
                          header_margin=HEADER_MARGIN,
                          footer_margin=FOOTER_MARGIN,
                          repeat_threshold=5):
    """
    Mengekstrak teks bersih per halaman dari PDF (input: path string atau BytesIO).
    Mengembalikan dict {printed_page_num: clean_text}.
    """
    if exclude_pages is None:
        exclude_pages = []

    all_lines = []
    
    # Pendekatan fleksibel untuk handle string path maupun io.BytesIO
    if isinstance(pdf_path, io.BytesIO):
        pdf_file = pdf_path
    else:
        pdf_file = pdf_path

    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            if (i + 1) in exclude_pages:
                continue
            h, w = page.height, page.width
            page_text = page.crop((0, header_margin, w, h - footer_margin)).extract_text() or ""
            for line in page_text.split('\n'):
                if line.strip():
                    all_lines.append(line.strip())

    line_counts = Counter(all_lines)
    boilerplate = {ln for ln, cnt in line_counts.items() if cnt >= repeat_threshold}

    pages_dict = {}
    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            phys_num = i + 1
            if phys_num in exclude_pages:
                continue
            printed_num = detect_printed_page_number(page, phys_num, header_margin, footer_margin)
            h, w = page.height, page.width
            words = page.crop((0, header_margin, w, h - footer_margin)).extract_words()
            page_text = " ".join(word["text"] for word in words)
            clean_lines = [ln for ln in page_text.split('\n') if ln.strip() not in boilerplate]
            page_clean = clean_text(" ".join(clean_lines))
            if page_clean:
                pages_dict[printed_num] = page_clean

    return pages_dict


# =====================================================================
# BAGIAN 2 — CLEANING & NORMALISASI
# =====================================================================

def split_merged_words(text, max_word_len=15):
    words = text.split()
    result = []
    for w in words:
        result.extend(wordninja.split(w) if len(w) > max_word_len else [w])
    return " ".join(result)


def clean_text(text):
    text = text.lower()
    text = re.sub(r'\(cid:\d+\)', ' ', text)   
    text = re.sub(r'\bcid\b', ' ', text)       
    text = re.sub(r'\b\d+\b', ' ', text)       
    text = re.sub(r'[^a-z\s\-]', ' ', text)     
    text = re.sub(r'\s+', ' ', text)
    text = split_merged_words(text)
    return text.strip()


def normalize_keyword(kw):
    kw = kw.lower()
    kw = re.sub(r'[^a-z0-9\s\-]', ' ', kw)
    kw = re.sub(r'\s+', ' ', kw).strip()
    return kw


def extract_index_from_separate_file(index_pdf_path, index_pages):
    index_keywords = set()
    with pdfplumber.open(index_pdf_path) as pdf:
        total = len(pdf.pages)
        for page_num in index_pages:
            if not (1 <= page_num <= total):
                continue
            text = pdf.pages[page_num - 1].extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                clean_line = re.sub(r'\d+', '', line).strip()
                for pt in re.split(r'[,;]', clean_line):
                    pt = re.sub(r'[^a-z\s\-]', ' ', pt.strip().lower()).strip()
                    pt = re.sub(r'\s+', ' ', pt)
                    if pt and 1 <= len(pt.split()) <= 5 and len(pt) > 1:
                        index_keywords.add(pt)
    return list(index_keywords)


# =====================================================================
# BAGIAN 3 — KEYBERT SCORING (PER HALAMAN + CHUNKING)
# =====================================================================

def process_keywords_by_pages(pages_dict, kw_model, chunk_size=100):
    keyword_scores = {}
    keyword_freqs = Counter()

    for printed_num, text in pages_dict.items():
        words = text.split()
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        for chunk in chunks:
            kws = kw_model.extract_keywords(
                chunk,
                keyphrase_ngram_range=(MIN_WORDS, MAX_WORDS),
                stop_words=None,
                top_n=50
            )
            for kw, score in kws:
                cnt = max(chunk.lower().count(kw.lower()), 1)
                keyword_freqs[kw] += cnt
                if kw not in keyword_scores or score > keyword_scores[kw]:
                    keyword_scores[kw] = score

    final_scores = {
        kw: score * (1 + math.log10(keyword_freqs.get(kw, 1)))
        for kw, score in keyword_scores.items()
    }
    return sorted(final_scores.items(), key=lambda x: x[1], reverse=True)


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


# =====================================================================
# BAGIAN 4 — POS FILTERING STANZA (BATCH, HEAD-FIRST BI)
# =====================================================================

def load_stanza_pipeline():
    kwargs = dict(lang="id", processors="tokenize,pos", tokenize_pretokenized=True, verbose=False)
    try:
        return stanza.Pipeline(**kwargs)
    except Exception:
        stanza.download("id", verbose=False)
        return stanza.Pipeline(**kwargs)


def load_models():
    nlp = load_stanza_pipeline()
    kw_model = KeyBERT("paraphrase-multilingual-MiniLM-L12-v2")
    return nlp, kw_model


def batch_pos_tags(phrases, nlp):
    pretokenized = [phrase.split() for phrase in phrases]
    doc = nlp(pretokenized)
    return [[word.upos for word in sent.words] for sent in doc.sentences]


def classify_noun_phrase(tags):
    if not tags:
        return False, "UNKNOWN (tag kosong)"
    if tags[0] in HEAD_POS:
        found_invalid = [t for t in tags if t in INVALID_NP_POS]
        if not found_invalid:
            return True, "Noun Phrase (NP)"
        return False, f"Bukan NP (mengandung {found_invalid})"
    if "VERB" in tags:
        return False, "Verb Phrase (VP)"
    if tags[0] == "ADJ":
        return False, "Adjective Phrase (ADJP)"
    if tags[0] == "ADV":
        return False, "Adverbial Phrase (ADVP)"
    return False, f"Other Phrase (tags: {tags})"


def filter_noun_phrases_batch(keywords, nlp, batch_size=500):
    valid_input = []
    pre_rejected = []
    for kw, score in keywords:
        tokens = kw.split()
        if all(len(w) <= 2 for w in tokens):
            pre_rejected.append((kw, score, "Artefak (semua token ≤2 huruf)"))
        else:
            valid_input.append((kw, score))

    phrases = [kw for kw, _ in valid_input]
    all_tags = []
    for i in range(0, len(phrases), batch_size):
        batch = phrases[i:i + batch_size]
        all_tags.extend(batch_pos_tags(batch, nlp))

    passed = []
    rejected = list(pre_rejected)

    for (kw, score), tags in zip(valid_input, all_tags):
        is_np, label = classify_noun_phrase(tags)
        if is_np:
            passed.append((kw, score, label))
        else:
            rejected.append((kw, score, label))

    return passed, rejected


# =====================================================================
# BAGIAN 5 — REDUNDANCY FILTERING (JACCARD)
# =====================================================================

def jaccard_similarity(a, b):
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0


def redundancy_filtering(keywords, similarity_threshold=SIMILARITY_THRESHOLD):
    final = []
    seen = set()

    for kw, score, label in keywords:
        if any(len(w) > 20 for w in kw.split()):
            continue
        if kw in seen:
            continue
        if any(jaccard_similarity(kw, prev) >= similarity_threshold for prev, _, _ in final):
            continue
        final.append((kw, score, label))
        seen.add(kw)

    return final


# =====================================================================
# BAGIAN 6 — EVALUASI & METRIK (SILENT)
# =====================================================================

def string_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def fuzzy_match(keyword, truth_set, threshold):
    best_match, best_score = None, 0
    for truth_kw in truth_set:
        score = string_similarity(keyword, truth_kw)
        if score > best_score:
            best_score = score
            best_match = truth_kw
        if best_score >= threshold:
            return best_match, best_score
    return (best_match if best_score >= threshold else None), best_score


def _run_fuzzy(extracted_set, truth_set, threshold):
    matches = {}
    unmatched = set()
    for kw in extracted_set:
        match, score = fuzzy_match(kw, truth_set, threshold)
        if match:
            matches[kw] = (match, score)
        else:
            unmatched.add(kw)
    tp = len(matches)
    precision = tp / len(extracted_set) if extracted_set else 0.0
    matched_gt = {gt for gt, _ in matches.values()}
    recall = len(matched_gt) / len(truth_set) if truth_set else 0.0
    f1 = (2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0)
    return precision, recall, f1, matches, unmatched, matched_gt


def delta_pos_vs_ground_truth(rejected, ground_truth, fuzzy_threshold=0.85):
    truth_set = {normalize_keyword(kw) for kw in ground_truth if kw.strip()}
    rejected_norm = [(normalize_keyword(kw), score, reason) for kw, score, reason in rejected]

    exact_lost = [(kw, score, reason) for kw, score, reason in rejected_norm if kw in truth_set]
    exact_lost_set = {kw for kw, _, _ in exact_lost}
    fuzzy_lost = []
    for kw, score, reason in rejected_norm:
        if kw in exact_lost_set:
            continue
        match, fscore = fuzzy_match(kw, truth_set, fuzzy_threshold)
        if match:
            fuzzy_lost.append((kw, score, reason, match, fscore))

    return {"exact_lost": exact_lost, "fuzzy_lost": fuzzy_lost}


def calculate_metrics(extracted_keywords, ground_truth):
    extracted_set = {normalize_keyword(kw) for kw, _, _ in extracted_keywords}
    truth_set = {normalize_keyword(kw) for kw in ground_truth if kw.strip()}

    exact_match = extracted_set & truth_set
    tp_e = len(exact_match)
    prec_e = tp_e / len(extracted_set) if extracted_set else 0.0
    rec_e = tp_e / len(truth_set) if truth_set else 0.0
    f1_e = (2 * prec_e * rec_e / (prec_e + rec_e) if (prec_e + rec_e) > 0 else 0.0)

    return prec_e, rec_e, f1_e


# =====================================================================
# BAGIAN INTERFACE UTAMA UNTUK STREAMLIT
# =====================================================================

def run_extraction(pdf_bytes, top_n, nlp, kw_model, progress_callback=None):
    """Run pipeline from PDF bytes (used by Streamlit UI) without print clutter."""
    
    def _prog(step, total, msg):
        if progress_callback:
            progress_callback(step, total, msg)

    _prog(1, 5, "Mengekstrak teks dari PDF...")
    pages_dict = extract_text_by_page(io.BytesIO(pdf_bytes))

    _prog(2, 5, "Menjalankan KeyBERT...")
    raw_ranked = process_keywords_by_pages(pages_dict, kw_model)

    _prog(3, 5, "Memfilter Noun Phrase dengan Stanza...")
    passed, rejected = filter_noun_phrases_batch(raw_ranked, nlp)

    _prog(4, 5, "Menghapus duplikat (Jaccard)...")
    filtered = redundancy_filtering(passed)

    _prog(5, 5, "Memetakan halaman...")
    results = []
    for kw, score, _ in filtered:
        pages = find_keyword_pages(kw, pages_dict)
        pages = [p for p in pages if str(p).strip() and str(p).strip() != "-"]
        if not pages:
            continue
        pages_str = ", ".join(map(str, pages))
        if not pages_str.strip() or pages_str == "-":
            continue
        results.append({
            "keyword": kw,
            "score": round(score, 4),
            "pages": pages_str,
        })

    top_n = top_n or len(results)
    results = results[:top_n]
    results.sort(key=lambda x: x["keyword"])
    return results