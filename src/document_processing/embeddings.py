"""Embeddings generation utilities supporting multiple providers."""

import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
import ollama

from models.eligibility import Chunk
from config.settings import (
    EMBEDDING_MODEL, 
    EMBEDDING_PROVIDER,
    EMBEDDING_DIMENSION,
    OLLAMA_HOST
)

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Embeddings generator supporting multiple providers (OpenAI, Ollama)."""

    def __init__(self, client: Optional[OpenAI] = None, provider: str = EMBEDDING_PROVIDER):
        """
        Initialize the embedding generator.
        
        Args:
            client: OpenAI client (required if provider is "openai")
            provider: Embedding provider ("openai" or "ollama")
        """
        self.client = client
        self.provider = provider
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if self.provider == "ollama":
            self.logger.info(f"Using Ollama embeddings with model: {EMBEDDING_MODEL}")
            self.logger.info(f"Embedding dimension: {EMBEDDING_DIMENSION}")
        elif self.provider == "openai":
            if not self.client:
                raise ValueError("OpenAI client is required when using OpenAI provider")
            self.logger.info(f"Using OpenAI embeddings with model: {EMBEDDING_MODEL}")
    
    def _create_ollama_embedding(self, text: str) -> List[float]:
        """
        Create embedding using Ollama.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = ollama.embeddings(
                model=EMBEDDING_MODEL,
                prompt=text
            )
            return response["embedding"]
        except Exception as e:
            self.logger.error(f"Error creating Ollama embedding: {e}")
            raise
    
    def _create_openai_embedding(self, text: str) -> List[float]:
        """
        Create embedding using OpenAI.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"Error creating OpenAI embedding: {e}")
            raise

    def create_embeddings(self, chunks: List[Chunk]) -> List[Dict[str, Any]]:
        """
        Chunk'lar için embeddings oluşturur.

        Args:
            chunks: Chunk listesi

        Returns:
            Embedding verileri listesi
        """
        self.logger.info(f"Creating embeddings for {len(chunks)} chunks using {self.provider}")

        embeddings_data = []

        for i, chunk in enumerate(chunks):
            try:
                # Embedding oluştur
                if self.provider == "ollama":
                    embedding = self._create_ollama_embedding(chunk.content)
                else:  # openai
                    embedding = self._create_openai_embedding(chunk.content)

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
        try:
            if self.provider == "ollama":
                return self._create_ollama_embedding(query)
            else:  # openai
                return self._create_openai_embedding(query)

        except Exception as e:
            self.logger.error(f"Error creating query embedding: {e}")
            raise