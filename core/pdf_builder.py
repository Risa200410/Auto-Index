"""
=====================================================================
AutoIndex - core/pdfbuilder.py
Membuat halaman indeks baru dengan ReportLab lalu
menggabungkannya ke PDF asli menggunakan PyMuPDF (fitz).
=====================================================================
"""

import io
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# ─────────────────────────────────────────────
# BUAT HALAMAN INDEKS (REPORTLAB → BytesIO)
# ─────────────────────────────────────────────
def build_index_pdf(keywords_with_pages: list[dict]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()
    W, H = A4

    # ── Style kustom ──────────────────────────────────────────────
    title_style = ParagraphStyle(
        "IndexTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "IndexSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        spaceAfter=14,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    letter_style = ParagraphStyle(
        "LetterHeader",
        parent=styles["Normal"],
        fontSize=12,
        textColor=colors.HexColor("#1a1a2e"),
        fontName="Helvetica-Bold",
        spaceBefore=8,  
        spaceAfter=4,
    )
    entry_style = ParagraphStyle(
        "IndexEntry",
        parent=styles["Normal"],
        fontSize=9.5,
        textColor=colors.HexColor("#222222"),
        fontName="Helvetica",
        leading=14,
        alignment=TA_LEFT,
    )
    # Style khusus untuk kolom nomor halaman -> tetap rata kiri
    page_entry_style = ParagraphStyle(
        "PageEntry",
        parent=styles["Normal"],
        fontSize=9.5,
        textColor=colors.HexColor("#222222"),
        fontName="Helvetica",
        leading=14,
        alignment=TA_LEFT,
    )

    # ── Urutkan A-Z ──────────────────────────────────────────────
    sorted_kws = sorted(keywords_with_pages, key=lambda x: x["keyword"].lower())

    # Kelompokkan per huruf awal
    groups: dict[str, list] = {}
    for item in sorted_kws:
        letter = item["keyword"][0].upper() if item["keyword"] else "#"
        groups.setdefault(letter, []).append(item)

    # ── Bangun flowable ───────────────────────────────────────────
    story = [
        Paragraph("INDEKS", title_style),
        # Paragraph(f"Total {len(sorted_kws)} kata kunci diekstrak secara otomatis", subtitle_style),
        HRFlowable(width="100%", thickness=1,
                   color=colors.HexColor("#1a1a2e"), spaceAfter=10),
    ]

    # Lebar kolom: kolom keyword diperkecil supaya kolom halaman geser ke kiri (lebih dekat ke kata kunci)
    colw = [(W - 5 * cm) * 0.40, (W - 5 * cm) * 0.60]

    for letter in sorted(groups.keys()):
        story.append(Paragraph(letter, letter_style))

        # ── GARIS ABU-ABU DI BAWAH HURUF ABJAD SUDAH DIHAPUS DI SINI ──

        # Buat tabel 2 kolom (keyword | halaman) per kelompok huruf
        table_data = []
        for item in groups[letter]:
            kw = item["keyword"].capitalize()
            pages = item["pages"]
            table_data.append([
                Paragraph(kw, entry_style),
                Paragraph(pages, page_entry_style),  # rata tengah
            ])

        tbl = Table(table_data, colWidths=colw)

        # ── MODIFIKASI TABLE STYLE: Menghapus LINEBELOW abu-abu ──
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),  # Ditambah sedikit padding agar spasi antar kata kustom tetap lega
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4))

    doc.build(story)
    return buffer.getvalue()


# ─────────────────────────────────────────────
# GABUNGKAN HALAMAN INDEKS KE PDF ASLI
# ─────────────────────────────────────────────
def merge_index_to_pdf(original_pdf_bytes: bytes,
                        index_pdf_bytes: bytes) -> bytes:
   
    orig_doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    index_doc = fitz.open(stream=index_pdf_bytes, filetype="pdf")
    orig_doc.insert_pdf(index_doc)
    merged_bytes = orig_doc.write()
    orig_doc.close()
    index_doc.close()
    return merged_bytes