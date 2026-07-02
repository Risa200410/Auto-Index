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



# BUAT HALAMAN INDEKS (Ukurannya dinamis mengikuti target_size)
def build_index_pdf(keywords_with_pages: list[dict], target_size: tuple[float, float]) -> bytes:
    buffer = io.BytesIO()
    
    # Ambil lebar (W) dan tinggi (H) asli dari PDF utama
    W, H = target_size
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(W, H),
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()

    #  Style kustom 
    title_style = ParagraphStyle(
        "IndexTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
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
    page_entry_style = ParagraphStyle(
        "PageEntry",
        parent=styles["Normal"],
        fontSize=9.5,
        textColor=colors.HexColor("#222222"),
        fontName="Helvetica",
        leading=14,
        alignment=TA_LEFT,
    )

    #  Urutkan A-Z 
    sorted_kws = sorted(keywords_with_pages, key=lambda x: x["keyword"].lower())

    groups: dict[str, list] = {}
    for item in sorted_kws:
        letter = item["keyword"][0].upper() if item["keyword"] else "#"
        groups.setdefault(letter, []).append(item)

    #  Bangun flowable 
    story = [
        Paragraph("INDEKS", title_style),
        HRFlowable(width="100%", thickness=1,
                   color=colors.HexColor("#1a1a2e"), spaceAfter=10),
    ]

    # Hitung lebar sisa halaman setelah dikurangi margin kiri-kanan
    available_width = W - (4.0 * cm)
    
    # UBAH BARIS INI: 
    # Berikan ruang kata kunci 40% saja agar nomor halaman langsung maju ke kiri
    colw = [available_width * 0.40, available_width * 0.60]

    for letter in sorted(groups.keys()):
        story.append(Paragraph(letter, letter_style))

        table_data = []
        for item in groups[letter]:
            kw = item["keyword"].capitalize()
            pages = item["pages"]
            table_data.append([
                Paragraph(kw, entry_style),
                Paragraph(pages, page_entry_style),
            ])

        tbl = Table(table_data, colWidths=colw)
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4))

    doc.build(story)
    return buffer.getvalue()


#
# PROSES UTAMA: AMBIL UKURAN DAN GABUNGKAN
def merge_index_to_pdf(original_pdf_bytes: bytes, keywords_with_pages: list[dict]) -> bytes:
    orig_doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    
    # 1. Dapatkan ukuran (width, height) dari halaman terakhir PDF asli
    last_page = orig_doc[-1]
    original_size = (last_page.rect.width, last_page.rect.height)
    
    # 2. Buat PDF indeks di ReportLab dengan ukuran yang sudah disesuaikan tadi
    index_bytes = build_index_pdf(keywords_with_pages, original_size)
    
    # 3. Buka halaman indeks yang baru dibuat, lalu gabungkan ke PDF asli
    index_doc = fitz.open(stream=index_bytes, filetype="pdf")
    
    # Jika halaman asli ada rotasi, samakan rotasinya
    if last_page.rotation:
        for page in index_doc:
            page.set_rotation(last_page.rotation)
            
    orig_doc.insert_pdf(index_doc)
    
    merged_bytes = orig_doc.write()
    orig_doc.close()
    index_doc.close()
    
    return merged_bytes