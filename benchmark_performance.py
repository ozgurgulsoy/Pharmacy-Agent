#!/usr/bin/env python3
"""
Performance benchmarking script for Pharmacy Agent.

Runs test cases and measures timing for each component.
"""

import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.llm.openai_client import OpenAIClientWrapper
from src.parsers.input_parser import InputParser
from src.rag.faiss_store import FAISSVectorStore
from src.rag.retriever import RAGRetriever
from src.llm.eligibility_checker import EligibilityChecker
from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


SAMPLE_REPORT = """
RAPOR NO: 12345
TARİH: 30/10/2025
TESİS KODU: 1234567

HASTA BİLGİLERİ:
TC Kimlik No: 12345678901
Ad Soyad: TEST HASTA
Doğum Tarihi: 01/01/1980
Cinsiyet: Erkek

DOKTOR BİLGİLERİ:
Dr. Test Doktor
Kardiyoloji
Diploma No: 123456

TANI BİLGİLERİ:
ICD-10: I25.1
Tanı: Aterosklerotik kalp hastalığı

İLAÇ BİLGİLERİ:
1. ETKİN MADDE: ATORVASTATIN
   FORM: Ağızdan katı
   TEDAVİ ŞEMASI: Günde 1x1
   MİKTAR: 1 kutu
   SGK KODU: SGK-1234567
   EKLENİŞ: 30/10/2025

AÇIKLAMALAR:
Hasta LDL: 180 mg/dL
Anjiyo tarihi: 15/09/2025
İlk statin tedavisi
"""


