"""Configuration settings for Pharmacy Agent."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")

# LLM Provider
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")
OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_PROVIDER: Optional[str] = os.getenv("OPENROUTER_PROVIDER")

# Embedding Provider - can be "openrouter", "openai", or "nebius"
EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "openrouter")
OPENROUTER_EMBEDDING_PROVIDER: Optional[str] = os.getenv("OPENROUTER_EMBEDDING_PROVIDER")  # e.g., "nebius"

# Model Settings
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")  # Default: Qwen3 Embedding 8B via OpenRouter - Türkçe destekli
EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "4096"))  # Qwen3 default: 4096, Nebius default: 4096
LLM_MODEL: str = os.getenv("LLM_MODEL", "google/gemini-2.5-flash-lite")  # Google Gemini 2.5 Flash via OpenRouter - High quality, fast, cost effective

# Chunk Settings - Optimized for SUT regulatory documents with hierarchical structure
# Note: text-embedding-3-small supports up to 8191 tokens, so we have plenty of room
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "2048"))  # ~512 tokens - captures complete subsections with context
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "256"))  # ~64 tokens (12.5%) - prevents context fragmentation
TOP_K_CHUNKS: int = int(os.getenv("TOP_K_CHUNKS", "3"))  # Reduced to 3 to prioritize highest-signal chunks

# Performance Settings
ENABLE_STREAMING: bool = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
PARALLEL_EMBEDDINGS: bool = os.getenv("PARALLEL_EMBEDDINGS", "true").lower() == "true"
CACHE_EMBEDDINGS: bool = os.getenv("CACHE_EMBEDDINGS", "true").lower() == "true"

# Batch Processing Settings
# Maximum number of drugs to process in a single batched LLM call
# For more drugs, sequential processing is used for better accuracy
MAX_BATCH_SIZE: int = int(os.getenv("MAX_BATCH_SIZE", "10"))  # Increased from 3 for better batching

# Chunking Strategy - can be "semantic", "fixed", or "hybrid"
CHUNKING_STRATEGY: str = os.getenv("CHUNKING_STRATEGY", "semantic")

# Semantic Chunking Settings
MIN_CHUNK_SIZE: int = int(os.getenv("MIN_CHUNK_SIZE", "512"))  # ~128 tokens minimum
MAX_CHUNK_SIZE: int = int(os.getenv("MAX_CHUNK_SIZE", "4096"))  # ~1024 tokens maximum
PRESERVE_PARAGRAPHS: bool = os.getenv("PRESERVE_PARAGRAPHS", "true").lower() == "true"

# Language Settings
OUTPUT_LANGUAGE: str = os.getenv("OUTPUT_LANGUAGE", "turkish")

# FAISS Settings
FAISS_INDEX_PATH: str = "data/faiss_index"
FAISS_METADATA_PATH: str = "data/faiss_metadata.json"

# File Paths
SUT_PDF_PATH: str = "data/SUT.pdf"
SAMPLE_REPORTS_DIR: str = "data/sample_reports"

# EK-4 Document Paths
EK4_DOCUMENTS = {
    "D": "data/20201207-1230-sut-ek-4-d-38dbc.pdf",
    "E": "data/20201207-1231-sut-ek-4-e-24c20.pdf",
    "F": "data/20201207-1232-sut-ek-4-f-8f928.pdf",
    "G": "data/20201207-1233-sut-ek-4-g-1a6a1.pdf",
}

# Validation
def validate_config() -> None:
    """Validate that all required configuration is present."""
    # Validate LLM provider
    if LLM_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY environment variable is required when using OpenRouter")
    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required when using OpenAI")
    
    # Validate embedding provider
    if EMBEDDING_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY environment variable is required for embeddings via OpenRouter")
        # If using Nebius through OpenRouter, validate the provider name
        if OPENROUTER_EMBEDDING_PROVIDER == "nebius":
            # Nebius embeddings via OpenRouter are supported
            pass
    elif EMBEDDING_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI embeddings")
    elif EMBEDDING_PROVIDER == "nebius":
        # Direct Nebius provider (if supported in future)
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY environment variable is required for Nebius embeddings")

# Call validation on import
validate_config()
