from __future__ import annotations

from pathlib import Path
from typing import List

import fitz

from .utils import ensure_dir


def rasterize_pdf(pdf_path: Path, output_dir: Path, zoom: float = 2.0) -> List[Path]:
    ensure_dir(output_dir)
    doc = fitz.open(pdf_path)
    image_paths: List[Path] = []
    matrix = fitz.Matrix(zoom, zoom)

    for idx, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        out_path = output_dir / f"slide_{idx:03d}.png"
        pix.save(out_path)
        image_paths.append(out_path)

    doc.close()
    return image_paths


def extract_page_text(pdf_path: Path) -> List[str]:
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        texts.append(page.get_text("text").strip())
    doc.close()
    return texts
