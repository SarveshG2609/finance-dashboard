from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path: Path, password: str | None = None) -> list[str]:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        if not password:
            raise ValueError("PDF is encrypted and requires a password.")
        result = reader.decrypt(password)
        if not result:
            raise ValueError("Invalid PDF password.")

    return [page.extract_text() or "" for page in reader.pages]
