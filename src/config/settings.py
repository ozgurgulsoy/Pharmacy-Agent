"""Configuration settings for Pharmacy Agent."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

# Ollama Settings
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Model Settings
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:8b")
EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "ollama")  # "ollama" or "openai"

LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-5-nano")

# Chunk Settings - Optimized for SUT regulatory documents with hierarchical structure
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))  # ~200 tokens - captures complete subsections
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))  # ~40 tokens - maintains context between chunks
TOP_K_CHUNKS: int = int(os.getenv("TOP_K_CHUNKS", "4"))

# Language Settings
OUTPUT_LANGUAGE: str = os.getenv("OUTPUT_LANGUAGE", "turkish")

# FAISS Settings
EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "4096"))  # qwen3-embedding:8b dimension
FAISS_INDEX_PATH: str = "data/faiss_index"
FAISS_METADATA_PATH: str = "data/faiss_metadata.json"

# File Paths
SUT_PDF_PATH: str = "data/9.5.17229.pdf"
SAMPLE_REPORTS_DIR: str = "data/sample_reports"

# Validation
def validate_config() -> None:
    """Validate that all required configuration is present."""
    if EMBEDDING_PROVIDER == "openai" and not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required when using OpenAI embeddings")

# Call validation on import
validate_config()