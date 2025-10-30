"""Embeddings generation utilities using OpenAI."""

import logging
from typing import List, Dict, Any
from openai import OpenAI

from models.eligibility import Chunk
from config.settings import EMBEDDING_MODEL, EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Embeddings generator using OpenAI."""

    def __init__(self, client: OpenAI):
        """
        Initialize the embedding generator.
        
        Args:
            client: OpenAI client
        """
        self.client = client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Using OpenAI embeddings with model: {EMBEDDING_MODEL}")
    
    def _create_embedding(self, text: str) -> List[float]:
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