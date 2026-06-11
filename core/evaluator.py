# =====================================================================
# AutoIndex - core/evaluator.py
# Modul untuk pengujian Precision & Recall (Exact Match & Fuzzy Match)
# =====================================================================

import io
import re
import pdfplumber
from difflib import SequenceMatcher

def string_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def fuzzy_match(keyword, truth_set, threshold=0.85):
    best_match = None
    best_score = 0
    for truth_kw in truth_set:
        score = string_similarity(keyword, truth_kw)
        if score > best_score:
            best_score = score
            best_match = truth_kw
    if best_score >= threshold:
        return best_match, best_score
    return None, best_score

def extract_index_from_pdf_bytes(pdf_bytes):
    index_keywords = set()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')
            for line in lines:
                clean_line = re.sub(r'\d+', '', line).strip()
                parts = re.split(r'[,;]', clean_line)
                for pt in parts:
                    pt = pt.strip().lower()
                    pt = re.sub(r'[^a-z\s\-]', ' ', pt).strip()
                    pt = re.sub(r'\s+', ' ', pt)
                    if pt and 1 <= len(pt.split()) <= 5 and len(pt) > 1:
                        index_keywords.add(pt)
    return sorted(list(index_keywords))

def calculate_metrics_dual(extracted_keywords, ground_truth, fuzzy_threshold=0.85):
    """
    Menghitung evaluasi Exact Match dan Fuzzy Match.
    extracted_keywords: list of dicts [{"keyword": ...}] atau struktur lain
    ground_truth: list of strings (ground truth keywords)
    """
    from core.extractor import normalize_keyword

    if isinstance(extracted_keywords, list) and len(extracted_keywords) > 0:
        if isinstance(extracted_keywords[0], dict):
            extracted_set = set([normalize_keyword(item["keyword"]) for item in extracted_keywords])
        elif isinstance(extracted_keywords[0], tuple):
            extracted_set = set([normalize_keyword(item[0]) for item in extracted_keywords])
        else:
            extracted_set = set([normalize_keyword(str(item)) for item in extracted_keywords])
    else:
        extracted_set = set()

    truth_set = set([normalize_keyword(kw) for kw in ground_truth if kw.strip()])

    # Exact Match
    match_keywords_exact = extracted_set.intersection(truth_set)
    tp_exact = len(match_keywords_exact)
    precision_exact = tp_exact / len(extracted_set) if extracted_set else 0.0
    recall_exact    = tp_exact / len(truth_set)     if truth_set     else 0.0
    f1_exact = (2 * precision_exact * recall_exact / (precision_exact + recall_exact) if (precision_exact + recall_exact) > 0 else 0.0)

    # Fuzzy Match
    fuzzy_matches = {} 
    for kw in extracted_set:
        match, score = fuzzy_match(kw, truth_set, threshold=fuzzy_threshold)
        if match:
            fuzzy_matches[kw] = (match, score)

    tp_fuzzy = len(fuzzy_matches)
    precision_fuzzy = tp_fuzzy / len(extracted_set) if extracted_set else 0.0
    
    matched_gt_by_fuzzy = set([gt for gt, _ in fuzzy_matches.values()])
    recall_fuzzy    = len(matched_gt_by_fuzzy) / len(truth_set) if truth_set else 0.0
    f1_fuzzy = (2 * precision_fuzzy * recall_fuzzy / (precision_fuzzy + recall_fuzzy) if (precision_fuzzy + recall_fuzzy) > 0 else 0.0)

    fp_exact = sorted(list(extracted_set - match_keywords_exact))
    fn_exact = sorted(list(truth_set - match_keywords_exact))

    fp_fuzzy = sorted(list(extracted_set - set(fuzzy_matches.keys())))
    fn_fuzzy = sorted(list(truth_set - matched_gt_by_fuzzy))

    return {
        "exact": {
            "precision": precision_exact,
            "recall": recall_exact,
            "f1": f1_exact,
            "fp": fp_exact,
            "fn": fn_exact,
            "tp": sorted(list(match_keywords_exact))
        },
        "fuzzy": {
            "precision": precision_fuzzy,
            "recall": recall_fuzzy,
            "f1": f1_fuzzy,
            "fp": fp_fuzzy,
            "fn": fn_fuzzy,
            "matches": fuzzy_matches,
            "tp": sorted(list(matched_gt_by_fuzzy))
        }
    }
