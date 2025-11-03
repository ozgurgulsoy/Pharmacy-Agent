#!/usr/bin/env python3
"""
SUT document indexing script for FAISS.
This script processes the SUT PDF, creates chunks, generates embeddings, and indexes them.
"""

import logging
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from openai import OpenAI

from app.config.settings import (
    OPENAI_API_KEY, 
    EMBEDDING_DIMENSION, 
    EMBEDDING_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL
)

# Import modules
from app.core.document_processing.pdf_loader import PDFLoader
from app.core.document_processing.chunker import SUTDocumentChunker
from app.core.document_processing.embeddings import EmbeddingGenerator
from app.core.rag.faiss_store import FAISSVectorStore

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def index_sut_document():
    """Main function to index SUT document."""
    try:
        logger.info("🚀 Starting SUT document indexing process with FAISS")
        logger.info(f"📊 Embedding Provider: {EMBEDDING_PROVIDER}")
        logger.info(f"🔢 Embedding Dimension: {EMBEDDING_DIMENSION}")

        # Initialize OpenAI client (not needed for OpenRouter embeddings)
        openai_client = None
        if EMBEDDING_PROVIDER == "openai":
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        vector_store = FAISSVectorStore()

        # Process document step by step
        logger.info("📄 Step 1: Loading PDF")
        pdf_loader = PDFLoader()
        text = pdf_loader.load_pdf("data/9.5.17229.pdf")

        logger.info("✂️ Step 2: Chunking document")
        chunker = SUTDocumentChunker()
        chunks = chunker.chunk_document(text)

        logger.info(f"🧮 Step 3: Creating embeddings using {EMBEDDING_PROVIDER}")
        embedding_generator = EmbeddingGenerator(client=openai_client)
        embeddings_data = embedding_generator.create_embeddings(chunks)

        # Create and populate FAISS index
        logger.info("🗂️ Step 4: Creating FAISS index")
        vector_store.create_index(dimension=EMBEDDING_DIMENSION)

        logger.info(f"📥 Step 5: Adding {len(embeddings_data)} vectors to FAISS index")
        vector_store.add_embeddings(embeddings_data)

        # Save index to disk
        logger.info("💾 Step 6: Saving FAISS index to disk")
        vector_store.save()

        logger.info("✅ SUT document indexing completed successfully")

        # Display stats
        stats = vector_store.get_stats()
        logger.info(f"📊 Index stats: {stats}")

    except Exception as e:
        logger.error(f"❌ Error during indexing: {e}")
        raise


if __name__ == "__main__":
    index_sut_document()
