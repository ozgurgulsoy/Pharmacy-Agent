"""RAG retrieval engine for SUT document search."""

import logging
from typing import List, Dict, Any, Optional

from openai import OpenAI

from rag.faiss_store import FAISSVectorStore
from document_processing.embeddings import EmbeddingGenerator
from models.report import Drug, Diagnosis, PatientInfo
from models.eligibility import RetrievedChunk, Chunk
from config.settings import EMBEDDING_PROVIDER

logger = logging.getLogger(__name__)


class RAGRetriever:
    """SUT dokümanından ilgili chunk'ları bulan retriever."""

    def __init__(
        self, 
        vector_store: FAISSVectorStore, 
        openai_client: Optional[OpenAI] = None,
        provider: str = EMBEDDING_PROVIDER
    ):
        self.vector_store = vector_store
        self.client = openai_client
        self.embedding_generator = EmbeddingGenerator(client=openai_client, provider=provider)
        self.logger = logging.getLogger(self.__class__.__name__)

    def retrieve_relevant_chunks(
        self,
        drug: Drug,
        diagnosis: Optional[Diagnosis] = None,
        patient: Optional[PatientInfo] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Bir ilaç için ilgili SUT chunk'larını getirir.

        Args:
            drug: İlaç bilgisi
            diagnosis: Tanı bilgisi (opsiyonel)
            patient: Hasta bilgisi (opsiyonel)
            top_k: Kaç chunk getirileceği

        Returns:
            İlgili chunk listesi
        """
        self.logger.info(f"Retrieving chunks for drug: {drug.etkin_madde}")

        # 1. Query oluştur
        query_text = self._build_query_text(drug, diagnosis, patient)
        self.logger.debug(f"Query: {query_text}")

        # 2. Query embedding oluştur
        query_embedding = self._create_query_embedding(query_text)

        # 3. Vector search
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Filtering için fazladan al
            filters={"drug_related": True} if self._has_metadata_filter() else None
        )

        # 4. İlaç ismine göre filtrele ve re-rank
        filtered_results = self._filter_by_drug_name(results, drug.etkin_madde)
        
        # 5. İlk top_k'yı al
        final_results = filtered_results[:top_k] if filtered_results else results[:top_k]

        self.logger.info(f"Retrieved {len(final_results)} relevant chunks")
        return final_results

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
        """Query için embedding oluşturur."""
        try:
            return self.embedding_generator.create_query_embedding(query_text)

        except Exception as e:
            self.logger.error(f"Error creating query embedding: {e}")
            raise

    def _has_metadata_filter(self) -> bool:
        """Vector store metadata filtering destekliyor mu?"""
        # FAISS için manual filtering yapıyoruz
        return False

    def _filter_by_drug_name(
        self,
        results: List[Dict[str, Any]],
        drug_name: str
    ) -> List[Dict[str, Any]]:
        """
        Sonuçları ilaç ismine göre filtreler.

        Args:
            results: FAISS search sonuçları
            drug_name: İlaç etkin maddesi

        Returns:
            Filtrelenmiş sonuçlar
        """
        filtered = []
        drug_name_lower = drug_name.lower()

        for result in results:
            metadata = result.get('metadata', {})
            
            # Etkin madde listesinde var mı?
            etkin_maddeler = metadata.get('etkin_madde', [])
            
            # String mi liste mi kontrol et
            if isinstance(etkin_maddeler, str):
                etkin_maddeler = [etkin_maddeler]
            
            # İlaç adı eşleşiyor mu?
            if any(drug_name_lower in em.lower() for em in etkin_maddeler):
                filtered.append(result)
                continue
            
            # Content'te geçiyor mu?
            content = metadata.get('content', '').lower()
            if drug_name_lower in content:
                filtered.append(result)

        return filtered if filtered else results  # Boşsa tüm sonuçları dön

    def retrieve_for_multiple_drugs(
        self,
        drugs: List[Drug],
        diagnosis: Optional[Diagnosis] = None,
        patient: Optional[PatientInfo] = None,
        top_k_per_drug: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Birden fazla ilaç için chunk'ları getirir.

        Args:
            drugs: İlaç listesi
            diagnosis: Tanı
            patient: Hasta bilgisi
            top_k_per_drug: Her ilaç için kaç chunk

        Returns:
            {drug_name: [chunks]} dictionary
        """
        results = {}

        for drug in drugs:
            chunks = self.retrieve_relevant_chunks(
                drug=drug,
                diagnosis=diagnosis,
                patient=patient,
                top_k=top_k_per_drug
            )
            results[drug.etkin_madde] = chunks

        return results
