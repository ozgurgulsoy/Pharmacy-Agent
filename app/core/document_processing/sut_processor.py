"""SUT document processing pipeline."""

import logging
from typing import List, Dict, Any, Optional

from .pdf_loader import PDFLoader
from .chunker import SUTDocumentChunker
from .embeddings import EmbeddingGenerator
from models.eligibility import Chunk
from config.settings import SUT_PDF_PATH, EMBEDDING_PROVIDER

logger = logging.getLogger(__name__)


class SUTDocumentProcessor:
    """SUT doküman işleme pipeline'ı."""

    def __init__(self, openai_client=None, provider: str = EMBEDDING_PROVIDER):
        self.pdf_loader = PDFLoader()
        self.chunker = SUTDocumentChunker()
        self.embedding_generator = EmbeddingGenerator(client=openai_client, provider=provider)
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_document(self, pdf_path: str = SUT_PDF_PATH) -> List[Dict[str, Any]]:
        """
        SUT dokümanını işler ve embedding'leri oluşturur.

        Args:
            pdf_path: PDF dosya yolu

        Returns:
            FAISS için hazır embedding verileri
        """
        self.logger.info("Starting SUT document processing pipeline")

        try:
            # 1. PDF'den metin çıkar
            self.logger.info("Step 1: Extracting text from PDF")
            text = self.pdf_loader.load_pdf(pdf_path)

            # 2. Dokümanı chunk'lara böl
            self.logger.info("Step 2: Chunking document")
            chunks = self.chunker.chunk_document(text)

            # 3. Embedding'ler oluştur
            self.logger.info("Step 3: Creating embeddings")
            embeddings_data = self.embedding_generator.create_embeddings(chunks)

            self.logger.info(f"Successfully processed {len(embeddings_data)} chunks")
            return embeddings_data

        except Exception as e:
            self.logger.error(f"Error in document processing pipeline: {e}")
            raise

    def load_and_chunk(self, pdf_path: str = SUT_PDF_PATH) -> List[Chunk]:
        """
        Sadece yükleme ve chunking yapar (embedding olmadan).

        Returns:
            Chunk listesi
        """
        text = self.pdf_loader.load_pdf(pdf_path)
        chunks = self.chunker.chunk_document(text)
        return chunks