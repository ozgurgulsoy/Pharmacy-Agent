"""FAISS vector store for efficient similarity search."""

import os
import json
import logging
import pickle
from typing import List, Dict, Any, Optional
import numpy as np
import faiss

from app.config.settings import FAISS_INDEX_PATH, FAISS_METADATA_PATH, EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """FAISS-based vector store with metadata support."""

    def __init__(self):
        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []
        self.id_to_idx: Dict[str, int] = {}
        self.drug_index: Dict[str, List[int]] = {}  # Drug name -> chunk indices for O(1) lookup
        self.logger = logging.getLogger(self.__class__.__name__)

    def create_index(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        """
        Create a new FAISS index.

        Args:
            dimension: Embedding dimension
        """
        # Use IndexFlatL2 for exact search (perfect for small datasets)
        self.index = faiss.IndexFlatL2(dimension)
        self.metadata = []
        self.id_to_idx = {}
        self.drug_index = {}
        self.logger.info(f"Created new FAISS index with dimension {dimension}")

    def add_embeddings(self, embeddings_data: List[Dict[str, Any]]) -> None:
        """
        Add embeddings to the index.

        Args:
            embeddings_data: List of dicts with 'id', 'values', and 'metadata'
        """
        if self.index is None:
            self.create_index()

        vectors = []
        for item in embeddings_data:
            vectors.append(item["values"])
            
            # Store metadata
            idx = len(self.metadata)
            meta = {
                "id": item["id"],
                **item["metadata"]
            }
            self.metadata.append(meta)
            self.id_to_idx[item["id"]] = idx
            
            # Build drug index for fast lookup
            etkin_maddeler = meta.get("etkin_madde", [])
            if isinstance(etkin_maddeler, str):
                etkin_maddeler = [etkin_maddeler]
            for drug in etkin_maddeler:
                drug_lower = drug.lower()
                if drug_lower not in self.drug_index:
                    self.drug_index[drug_lower] = []
                self.drug_index[drug_lower].append(idx)

        # Convert to numpy array and add to index
        vectors_array = np.array(vectors, dtype=np.float32)
        self.index.add(vectors_array)
        
        self.logger.info(f"Added {len(vectors)} vectors to FAISS index")
        self.logger.info(f"Total vectors in index: {self.index.ntotal}")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of results with metadata and scores
        """
        if self.index is None or self.index.ntotal == 0:
            self.logger.warning("Index is empty or not initialized")
            return []

        # Convert query to numpy array
        query_vector = np.array([query_embedding], dtype=np.float32)

        # Search
        # If filters are provided, search more results and filter afterwards
        search_k = top_k * 10 if filters else top_k
        distances, indices = self.index.search(query_vector, min(search_k, self.index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for empty results
                continue

            metadata = self.metadata[idx].copy()
            
            # Apply filters if provided
            if filters:
                match = True
                for key, value in filters.items():
                    if key in metadata and metadata[key] != value:
                        match = False
                        break
                if not match:
                    continue

            # Convert L2 distance to similarity score (0-1 range)
            # Lower distance = higher similarity
            similarity = 1 / (1 + dist)
            
            results.append({
                "id": metadata["id"],
                "score": float(similarity),
                "metadata": metadata
            })

            if len(results) >= top_k:
                break

        self.logger.info(f"Found {len(results)} results for query")
        return results

    def save(self, index_path: str = FAISS_INDEX_PATH, metadata_path: str = FAISS_METADATA_PATH) -> None:
        """
        Save index and metadata to disk.

        Args:
            index_path: Path to save FAISS index
            metadata_path: Path to save metadata JSON
        """
        if self.index is None:
            self.logger.warning("No index to save")
            return

        # Create directory if needed
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        
        # Save FAISS index
        faiss.write_index(self.index, index_path)
        
        # Save metadata
        metadata_dict = {
            "metadata": self.metadata,
            "id_to_idx": self.id_to_idx,
            "drug_index": self.drug_index
        }
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Saved FAISS index to {index_path}")
        self.logger.info(f"Saved metadata to {metadata_path}")

    def load(self, index_path: str = FAISS_INDEX_PATH, metadata_path: str = FAISS_METADATA_PATH) -> None:
        """
        Load index and metadata from disk.

        Args:
            index_path: Path to FAISS index
            metadata_path: Path to metadata JSON
        """
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Index file not found: {index_path}")
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        # Load FAISS index
        self.index = faiss.read_index(index_path)
        
        # Load metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata_dict = json.load(f)
        
        self.metadata = metadata_dict["metadata"]
        self.id_to_idx = metadata_dict["id_to_idx"]
        self.drug_index = metadata_dict.get("drug_index", {})
        
        self.logger.info(f"Loaded FAISS index from {index_path}")
        self.logger.info(f"Index contains {self.index.ntotal} vectors")
        self.logger.info(f"Loaded {len(self.metadata)} metadata entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if self.index is None:
            return {"status": "not_initialized"}

        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.index.d,
            "metadata_count": len(self.metadata),
            "index_type": type(self.index).__name__
        }

    def get_chunks_by_drug(self, drug_name: str) -> List[int]:
        """
        Get chunk indices containing a specific drug (O(1) lookup).
        
        Args:
            drug_name: Drug name to search for
            
        Returns:
            List of chunk indices
        """
        drug_lower = drug_name.lower()
        return self.drug_index.get(drug_lower, [])
    
    def delete_all(self) -> None:
        """Clear the index and metadata."""
        self.create_index()
        self.logger.info("Cleared FAISS index and metadata")
