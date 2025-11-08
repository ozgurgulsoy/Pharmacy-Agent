"""
High-level SUT Checker Service.
Orchestrates report parsing, RAG retrieval, and eligibility checking.
"""

import logging
from typing import List, Dict, Any
from openai import OpenAI

from app.core.parsers.input_parser import InputParser
from app.core.rag.faiss_store import FAISSVectorStore
from app.core.rag.retriever import RAGRetriever
from app.core.llm.openai_client import OpenAIClientWrapper
from app.core.llm.eligibility_checker import EligibilityChecker
from app.models.report import ParsedReport
from app.models.eligibility import EligibilityResult
from app.config.settings import (
    OPENAI_API_KEY,
    FAISS_INDEX_PATH,
    FAISS_METADATA_PATH,
    TOP_K_CHUNKS,
)

logger = logging.getLogger(__name__)


class SUTCheckerService:
    """
    Main service for SUT compliance checking.
    Provides a clean interface for all report analysis operations.
    """

    def __init__(self):
        self.parser = InputParser()
        self.vector_store = None
        self.retriever = None
        self.eligibility_checker = None
        self.openai_client = None
        self.initialized = False

    def initialize(self) -> None:
        """Initialize all components."""
        if self.initialized:
            logger.info("Service already initialized")
            return

        logger.info("Initializing SUT Checker Service...")

        try:
            # Initialize OpenAI client
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            openai_wrapper = OpenAIClientWrapper()
            logger.info("✓ OpenAI client initialized")

            # Load FAISS index
            self.vector_store = FAISSVectorStore()
            self.vector_store.load(FAISS_INDEX_PATH, FAISS_METADATA_PATH)
            stats = self.vector_store.get_stats()
            logger.info(f"✓ FAISS index loaded ({stats['total_vectors']} vectors)")

            # Initialize RAG retriever
            self.retriever = RAGRetriever(self.vector_store, self.openai_client)
            logger.info("✓ RAG retriever initialized")

            # Initialize eligibility checker
            self.eligibility_checker = EligibilityChecker(openai_wrapper)
            logger.info("✓ Eligibility checker initialized")

            self.initialized = True
            logger.info("✅ Service initialized successfully")

        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            raise

    def parse_report(self, report_text: str) -> ParsedReport:
        """
        Parse raw report text into structured format.
        
        Args:
            report_text: Raw patient report text
            
        Returns:
            ParsedReport object with extracted information
        """
        if not self.initialized:
            raise RuntimeError("Service not initialized. Call initialize() first.")
        
        return self.parser.parse_report(report_text)

    def check_eligibility(
        self,
        report_text: str,
        top_k: int = TOP_K_CHUNKS
    ) -> Dict[str, Any]:
        """
        Complete eligibility check workflow with EK-4 document support.
        
        Args:
            report_text: Raw patient report text
            top_k: Number of chunks to retrieve per drug per document
            
        Returns:
            Dictionary with parsed report info and eligibility results
        """
        if not self.initialized:
            raise RuntimeError("Service not initialized. Call initialize() first.")

        import time
        
        start_time = time.time()
        
        # 1. Parse report
        parsed_report = self.parse_report(report_text)
        
        # 2. Retrieve relevant SUT chunks (pass full report text for EK-4 detection)
        logger.info("Retrieving relevant SUT chunks...")
        retrieve_start = time.time()
        
        sut_chunks_dict, rag_timings = self.retriever.retrieve_for_multiple_drugs(
            drugs=parsed_report.drugs,
            diagnosis=parsed_report.diagnoses[0] if parsed_report.diagnoses else None,
            patient=parsed_report.patient,
            top_k_per_drug=top_k,
            report_text=parsed_report.raw_text  # Pass full report for EK-4 detection
        )
        
        # 3. Check eligibility for all drugs
        eligibility_results = self.eligibility_checker.check_multiple_drugs(
            drugs=parsed_report.drugs,
            diagnoses=parsed_report.diagnoses,
            patient=parsed_report.patient,
            doctor=parsed_report.doctor,
            sut_chunks_per_drug=sut_chunks_dict,
            explanations=parsed_report.explanations,
            report_type=parsed_report.report_type
        )
        
        total_time = (time.time() - start_time) * 1000  # Convert to ms
        
        return {
            "parsed_report": parsed_report,
            "eligibility_results": eligibility_results,
            "performance": {
                "total_ms": total_time,
                "retrieval_ms": rag_timings.get('total', 0),
                "ek4_refs_detected": rag_timings.get('ek4_refs_found', 0)
            }
        }

    def check_single_drug(
        self,
        drug_name: str,
        diagnosis_code: str = None,
        top_k: int = TOP_K_CHUNKS
    ) -> List[Dict[str, Any]]:
        """
        Check eligibility for a single drug (useful for quick lookups).
        
        Args:
            drug_name: Name of the drug/active ingredient
            diagnosis_code: Optional ICD-10 diagnosis code
            top_k: Number of SUT chunks to retrieve
            
        Returns:
            List of relevant SUT chunks
        """
        if not self.initialized:
            raise RuntimeError("Service not initialized. Call initialize() first.")
        
        query_text = f"İlaç: {drug_name}"
        if diagnosis_code:
            query_text += f" Tanı: {diagnosis_code}"
        
        chunks = self.retriever.retrieve(
            query_text=query_text,
            top_k=top_k
        )
        
        return chunks

    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        if not self.initialized:
            return {"initialized": False}
        
        faiss_stats = self.vector_store.get_stats()
        
        return {
            "initialized": True,
            "faiss_index": {
                "total_vectors": faiss_stats.get("total_vectors", 0),
                "dimension": faiss_stats.get("dimension", 0)
            }
        }
