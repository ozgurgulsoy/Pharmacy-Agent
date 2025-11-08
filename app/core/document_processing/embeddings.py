"""Embeddings generation utilities using OpenAI or OpenRouter."""

import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from app.models.eligibility import Chunk
from app.config.settings import (
    EMBEDDING_MODEL, 
    EMBEDDING_DIMENSION, 
    EMBEDDING_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENAI_API_KEY,
    OPENROUTER_EMBEDDING_PROVIDER,
)

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Embeddings generator using OpenAI or OpenRouter."""

    def __init__(self, client: OpenAI = None):
        """
        Initialize the embedding generator.
        
        Args:
            client: OpenAI client (optional, will create based on provider)
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.provider_preferences: List[str] = []
        
        # Determine which client to use based on provider
        if EMBEDDING_PROVIDER == "openrouter":
            self.client = OpenAI(
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL
            )
            self.provider_preferences = self._parse_provider_override(OPENROUTER_EMBEDDING_PROVIDER)
            if self.provider_preferences:
                self.logger.info(f"OpenRouter embedding provider preference order: {self.provider_preferences}")
            self.logger.info(f"✅ Using OpenRouter embeddings with model: {EMBEDDING_MODEL} (dimension: {EMBEDDING_DIMENSION}) via {OPENROUTER_EMBEDDING_PROVIDER or 'default'}")
        else:
            self.client = client or OpenAI(api_key=OPENAI_API_KEY)
            self.logger.info(f"✅ Using OpenAI embeddings with model: {EMBEDDING_MODEL} (dimension: {EMBEDDING_DIMENSION})")

    @staticmethod
    def _parse_provider_override(raw_value: Optional[str]) -> List[str]:
        """Return a provider preference list from a comma-delimited string."""
        if not raw_value:
            return []
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    def _inject_provider_preferences(self, kwargs: Dict[str, Any]) -> None:
        """Augment embedding kwargs with provider preferences."""
        if not self.provider_preferences:
            return

        provider_body = {
            "order": self.provider_preferences,
            "allow_fallbacks": len(self.provider_preferences) > 1
        }

        extra_body = kwargs.setdefault("extra_body", {})
        extra_body["provider"] = provider_body
    
    def _create_embedding(self, text: str) -> List[float]:
        """
        Create embedding using configured provider.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            # Create embedding (OpenRouter's Qwen3 returns 4096 dimensions by default)
            kwargs = {
                "model": EMBEDDING_MODEL,
                "input": text,
                "encoding_format": "float"
            }

            self._inject_provider_preferences(kwargs)
            
            response = self.client.embeddings.create(**kwargs)
            
            embedding = response.data[0].embedding
            
            # Verify dimension
            if len(embedding) != EMBEDDING_DIMENSION:
                self.logger.warning(
                    f"⚠️ Dimension mismatch! Expected {EMBEDDING_DIMENSION}, got {len(embedding)}. "
                    f"Update EMBEDDING_DIMENSION in .env to {len(embedding)}"
                )
            
            return embedding
            
        except Exception as e:
            self.logger.error(f"Error creating embedding: {e}")
            raise

    def create_embeddings(self, chunks: List[Chunk]) -> List[Dict[str, Any]]:
        """
        Chunk'lar için embeddings oluşturur.

        Args:
            chunks: Chunk listesi

        Returns:
            Embedding verileri listesi
        """
        self.logger.info(f"Creating embeddings for {len(chunks)} chunks")

        embeddings_data = []

        for i, chunk in enumerate(chunks):
            try:
                # Embedding oluştur
                embedding = self._create_embedding(chunk.content)

                # FAISS formatında veri hazırla
                embedding_data = {
                    "id": chunk.chunk_id,
                    "values": embedding,
                    "metadata": {
                        "content": chunk.content,
                        "section": chunk.metadata.section,
                        "topic": chunk.metadata.topic,
                        "etkin_madde": chunk.metadata.etkin_madde,
                        "keywords": chunk.metadata.keywords,
                        "drug_related": chunk.metadata.drug_related,
                        "has_conditions": chunk.metadata.has_conditions,
                        "doc_type": chunk.metadata.doc_type,
                        "doc_source": chunk.metadata.doc_source,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line
                    }
                }

                embeddings_data.append(embedding_data)

                if (i + 1) % 10 == 0:
                    self.logger.info(f"Processed {i + 1}/{len(chunks)} chunks")

            except Exception as e:
                self.logger.error(f"Error creating embedding for chunk {chunk.chunk_id}: {e}")
                continue

        self.logger.info(f"Successfully created {len(embeddings_data)} embeddings")
        return embeddings_data

    def create_query_embedding(self, query: str) -> List[float]:
        """
        Sorgu için embedding oluşturur.

        Args:
            query: Sorgu metni

        Returns:
            Embedding vektörü
        """
        return self._create_embedding(query)
