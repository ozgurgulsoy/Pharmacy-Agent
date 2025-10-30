#!/usr/bin/env python3
"""
Chunking Strategy Evaluation Script

This script helps you test different chunking strategies and parameters
to find the optimal configuration for your RAG system.

Usage:
    python scripts/evaluate_chunking.py --strategy semantic --chunk-size 2048
    python scripts/evaluate_chunking.py --run-all-tests
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import argparse
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import json
from datetime import datetime

from document_processing.pdf_loader import PDFLoader
from document_processing.chunker import SUTDocumentChunker
from document_processing.embeddings import EmbeddingGenerator
from llm.openai_client import OpenAIClientWrapper
from rag.faiss_store import FAISSVectorStore
from rag.retriever import RAGRetriever
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EvaluationQuestion:
    """A test question with expected answer information."""
    question: str
    expected_section: str  # Expected SUT section (e.g., "4.2.28")
    expected_keywords: List[str]  # Keywords that should appear in the answer
    description: str  # What this question tests


# Golden Question Set - Customize these for your SUT document
GOLDEN_QUESTIONS = [
    EvaluationQuestion(
        question="Ezetimib için hangi şartlar gerekli?",
        expected_section="4.2.28",
        expected_keywords=["ezetimib", "kolesterol", "LDL"],
        description="Tests specific drug condition retrieval"
    ),
    EvaluationQuestion(
        question="Multipl skleroz tedavisinde interferon kullanımı için hangi koşullar var?",
        expected_section="4.2.28.A",
        expected_keywords=["interferon", "multipl skleroz", "MS"],
        description="Tests complex medical condition matching"
    ),
    EvaluationQuestion(
        question="Pulmoner hipertansiyon tedavisinde iloprost ne zaman kullanılır?",
        expected_section="4.2.28.C",
        expected_keywords=["iloprost", "pulmoner hipertansiyon", "WHO"],
        description="Tests specific treatment protocol retrieval"
    ),
    EvaluationQuestion(
        question="Yaşa bağlı makula dejenerasyonu için anti-VEGF tedavisi şartları nelerdir?",
        expected_section="4.2.28",
        expected_keywords=["VEGF", "makula", "göz"],
        description="Tests ophthalmology-specific queries"
    ),
    EvaluationQuestion(
        question="Endometriozis tedavisinde dienogest kullanımı için gerekli koşullar?",
        expected_section="4.2.28",
        expected_keywords=["dienogest", "endometrioz"],
        description="Tests gynecology medication conditions"
    ),
]


class ChunkingEvaluator:
    """Evaluates different chunking strategies."""

    def __init__(self, sut_pdf_path: str):
        """
        Initialize evaluator.
        
        Args:
            sut_pdf_path: Path to SUT PDF file
        """
        self.sut_pdf_path = sut_pdf_path
        self.pdf_loader = PDFLoader()
        
    def evaluate_strategy(
        self, 
        strategy: str,
        chunk_size: int,
        chunk_overlap: int,
        questions: List[EvaluationQuestion] = GOLDEN_QUESTIONS
    ) -> Dict[str, Any]:
        """
        Evaluate a chunking strategy.
        
        Args:
            strategy: Chunking strategy ("semantic", "fixed", "hybrid")
            chunk_size: Chunk size in characters
            chunk_overlap: Overlap size in characters
            questions: List of test questions
            
        Returns:
            Evaluation results
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Evaluating: {strategy} strategy")
        logger.info(f"Chunk Size: {chunk_size} chars (~{chunk_size//4} tokens)")
        logger.info(f"Overlap: {chunk_overlap} chars ({chunk_overlap/chunk_size*100:.1f}%)")
        logger.info(f"{'='*80}\n")
        
        # Temporarily override settings
        original_strategy = settings.CHUNKING_STRATEGY
        original_chunk_size = settings.CHUNK_SIZE
        original_overlap = settings.CHUNK_OVERLAP
        
        settings.CHUNKING_STRATEGY = strategy
        settings.CHUNK_SIZE = chunk_size
        settings.CHUNK_OVERLAP = chunk_overlap
        
        try:
            # Load and chunk document
            logger.info("Loading PDF...")
            text = self.pdf_loader.load_pdf(self.sut_pdf_path)
            
            logger.info("Chunking document...")
            chunker = SUTDocumentChunker(strategy=strategy)
            chunks = chunker.chunk_document(text)
            
            # Analyze chunks
            chunk_stats = self._analyze_chunks(chunks)
            
            # Create embeddings and index
            logger.info("Creating embeddings...")
            openai_client = OpenAIClientWrapper()
            embedding_gen = EmbeddingGenerator(client=openai_client.client)
            embeddings_data = embedding_gen.create_embeddings(chunks)
            
            # Create temporary FAISS index
            logger.info("Building FAISS index...")
            faiss_store = FAISSVectorStore()
            faiss_store.add_embeddings(embeddings_data)
            
            # Test retrieval
            logger.info("Testing retrieval...")
            
            retrieval_results = []
            for i, question in enumerate(questions):
                logger.info(f"\nQuestion {i+1}/{len(questions)}: {question.question}")
                
                # Create simple query embedding and search directly
                query_embedding = embedding_gen.create_query_embedding(question.question)
                retrieved_chunks = faiss_store.search(
                    query_embedding=query_embedding,
                    top_k=5
                )
                
                # Evaluate results
                result = self._evaluate_retrieval(question, retrieved_chunks)
                retrieval_results.append(result)
                
                logger.info(f"  ✓ Section Match: {result['section_match']}")
                logger.info(f"  ✓ Keyword Coverage: {result['keyword_coverage']:.1%}")
                logger.info(f"  ✓ Avg Similarity: {result['avg_similarity']:.3f}")
            
            # Calculate overall metrics
            overall_metrics = self._calculate_overall_metrics(retrieval_results)
            
            results = {
                "strategy": strategy,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "overlap_percentage": chunk_overlap / chunk_size * 100,
                "chunk_stats": chunk_stats,
                "retrieval_results": retrieval_results,
                "overall_metrics": overall_metrics,
                "timestamp": datetime.now().isoformat()
            }
            
            return results
            
        finally:
            # Restore original settings
            settings.CHUNKING_STRATEGY = original_strategy
            settings.CHUNK_SIZE = original_chunk_size
            settings.CHUNK_OVERLAP = original_overlap
    
    def _analyze_chunks(self, chunks: List) -> Dict[str, Any]:
        """Analyze chunk statistics."""
        sizes = [len(chunk.content) for chunk in chunks]
        
        return {
            "total_chunks": len(chunks),
            "avg_size": sum(sizes) / len(sizes) if sizes else 0,
            "min_size": min(sizes) if sizes else 0,
            "max_size": max(sizes) if sizes else 0,
            "avg_tokens": sum(sizes) / len(sizes) / 4 if sizes else 0,  # Rough estimate
        }
    
    def _evaluate_retrieval(
        self, 
        question: EvaluationQuestion, 
        retrieved_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Evaluate retrieval quality for a question."""
        
        # Check if expected section is in top results
        section_match = False
        for chunk in retrieved_chunks[:3]:  # Check top 3
            section = chunk.get('metadata', {}).get('section', '')
            if question.expected_section in section:
                section_match = True
                break
        
        # Check keyword coverage
        retrieved_text = ' '.join([
            chunk.get('metadata', {}).get('content', '') 
            for chunk in retrieved_chunks
        ]).lower()
        
        keyword_matches = sum(
            1 for keyword in question.expected_keywords 
            if keyword.lower() in retrieved_text
        )
        keyword_coverage = keyword_matches / len(question.expected_keywords) if question.expected_keywords else 0
        
        # Average similarity score
        avg_similarity = sum(
            chunk.get('score', 0) for chunk in retrieved_chunks
        ) / len(retrieved_chunks) if retrieved_chunks else 0
        
        return {
            "question": question.question,
            "description": question.description,
            "section_match": section_match,
            "keyword_coverage": keyword_coverage,
            "avg_similarity": avg_similarity,
            "top_chunk_size": len(retrieved_chunks[0].get('metadata', {}).get('content', '')) if retrieved_chunks else 0,
        }
    
    def _calculate_overall_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate overall performance metrics."""
        if not results:
            return {}
        
        return {
            "section_match_rate": sum(r['section_match'] for r in results) / len(results),
            "avg_keyword_coverage": sum(r['keyword_coverage'] for r in results) / len(results),
            "avg_similarity": sum(r['avg_similarity'] for r in results) / len(results),
        }
    
    def run_comprehensive_evaluation(self) -> List[Dict[str, Any]]:
        """Run evaluation with multiple configurations."""
        configurations = [
            # Small chunks (high precision, potential fragmentation)
            ("semantic", 1024, 128),
            ("fixed", 1024, 128),
            ("hybrid", 1024, 128),
            
            # Medium chunks (balanced)
            ("semantic", 2048, 256),
            ("fixed", 2048, 256),
            ("hybrid", 2048, 256),
            
            # Large chunks (high context, potential noise)
            ("semantic", 4096, 512),
            ("fixed", 4096, 512),
            ("hybrid", 4096, 512),
        ]
        
        all_results = []
        
        for strategy, chunk_size, overlap in configurations:
            try:
                results = self.evaluate_strategy(strategy, chunk_size, overlap)
                all_results.append(results)
            except Exception as e:
                logger.error(f"Error evaluating {strategy}/{chunk_size}: {e}")
                continue
        
        # Save results
        output_file = f"data/chunking_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Evaluation complete! Results saved to: {output_file}")
        logger.info(f"{'='*80}\n")
        
        # Print summary
        self._print_summary(all_results)
        
        return all_results
    
    def _print_summary(self, all_results: List[Dict[str, Any]]):
        """Print evaluation summary."""
        print("\n" + "="*80)
        print("EVALUATION SUMMARY")
        print("="*80)
        print(f"\n{'Strategy':<12} {'Size':<8} {'Overlap':<8} {'Chunks':<8} {'Section':<10} {'Keywords':<10} {'Similarity':<10}")
        print("-" * 80)
        
        for result in all_results:
            strategy = result['strategy']
            size = result['chunk_size']
            overlap = f"{result['overlap_percentage']:.0f}%"
            chunks = result['chunk_stats']['total_chunks']
            metrics = result['overall_metrics']
            
            print(f"{strategy:<12} {size:<8} {overlap:<8} {chunks:<8} "
                  f"{metrics['section_match_rate']:<10.1%} "
                  f"{metrics['avg_keyword_coverage']:<10.1%} "
                  f"{metrics['avg_similarity']:<10.3f}")
        
        print("="*80)
        
        # Find best configuration
        best = max(all_results, key=lambda x: (
            x['overall_metrics']['section_match_rate'] * 0.5 +
            x['overall_metrics']['avg_keyword_coverage'] * 0.3 +
            x['overall_metrics']['avg_similarity'] * 0.2
        ))
        
        print(f"\n🏆 BEST CONFIGURATION:")
        print(f"   Strategy: {best['strategy']}")
        print(f"   Chunk Size: {best['chunk_size']} chars (~{best['chunk_size']//4} tokens)")
        print(f"   Overlap: {best['chunk_overlap']} chars ({best['overlap_percentage']:.1f}%)")
        print(f"   Section Match Rate: {best['overall_metrics']['section_match_rate']:.1%}")
        print(f"   Keyword Coverage: {best['overall_metrics']['avg_keyword_coverage']:.1%}")
        print("="*80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Evaluate chunking strategies")
    parser.add_argument("--strategy", type=str, choices=["semantic", "fixed", "hybrid"],
                       help="Chunking strategy to evaluate")
    parser.add_argument("--chunk-size", type=int, default=2048,
                       help="Chunk size in characters")
    parser.add_argument("--overlap", type=int, default=256,
                       help="Chunk overlap in characters")
    parser.add_argument("--run-all-tests", action="store_true",
                       help="Run comprehensive evaluation with all configurations")
    parser.add_argument("--sut-path", type=str, default=settings.SUT_PDF_PATH,
                       help="Path to SUT PDF file")
    
    args = parser.parse_args()
    
    evaluator = ChunkingEvaluator(args.sut_path)
    
    if args.run_all_tests:
        evaluator.run_comprehensive_evaluation()
    elif args.strategy:
        results = evaluator.evaluate_strategy(
            args.strategy, 
            args.chunk_size, 
            args.overlap
        )
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
