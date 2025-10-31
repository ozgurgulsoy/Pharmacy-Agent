"""RAG retrieval engine for SUT document search."""

import time
import logging
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from openai import OpenAI

from app.core.rag.faiss_store import FAISSVectorStore
from app.core.document_processing.embeddings import EmbeddingGenerator
from app.models.report import Drug, Diagnosis, PatientInfo
from app.models.eligibility import RetrievedChunk, Chunk
from app.config.settings import EMBEDDING_MODEL

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """Cache for query embeddings to avoid recomputation."""

    def __init__(self, cache_dir: str = "data/embedding_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def get_cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, text: str) -> Optional[List[float]]:
        cache_file = self.cache_dir / f"{self.get_cache_key(text)}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                return None
        return None

    def set(self, text: str, embedding: List[float]):
        cache_file = self.cache_dir / f"{self.get_cache_key(text)}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(embedding, f)
        except Exception:
            pass  # Fail silently for cache writes


class RAGRetriever:
    """SUT dokümanından ilgili chunk'ları bulan retriever."""

    def __init__(
        self,
        vector_store: FAISSVectorStore,
        openai_client: Optional[OpenAI] = None
    ):
        self.vector_store = vector_store
        self.client = openai_client
        self.embedding_generator = EmbeddingGenerator(client=openai_client)
        self.embedding_cache = EmbeddingCache()
        self.logger = logging.getLogger(self.__class__.__name__)

    def retrieve_relevant_chunks(
        self,
        drug: Drug,
        diagnosis: Optional[Diagnosis] = None,
        patient: Optional[PatientInfo] = None,
        top_k: int = 5
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        Bir ilaç için ilgili SUT chunk'larını getirir.

        Args:
            drug: İlaç bilgisi
            diagnosis: Tanı bilgisi (opsiyonel)
            patient: Hasta bilgisi (opsiyonel)
            top_k: Kaç chunk getirileceği

        Returns:
            (İlgili chunk listesi, timing bilgileri)
        """
        timings = {}
        total_start = time.time()
        
        self.logger.info(f"Retrieving chunks for drug: {drug.etkin_madde}")

        # 1. Query oluştur
        query_start = time.time()
        query_text = self._build_query_text(drug, diagnosis, patient)
        timings['query_build'] = (time.time() - query_start) * 1000
        self.logger.debug(f"Query: {query_text}")

        # 2. Hybrid search: Keyword + Semantic
        keyword_start = time.time()
        keyword_results = self._keyword_search(drug.etkin_madde)
        timings['keyword_search'] = (time.time() - keyword_start) * 1000
        
        # 3. Query embedding oluştur
        embedding_start = time.time()
        query_embedding = self._create_query_embedding(query_text)
        timings['embedding_creation'] = (time.time() - embedding_start) * 1000

        # 4. Vector search
        vector_start = time.time()
        semantic_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,
            filters={"drug_related": True} if self._has_metadata_filter() else None
        )
        timings['vector_search'] = (time.time() - vector_start) * 1000

        # 5. Combine and re-rank with keyword boosting
        rerank_start = time.time()
        final_results = self._hybrid_rerank(
            keyword_results=keyword_results,
            semantic_results=semantic_results,
            drug_name=drug.etkin_madde,
            top_k=top_k
        )
        timings['reranking'] = (time.time() - rerank_start) * 1000
        
        timings['total'] = (time.time() - total_start) * 1000

        self.logger.info(f"Retrieved {len(final_results)} relevant chunks in {timings['total']:.1f}ms")
        return final_results, timings

    def _build_query_text(
        self,
        drug: Drug,
        diagnosis: Optional[Diagnosis],
        patient: Optional[PatientInfo]
    ) -> str:
        """Semantic search için query metni oluşturur."""
        query_parts = [
            f"İlaç: {drug.etkin_madde}",
            f"Form: {drug.form}",
        ]

        if diagnosis:
            query_parts.append(f"Tanı: {diagnosis.tanim}")
            if diagnosis.icd10_code != "UNKNOWN":
                query_parts.append(f"ICD-10: {diagnosis.icd10_code}")

        if patient and patient.yas:
            query_parts.append(f"Hasta yaşı: {patient.yas}")

        # SUT kullanım şartları ve koşulları
        query_parts.append("kullanım şartları uygunluk kriterleri rapor gerekli")

        return " | ".join(query_parts)

    def _create_query_embedding(self, query_text: str) -> List[float]:
        """Query için embedding oluşturur (with caching)."""
        try:
            # Check cache first
            cached_embedding = self.embedding_cache.get(query_text)
            if cached_embedding is not None:
                self.logger.debug(f"Using cached embedding for query: {query_text[:50]}...")
                return cached_embedding

            # Create new embedding
            embedding = self.embedding_generator.create_query_embedding(query_text)

            # Cache the result
            self.embedding_cache.set(query_text, embedding)

            return embedding

        except Exception as e:
            self.logger.error(f"Error creating query embedding: {e}")
            raise

    def _has_metadata_filter(self) -> bool:
        """Vector store metadata filtering destekliyor mu?"""
        # FAISS için manual filtering yapıyoruz
        return False

    def _keyword_search(self, drug_name: str) -> List[Dict[str, Any]]:
        """
        Fast O(1) keyword search using drug index.
        
        Args:
            drug_name: Drug name to search for
            
        Returns:
            Matching chunks with boosted scores
        """
        indices = self.vector_store.get_chunks_by_drug(drug_name)
        results = []
        
        for idx in indices:
            metadata = self.vector_store.metadata[idx].copy()
            results.append({
                "id": metadata["id"],
                "score": 1.0,  # Perfect match score
                "metadata": metadata,
                "match_type": "keyword"
            })
        
        return results
    
    def _hybrid_rerank(
        self,
        keyword_results: List[Dict[str, Any]],
        semantic_results: List[Dict[str, Any]],
        drug_name: str,
        top_k: int,
        keyword_boost: float = 5.0  # Increased from 2.0 to ensure keyword matches always rank first
    ) -> List[Dict[str, Any]]:
        """
        Combine keyword and semantic results with boosting.
        
        Keyword exact matches (from drug index) get highest priority (5x boost).
        Content matches (drug name in text) get medium priority (2x boost).
        Semantic-only matches get base priority (1x).
        
        Args:
            keyword_results: Results from keyword search (drug index hits)
            semantic_results: Results from semantic search
            drug_name: Drug name for partial matching
            top_k: Number of results to return
            keyword_boost: Score multiplier for exact keyword matches
            
        Returns:
            Re-ranked combined results
        """
        # Create score map
        score_map = {}
        drug_lower = drug_name.lower()
        
        # Add keyword results with HIGH boost (drug index exact matches)
        for result in keyword_results:
            chunk_id = result["id"]
            score_map[chunk_id] = {
                "score": result["score"] * keyword_boost,  # 5.0x boost
                "metadata": result["metadata"],
                "has_keyword": True,
                "match_type": "exact"
            }
        
        # Add/update with semantic results
        for result in semantic_results:
            chunk_id = result["id"]
            if chunk_id in score_map:
                # Already have keyword match - add semantic score (but keep keyword priority)
                score_map[chunk_id]["score"] = (
                    score_map[chunk_id]["score"] * 0.8 + result["score"] * 0.2
                )
            else:
                # Check for partial match in content
                content = result.get("metadata", {}).get("content", "").lower()
                has_match = drug_lower in content
                
                if has_match:
                    # Drug name in content - medium boost
                    boost = 2.0
                    match_type = "partial"
                else:
                    # Pure semantic match - no boost
                    boost = 1.0
                    match_type = "semantic"
                
                score_map[chunk_id] = {
                    "score": result["score"] * boost,
                    "metadata": result["metadata"],
                    "has_keyword": has_match,
                    "match_type": match_type
                }
        
        # Sort by score and return top_k
        ranked = sorted(
            [
                {"id": k, **v} for k, v in score_map.items()
            ],
            key=lambda x: x["score"],
            reverse=True
        )
        
        return ranked[:top_k]

    def retrieve_for_multiple_drugs(
        self,
        drugs: List[Drug],
        diagnosis: Optional[Diagnosis] = None,
        patient: Optional[PatientInfo] = None,
        top_k_per_drug: int = 5
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Birden fazla ilaç için chunk'ları getirir.

        Args:
            drugs: İlaç listesi
            diagnosis: Tanı
            patient: Hasta bilgisi
            top_k_per_drug: Her ilaç için kaç chunk

        Returns:
            ({drug_name: [chunks]} dictionary, aggregate timings)
        """
        results: Dict[str, List[Dict[str, Any]]] = {}
        all_timings: List[Dict[str, float]] = []

        if not drugs:
            return results, {}

        import time
        total_start = time.time()

        # 1) Build all queries
        query_build_start = time.time()
        queries: List[str] = []
        query_metadata: List[Dict[str, Any]] = []
        for drug in drugs:
            q = self._build_query_text(drug, diagnosis, patient)
            queries.append(q)
            query_metadata.append({"drug": drug, "query": q})
        query_build_time = (time.time() - query_build_start) * 1000

        # 2) Create embeddings in batch with caching and parallel processing
        embedding_start = time.time()
        embeddings: List[List[float]] = []

        try:
            # Check cache for all queries first
            cached_embeddings = []
            uncached_queries = []
            uncached_indices = []

            for i, query in enumerate(queries):
                cached = self.embedding_cache.get(query)
                if cached is not None:
                    cached_embeddings.append((i, cached))
                else:
                    uncached_queries.append(query)
                    uncached_indices.append(i)

            # Create embeddings for uncached queries
            if uncached_queries:
                # Use OpenAI batch API (much faster than sequential)
                self.logger.info(f"Creating batch embeddings for {len(uncached_queries)} uncached queries")
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=uncached_queries,
                    encoding_format="float"
                )
                new_embeddings = [item.embedding for item in response.data]

                # Cache new embeddings
                for query, embedding in zip(uncached_queries, new_embeddings):
                    self.embedding_cache.set(query, embedding)

                # Reconstruct full embeddings list
                embeddings = [None] * len(queries)
                for i, emb in cached_embeddings:
                    embeddings[i] = emb
                for i, emb in zip(uncached_indices, new_embeddings):
                    embeddings[i] = emb
            else:
                # All from cache
                embeddings = [emb for _, emb in cached_embeddings]

        except Exception as e:
            # Fallback to sequential processing
            self.logger.error(f"Batch embedding creation failed: {e}, falling back to sequential")
            embeddings = [self._create_query_embedding(q) for q in queries]

        embedding_time = (time.time() - embedding_start) * 1000

        # 3) For each embedding, perform vector search + keyword + rerank
        search_start = time.time()
        for idx, (meta, emb) in enumerate(zip(query_metadata, embeddings)):
            drug: Drug = meta["drug"]
            drug_start = time.time()

            # Keyword search (fast)
            k_start = time.time()
            keyword_results = self._keyword_search(drug.etkin_madde)
            k_time = (time.time() - k_start) * 1000

            # Vector search
            v_start = time.time()
            semantic_results = self.vector_store.search(
                query_embedding=emb,
                top_k=top_k_per_drug * 2,
                filters={"drug_related": True} if self._has_metadata_filter() else None
            )
            v_time = (time.time() - v_start) * 1000

            # Re-rank
            r_start = time.time()
            final_results = self._hybrid_rerank(
                keyword_results=keyword_results,
                semantic_results=semantic_results,
                drug_name=drug.etkin_madde,
                top_k=top_k_per_drug
            )
            r_time = (time.time() - r_start) * 1000

            results[drug.etkin_madde] = final_results

            drug_total = (time.time() - drug_start) * 1000
            all_timings.append({
                'keyword_search': k_time,
                'embedding_creation': 0.0,  # accounted for in batch
                'vector_search': v_time,
                'reranking': r_time,
                'total': drug_total
            })

        search_time = (time.time() - search_start) * 1000
        total_time = (time.time() - total_start) * 1000

        # Aggregate timings
        aggregate = {
            'query_building': query_build_time,
            'embedding_creation': embedding_time,
            'keyword_search': sum(t['keyword_search'] for t in all_timings),
            'vector_search': sum(t['vector_search'] for t in all_timings),
            'reranking': sum(t['reranking'] for t in all_timings),
            'total': total_time,
            'avg_per_drug': total_time / len(drugs) if drugs else 0
        }

        self.logger.info(f"Retrieved chunks for {len(drugs)} drugs in {total_time:.1f}ms (embeddings: {embedding_time:.1f}ms)")
        return results, aggregate
