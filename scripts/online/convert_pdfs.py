#!/usr/bin/env python3
"""Phase 6.5: Convert lesson PDFs to markdown via pdftotext."""
import os
import subprocess

DB_PATH = "/home/peter/Documents/Projects/zolai-ai/data/zolai.db"
PDF_BASE = "/home/peter/Downloads/Kaggle/data/Zolai Lessons"
OUT_DIR = "/home/peter/Documents/Projects/zolai-ai/data/reference/grammar"

# (filename, output_name)
PDF_MAP = [
    # Simbu Tan books → Zolai_Simbu_Tan_khat_sinna.md etc.
    ("zolai-simbu-tan-khat-sinna_compress.pdf", "Zolai_Simbu_Tan_khat_sinna.md"),
    ("zolai-simbu-tan-lang-sinna_compress.pdf", "Zolai_Simbu_Tan_lang_sinna.md"),
    ("zolai-simbu-tan-li-sinna_compress.pdf", "Zolai_Simbu_Tan_li_sinna.md"),
    ("zolai-simbu-tan-nih-sinna_compress.pdf", "Zolai_Simbu_Tan_nih_sinna.md"),
    ("zolai-simbu-tan-thum-sinna_compress.pdf", "Zolai_Simbu_Tan_thum_sinna.md"),
    # Lesson PDFs
    ("Zolai_Standard_Format.pdf", "Zolai_Standard_Format_online.md"),
    ("2_Tone_Sandhi_in_Tedim_Zomi_Toponyms.pdf", "lesson_02_Tone_Sandhi_Tedim_Zomi_Toponyms.md"),
    ("6_Composite_Bibliography.pdf", "lesson_06_Composite_Bibliography.md"),
    ("8_We_Are_Zomis_Poem.pdf", "lesson_08_We_Are_Zomis_Poem.md"),
    ("12_Zolai_Khantohsak_Nang_Hanciamnate_Pa.pdf", "lesson_12_Khantohsak_Hanciamnate_Pa.md"),
    ("13_Zomi_Nam_Ni_Vai_Dawnna.pdf", "lesson_13_Zomi_Nam_Ni_Vai_Dawnna.md"),
    ("16_Zolai_Picinsak_Ding_Hanciam_Huai.pdf", "lesson_16_Picinsak_Hanciam_Huai.md"),
    ("18_Lia_le_Taang_Vai_01.pdf", "lesson_18_Lia_le_Taang_Vai_01.md"),
    ("19_Lia_leh_Taang_Vai_02A.pdf", "lesson_19_Lia_leh_Taang_Vai_02A.md"),
    ("20_Lia_leh_Taang_Vai_02B.pdf", "lesson_20_Lia_leh_Taang_Vai_02B.md"),
]


def convert_pdf(pdf_path: str, out_path: str) -> bool:
    """Convert a single PDF to markdown via pdftotext."""
    if not os.path.isfile(pdf_path):
        print(f"  SKIP (not found): {pdf_path}")
        return False
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"  FAIL (pdftotext exit {result.returncode}): {pdf_path}")
        print(f"    stderr: {result.stderr.strip()[:200]}")
        return False
    text = result.stdout.strip()
    if not text:
        print(f"  SKIP (empty output): {pdf_path}")
        return False
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return True


def convert_all() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Converting {len(PDF_MAP)} PDFs → {OUT_DIR}")
    converted = 0
    skipped = 0
    for pdf_name, out_name in PDF_MAP:
        pdf_path = os.path.join(PDF_BASE, pdf_name)
        out_path = os.path.join(OUT_DIR, out_name)
        ok = convert_pdf(pdf_path, out_path)
        if ok:
            size = os.path.getsize(out_path)
            print(f"  ✓ {out_name} ({size:,} bytes)")
            converted += 1
        else:
            skipped += 1
    print(f"\nConverted: {converted}, Skipped: {skipped}")


if __name__ == "__main__":
    convert_all()
