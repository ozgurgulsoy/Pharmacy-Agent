"""Configuration settings for Pharmacy Agent."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

# Model Settings
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")  # Latest fast model
# Note: Model-specific parameter support:
#   - gpt-5-*: use max_completion_tokens, temperature locked to 1 (default)
#   - o1-*: use max_completion_tokens, no temperature support
#   - gpt-4-*/gpt-3.5-*: use max_tokens, full temperature support
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))  # Limit response length
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))  # Lower = faster (ignored for gpt-5/o1)

# Chunk Settings - Optimized for SUT regulatory documents with hierarchical structure
# Note: text-embedding-3-small supports up to 8191 tokens, so we have plenty of room
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "2048"))  # ~512 tokens - captures complete subsections with context
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "256"))  # ~64 tokens (12.5%) - prevents context fragmentation
TOP_K_CHUNKS: int = int(os.getenv("TOP_K_CHUNKS", "5"))  # Reduced to 5 for optimal balance

# Performance Settings
ENABLE_STREAMING: bool = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
PARALLEL_EMBEDDINGS: bool = os.getenv("PARALLEL_EMBEDDINGS", "true").lower() == "true"
CACHE_EMBEDDINGS: bool = os.getenv("CACHE_EMBEDDINGS", "true").lower() == "true"

# Batch Processing Settings
# Maximum number of drugs to process in a single batched LLM call
# For more drugs, sequential processing is used for better accuracy
# Recommended: 3 for gpt-5-nano (temperature=1.0), 5 for gpt-4o-mini (temperature=0.1)
MAX_BATCH_SIZE: int = int(os.getenv("MAX_BATCH_SIZE", "3"))

# Chunking Strategy - can be "semantic", "fixed", or "hybrid"
CHUNKING_STRATEGY: str = os.getenv("CHUNKING_STRATEGY", "semantic")

# Semantic Chunking Settings
MIN_CHUNK_SIZE: int = int(os.getenv("MIN_CHUNK_SIZE", "512"))  # ~128 tokens minimum
MAX_CHUNK_SIZE: int = int(os.getenv("MAX_CHUNK_SIZE", "4096"))  # ~1024 tokens maximum
PRESERVE_PARAGRAPHS: bool = os.getenv("PRESERVE_PARAGRAPHS", "true").lower() == "true"

# Language Settings
OUTPUT_LANGUAGE: str = os.getenv("OUTPUT_LANGUAGE", "turkish")

# FAISS Settings
EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1536"))  # text-embedding-3-small dimension
FAISS_INDEX_PATH: str = "data/faiss_index"
FAISS_METADATA_PATH: str = "data/faiss_metadata.json"

# File Paths
SUT_PDF_PATH: str = "data/9.5.17229.pdf"
SAMPLE_REPORTS_DIR: str = "data/sample_reports"

# Validation
def validate_config() -> None:
    """Validate that all required configuration is present."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required")

# Call validation on import
validate_config()