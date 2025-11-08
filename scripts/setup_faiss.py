#!/usr/bin/env python3
"""
Multi-document indexing script for FAISS.
This script processes SUT PDF + EK-4 documents, creates chunks, generates embeddings, and indexes them.
"""

import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from openai import OpenAI

from app.config.settings import (
    OPENAI_API_KEY, 
    EMBEDDING_DIMENSION, 
    EMBEDDING_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    SUT_PDF_PATH,
    EK4_DOCUMENTS
)

# Import modules
from app.core.document_processing.pdf_loader import PDFLoader
from app.core.document_processing.chunker import SUTDocumentChunker
from app.core.document_processing.embeddings import EmbeddingGenerator
from app.core.rag.faiss_store import FAISSVectorStore
from app.models.eligibility import Chunk

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_document(
    pdf_path: str,
    doc_type: str,
    doc_source: str,
    pdf_loader: PDFLoader
) -> List[Chunk]:
    """
    Process a single document and return chunks.
    
    Args:
        pdf_path: Path to PDF file
        doc_type: Document type identifier (e.g., "SUT", "EK-4/D")
        doc_source: Source filename
        pdf_loader: PDF loader instance
        
    Returns:
        List of chunks with metadata
    """
    logger.info(f"📄 Loading {doc_type} from {doc_source}")
    text = pdf_loader.load_pdf(pdf_path)
    
    logger.info(f"✂️ Chunking {doc_type} document")
    chunker = SUTDocumentChunker(doc_type=doc_type, doc_source=doc_source)
    chunks = chunker.chunk_document(text)
    
    logger.info(f"✓ Created {len(chunks)} chunks from {doc_type}")
    return chunks


def index_all_documents():
    """Main function to index SUT + all EK-4 documents."""
    try:
        logger.info("🚀 Starting multi-document indexing process with FAISS")
        logger.info(f"📊 Embedding Provider: {EMBEDDING_PROVIDER}")
        logger.info(f"🔢 Embedding Dimension: {EMBEDDING_DIMENSION}")
        logger.info(f"📚 Documents to index: 1 SUT + {len(EK4_DOCUMENTS)} EK-4 documents")

        # Initialize OpenAI client (not needed for OpenRouter embeddings)
        openai_client = None
        if EMBEDDING_PROVIDER == "openai":
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        vector_store = FAISSVectorStore()
        pdf_loader = PDFLoader()
        embedding_generator = EmbeddingGenerator(client=openai_client)

        # ===== Step 1: Process SUT document =====
        logger.info("\n" + "="*60)
        logger.info("STEP 1: Processing Main SUT Document")
        logger.info("="*60)
        
        sut_chunks = process_document(
            pdf_path=SUT_PDF_PATH,
            doc_type="SUT",
            doc_source=os.path.basename(SUT_PDF_PATH),
            pdf_loader=pdf_loader
        )

        # ===== Step 2: Process all EK-4 documents =====
        logger.info("\n" + "="*60)
        logger.info("STEP 2: Processing EK-4 Documents")
        logger.info("="*60)
        
        ek4_chunks = []
        for variant, pdf_path in EK4_DOCUMENTS.items():
            doc_type = f"EK-4/{variant}"
            doc_source = os.path.basename(pdf_path)
            
            chunks = process_document(
                pdf_path=pdf_path,
                doc_type=doc_type,
                doc_source=doc_source,
                pdf_loader=pdf_loader
            )
            ek4_chunks.extend(chunks)
        
        # ===== Step 3: Combine all chunks =====
        logger.info("\n" + "="*60)
        logger.info("STEP 3: Combining Chunks")
        logger.info("="*60)
        
        all_chunks = sut_chunks + ek4_chunks
        logger.info(f"✓ Total chunks: {len(all_chunks)}")
        logger.info(f"  - SUT chunks: {len(sut_chunks)}")
        logger.info(f"  - EK-4 chunks: {len(ek4_chunks)}")

        # ===== Step 4: Create embeddings =====
        logger.info("\n" + "="*60)
        logger.info(f"STEP 4: Creating Embeddings using {EMBEDDING_PROVIDER}")
        logger.info("="*60)
        
        embeddings_data = embedding_generator.create_embeddings(all_chunks)
        logger.info(f"✓ Created {len(embeddings_data)} embeddings")

        # ===== Step 5: Create and populate FAISS index =====
        logger.info("\n" + "="*60)
        logger.info("STEP 5: Creating FAISS Index")
        logger.info("="*60)
        
        vector_store.create_index(dimension=EMBEDDING_DIMENSION)
        logger.info(f"✓ Created FAISS index with dimension {EMBEDDING_DIMENSION}")

        logger.info(f"📥 Adding {len(embeddings_data)} vectors to FAISS index")
        vector_store.add_embeddings(embeddings_data)

        # ===== Step 6: Save index to disk =====
        logger.info("\n" + "="*60)
        logger.info("STEP 6: Saving FAISS Index")
        logger.info("="*60)
        
        vector_store.save()
        logger.info("✓ Index saved to disk")

        # ===== Final Summary =====
        logger.info("\n" + "="*60)
        logger.info("✅ INDEXING COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        
        stats = vector_store.get_stats()
        logger.info(f"📊 Final Index Statistics:")
        logger.info(f"  - Total vectors: {stats['total_vectors']}")
        logger.info(f"  - Dimension: {stats['dimension']}")
        logger.info(f"  - Index type: {stats['index_type']}")
        
        # Document breakdown
        sut_count = len([c for c in all_chunks if c.metadata.doc_type == "SUT"])
        ek4_d = len([c for c in all_chunks if c.metadata.doc_type == "EK-4/D"])
        ek4_e = len([c for c in all_chunks if c.metadata.doc_type == "EK-4/E"])
        ek4_f = len([c for c in all_chunks if c.metadata.doc_type == "EK-4/F"])
        ek4_g = len([c for c in all_chunks if c.metadata.doc_type == "EK-4/G"])
        
        logger.info(f"\n� Document Breakdown:")
        logger.info(f"  - SUT: {sut_count} chunks")
        logger.info(f"  - EK-4/D: {ek4_d} chunks")
        logger.info(f"  - EK-4/E: {ek4_e} chunks")
        logger.info(f"  - EK-4/F: {ek4_f} chunks")
        logger.info(f"  - EK-4/G: {ek4_g} chunks")

    except Exception as e:
        logger.error(f"❌ Error during indexing: {e}")
        raise


if __name__ == "__main__":
    index_all_documents()