def measure_time(func_name: str):
    """Decorator to measure function execution time."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.info(f"\n{'='*60}")
            logger.info(f"🏃 STARTING: {func_name}")
            logger.info(f"{'='*60}")
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"{'='*60}")
            logger.info(f"✅ COMPLETED: {func_name} in {elapsed:.2f}s ({elapsed*1000:.1f}ms)")
            logger.info(f"{'='*60}\n")
            return result, elapsed
        return wrapper
    return decorator


@measure_time("1. System Initialization")
def test_initialization() -> Dict[str, Any]:
    """Test system initialization time."""
    logger.info("Initializing OpenAI client...")
    openai_client = OpenAIClientWrapper()
    
    logger.info("Loading FAISS index...")
    vector_store = FAISSVectorStore()
    vector_store.load(settings.FAISS_INDEX_PATH)
    
    logger.info("Initializing RAG retriever...")
    retriever = RAGRetriever(
        vector_store=vector_store,
        openai_client=openai_client.client
    )
    
    logger.info("Initializing components...")
    parser = InputParser(openai_client)
    checker = EligibilityChecker(openai_client)
    
    return {
        'openai_client': openai_client,
        'vector_store': vector_store,
        'retriever': retriever,
        'parser': parser,
        'checker': checker
    }


@measure_time("2. Report Parsing (includes LLM call)")
def test_parsing(parser: InputParser) -> Any:
    """Test report parsing performance."""
    logger.info(f"Parsing report ({len(SAMPLE_REPORT)} chars)...")
    logger.info(f"Model: {settings.LLM_MODEL}")
    logger.info(f"Max tokens: {settings.MAX_TOKENS}")
    logger.info(f"Temperature: {settings.TEMPERATURE}")
    
    parsed = parser.parse_report(SAMPLE_REPORT)
    
    logger.info(f"Extracted: {len(parsed.drugs)} drugs, {len(parsed.diagnoses)} diagnoses")
    for drug in parsed.drugs:
        logger.info(f"  - Drug: {drug.etkin_madde}")
    
    return parsed


@measure_time("3. RAG Retrieval (includes embeddings)")
def test_retrieval(retriever: RAGRetriever, parsed_report: Any) -> Dict[str, Any]:
    """Test RAG retrieval performance."""
    if not parsed_report.drugs:
        logger.warning("No drugs to retrieve for")
        return {}
    
    logger.info(f"Retrieving chunks for {len(parsed_report.drugs)} drug(s)...")
    logger.info(f"Top K: {settings.TOP_K_CHUNKS}")
    logger.info(f"Parallel embeddings: {settings.PARALLEL_EMBEDDINGS}")
    logger.info(f"Cache embeddings: {settings.CACHE_EMBEDDINGS}")
    
    diagnosis = parsed_report.diagnoses[0] if parsed_report.diagnoses else None
    
    results, timings = retriever.retrieve_for_multiple_drugs(
        drugs=parsed_report.drugs,
        diagnosis=diagnosis,
        patient=parsed_report.patient,
        top_k_per_drug=settings.TOP_K_CHUNKS
    )
    
    logger.info(f"\nRetrieval timings:")
    for key, value in timings.items():
        logger.info(f"  {key}: {value:.1f}ms")
    
    for drug_name, chunks in results.items():
        logger.info(f"  {drug_name}: {len(chunks)} chunks retrieved")
    
    return results


@measure_time("4. Eligibility Checking (includes LLM call)")
def test_eligibility(checker: EligibilityChecker, parsed_report: Any, sut_chunks: Dict[str, Any]) -> Any:
    """Test eligibility checking performance."""
    if not parsed_report.drugs:
        logger.warning("No drugs to check")
        return []
    
    logger.info(f"Checking eligibility for {len(parsed_report.drugs)} drug(s)...")
    logger.info(f"Model: {settings.LLM_MODEL}")
    logger.info(f"Batched processing: Enabled")
    
    diagnosis = parsed_report.diagnoses[0] if parsed_report.diagnoses else None
    
    results = checker.check_multiple_drugs(
        drugs=parsed_report.drugs,
        diagnoses=parsed_report.diagnoses,
        patient=parsed_report.patient,
        doctor=parsed_report.doctor,
        sut_chunks_per_drug=sut_chunks,
        explanations=parsed_report.explanations
    )
    
    logger.info(f"\nEligibility results:")
    for result in results:
        logger.info(f"  {result.drug_name}: {result.status} (confidence: {result.confidence:.2f})")
    
    return results


def run_full_benchmark():
    """Run complete benchmark suite."""
    logger.info("\n" + "="*80)
    logger.info(" 🚀 PHARMACY AGENT PERFORMANCE BENCHMARK")
    logger.info("="*80)
    logger.info(f"\nConfiguration:")
    logger.info(f"  LLM Model: {settings.LLM_MODEL}")
    logger.info(f"  Embedding Model: {settings.EMBEDDING_MODEL}")
    logger.info(f"  Max Tokens: {settings.MAX_TOKENS}")
    logger.info(f"  Temperature: {settings.TEMPERATURE}")
    logger.info(f"  Top K Chunks: {settings.TOP_K_CHUNKS}")
    logger.info(f"  Chunk Size: {settings.CHUNK_SIZE}")
    logger.info(f"  Parallel Embeddings: {settings.PARALLEL_EMBEDDINGS}")
    logger.info(f"  Cache Embeddings: {settings.CACHE_EMBEDDINGS}")
    
    total_start = time.time()
    timings = {}
    
    try:
        # 1. Initialize
        components, t1 = test_initialization()
        timings['initialization'] = t1
        
        # 2. Parse
        parsed_report, t2 = test_parsing(components['parser'])
        timings['parsing'] = t2
        
        # 3. Retrieve
        sut_chunks, t3 = test_retrieval(components['retriever'], parsed_report)
        timings['retrieval'] = t3
        
        # 4. Check eligibility
        results, t4 = test_eligibility(components['checker'], parsed_report, sut_chunks)
        timings['eligibility'] = t4
        
        total_time = time.time() - total_start
        
        # Print summary
        logger.info("\n" + "="*80)
        logger.info(" 📊 BENCHMARK SUMMARY")
        logger.info("="*80)
        logger.info(f"\n{'Component':<30} {'Time (s)':<15} {'Time (ms)':<15} {'% of Total':<15}")
        logger.info("-" * 80)
        
        for name, t in timings.items():
            pct = (t / total_time) * 100
            logger.info(f"{name.title():<30} {t:>10.2f}s     {t*1000:>10.1f}ms     {pct:>10.1f}%")
        
        logger.info("-" * 80)
        logger.info(f"{'TOTAL':<30} {total_time:>10.2f}s     {total_time*1000:>10.1f}ms     {100:>10.1f}%")
        logger.info("="*80)
        
        # Performance assessment
        logger.info("\n📈 PERFORMANCE ASSESSMENT:")
        
        if timings['parsing'] < 10:
            logger.info("  ✅ Parsing: EXCELLENT (< 10s)")
        elif timings['parsing'] < 20:
            logger.info("  ✅ Parsing: GOOD (< 20s)")
        elif timings['parsing'] < 30:
            logger.info("  ⚠️  Parsing: ACCEPTABLE (< 30s)")
        else:
            logger.info("  ❌ Parsing: SLOW (> 30s) - Consider optimizing")
        
        if timings['retrieval'] < 1:
            logger.info("  ✅ Retrieval: EXCELLENT (< 1s)")
        elif timings['retrieval'] < 3:
            logger.info("  ✅ Retrieval: GOOD (< 3s)")
        else:
            logger.info("  ⚠️  Retrieval: SLOW (> 3s) - Check embeddings/cache")
        
        if timings['eligibility'] < 20:
            logger.info("  ✅ Eligibility: EXCELLENT (< 20s)")
        elif timings['eligibility'] < 40:
            logger.info("  ✅ Eligibility: GOOD (< 40s)")
        elif timings['eligibility'] < 60:
            logger.info("  ⚠️  Eligibility: ACCEPTABLE (< 60s)")
        else:
            logger.info("  ❌ Eligibility: SLOW (> 60s) - Consider faster model")
        
        if total_time < 40:
            logger.info(f"\n🎉 Overall: EXCELLENT! Total time: {total_time:.1f}s")
        elif total_time < 60:
            logger.info(f"\n✅ Overall: GOOD! Total time: {total_time:.1f}s")
        else:
            logger.info(f"\n⚠️  Overall: Consider optimizations. Total time: {total_time:.1f}s")
        
        logger.info("\n💡 TIP: Run this benchmark multiple times. The 2nd+ runs should be")
        logger.info("   faster due to embedding caching!")
        
    except Exception as e:
        logger.error(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(run_full_benchmark())
