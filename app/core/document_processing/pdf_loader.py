"""PDF document loading and text extraction utilities."""

import logging
from pathlib import Path
from typing import Optional

from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


class PDFLoader:
    """PDF dosyasından metin çıkarma sınıfı."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_pdf(self, filepath: str) -> str:
        """
        PDF dosyasından metin çıkarır.

        Args:
            filepath: PDF dosya yolu

        Returns:
            Çıkarılan metin

        Raises:
            FileNotFoundError: Dosya bulunamazsa
            Exception: PDF işleme hatası
        """
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")

        try:
            self.logger.info(f"Loading PDF: {filepath}")

            reader = PdfReader(filepath)
            text = ""

            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():
                    text += f"\n=== Sayfa {page_num} ===\n{page_text}\n"

            self.logger.info(f"Extracted {len(text)} characters from {len(reader.pages)} pages")
            return text

        except Exception as e:
            self.logger.error(f"Error loading PDF {filepath}: {e}")
            raise

    def get_page_count(self, filepath: str) -> int:
        """PDF dosyasındaki sayfa sayısını döndürür."""
        reader = PdfReader(filepath)
        return len(reader.pages)

    def extract_text_with_metadata(self, filepath: str) -> dict:
        """
        Metin ile birlikte metadata çıkarır.

        Returns:
            {
                "text": str,
                "page_count": int,
                "file_size": int
            }
        """
        text = self.load_pdf(filepath)
        page_count = self.get_page_count(filepath)
        file_size = Path(filepath).stat().st_size

        return {
            "text": text,
            "page_count": page_count,
            "file_size": file_size
        }