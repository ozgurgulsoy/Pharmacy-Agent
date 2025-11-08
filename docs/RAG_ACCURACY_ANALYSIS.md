# 🎯 RAG System Accuracy Analysis & Improvement Plan

**Date:** November 8, 2025  
**System:** Pharmacy Agent - SUT Eligibility Checker  
**Current Status:** Production system with multi-document retrieval (SUT + EK-4)

---

## 📊 Executive Summary

Your RAG system is **well-architected** with:
- ✅ Multi-document retrieval (SUT + 4 EK-4 variants)
- ✅ Hybrid search (keyword + semantic)
- ✅ Embedding caching for performance
- ✅ Semantic chunking strategy
- ✅ Turkish language support (Qwen3 embeddings)

**Key Finding:** Your accuracy bottleneck is NOT in chunking or embeddings, but in:
1. **Metadata completeness** (missing doc_type/doc_source fields)
2. **Retrieval evaluation** (no systematic accuracy measurement)
3. **Chunk quality validation** (no automated testing)

---

## 🏗️ Current System Architecture

### **Embedding Pipeline**
```
Document → PDF Loader → Semantic Chunker → Qwen3 Embeddings → FAISS Index
                           ↓                    ↓
                    ChunkMetadata        4096-dimensional
                    (doc_type, etc.)     vectors
```

### **Retrieval Pipeline**
```
Query → EK-4 Detection → Query Embedding → Multi-Doc Search → Hybrid Rerank → Top-K
           ↓                                      ↓
    ["EK-4/D", ...]                    SUT + EK-4/D + EK-4/E + ...
```

### **Current Metrics**
- **Index Size:** 578 vectors (estimated from summary)
- **Chunk Size:** 2048 chars (~512 tokens) - GOOD for regulatory text
- **Overlap:** 256 chars (12.5%) - GOOD for context preservation
- **Top-K:** 3-5 chunks (increased for multi-doc)
- **Strategy:** Semantic (paragraph-preserving)

---

## 🔬 Accuracy Assessment Framework

### **1. Retrieval Accuracy (What We Need to Measure)**

#### A. **Hit Rate (Recall@K)**
*Does the system retrieve relevant chunks?*

```python
# Pseudo-metric
Hit Rate = (Queries with ≥1 relevant chunk in top-K) / Total queries
```

**Current Status:** ❌ **Not Measured**

**Target:** ≥85% for K=3, ≥95% for K=5

#### B. **Mean Reciprocal Rank (MRR)**
*How high are relevant chunks ranked?*

```python
MRR = Average(1 / rank_of_first_relevant_chunk)
```

**Current Status:** ❌ **Not Measured**

**Target:** ≥0.6 (relevant chunk in top 2 on average)

#### C. **NDCG@K (Normalized Discounted Cumulative Gain)**
*Are the most relevant chunks ranked highest?*

**Current Status:** ❌ **Not Measured**

**Target:** ≥0.7 for K=5

---

## 🚨 Critical Issues Identified

### **Issue #1: Missing Metadata Fields** 🔥
**Severity:** CRITICAL  
**Impact:** Multi-document retrieval failing

**Problem:**
```json
// Current metadata (faiss_metadata.json)
{
  "id": "sut_chunk_0001",
  "content": "...",
  "section": "4.2.28",
  "keywords": [...],
  // ❌ MISSING: doc_type
  // ❌ MISSING: doc_source
}
```

**Solution:**
```bash
# Rebuild FAISS index with complete metadata
python scripts/setup_faiss.py
```

**Verification:**
```python
# After rebuild, check metadata
import json
with open("data/faiss_metadata.json") as f:
    meta = json.load(f)
    assert "doc_type" in meta[0], "doc_type field missing!"
    assert "doc_source" in meta[0], "doc_source field missing!"
```

---

### **Issue #2: No Retrieval Evaluation** 🔥
**Severity:** HIGH  
**Impact:** Can't measure accuracy improvements

**Problem:** No golden dataset of query-chunk pairs

**Solution:** Create evaluation dataset

---

### **Issue #3: Chunking Quality Unknown** ⚠️
**Severity:** MEDIUM  
**Impact:** May lose critical context at chunk boundaries

**Problem:** No validation of chunk coherence

**Solution:** Implement chunk quality metrics

---

## 🎯 Improvement Recommendations (Prioritized)

### **Priority 1: Create Evaluation Dataset** (Week 1)

Create `tests/fixtures/retrieval_golden_set.json`:

```json
{
  "test_cases": [
    {
      "id": "gabapentin_ek4d_neuropathy",
      "query": {
        "drug": "GABAPENTİN",
        "diagnosis": "G62.9 POLİNÖROPATİ, TANIMLANMAMIŞ",
        "report_type": "Sağlık Kurulu Raporu",
        "ek4_refs": ["EK-4/D"]
      },
      "expected_chunks": [
        {
          "doc_type": "EK-4/D",
          "min_rank": 1,
          "max_rank": 3,
          "content_must_contain": ["Gabapentin", "nöropatik", "ağrı"]
        },
        {
          "doc_type": "SUT",
          "min_rank": 1,
          "max_rank": 5,
          "content_must_contain": ["Sağlık Kurulu", "raporu"]
        }
      ]
    },
    {
      "id": "ezetimib_sut_statin_intolerance",
      "query": {
        "drug": "EZETİMİB",
        "diagnosis": "E78.4 HİPERLİPİDEMİ",
        "report_type": "Uzman Hekim Raporu",
        "ek4_refs": []
      },
      "expected_chunks": [
        {
          "doc_type": "SUT",
          "min_rank": 1,
          "max_rank": 2,
          "content_must_contain": ["Ezetimib", "statin", "LDL"]
        }
      ]
    }
  ]
}
```

**Implementation:**

```python
# tests/test_retrieval_accuracy.py
import pytest
import json
from app.core.rag.retriever import RAGRetriever
from app.core.rag.faiss_store import FAISSVectorStore

@pytest.fixture
def golden_set():
    with open("tests/fixtures/retrieval_golden_set.json") as f:
        return json.load(f)

def test_retrieval_accuracy(golden_set):
    """Test retrieval accuracy against golden dataset."""
    vector_store = FAISSVectorStore()
    vector_store.load()
    retriever = RAGRetriever(vector_store)
    
    metrics = {
        "hit_rate": [],
        "mrr": [],
        "doc_type_accuracy": []
    }
    
    for test_case in golden_set["test_cases"]:
        # Build query
        drug = Drug(
            etkin_madde=test_case["query"]["drug"],
            form="Ağızdan tablet"
        )
        diagnosis = Diagnosis(tanim=test_case["query"]["diagnosis"])
        
        # Retrieve chunks
        chunks, _ = retriever.retrieve_relevant_chunks(
            drug=drug,
            diagnosis=diagnosis,
            top_k=5
        )
        
        # Evaluate
        hit = False
        first_rank = None
        doc_type_correct = 0
        
        for expected in test_case["expected_chunks"]:
            for rank, chunk in enumerate(chunks, 1):
                # Check doc_type
                if chunk["metadata"].get("doc_type") == expected["doc_type"]:
                    doc_type_correct += 1
                
                # Check content
                content = chunk["metadata"]["content"].lower()
                if all(term.lower() in content for term in expected["content_must_contain"]):
                    if expected["min_rank"] <= rank <= expected["max_rank"]:
                        hit = True
                        if first_rank is None:
                            first_rank = rank
        
        metrics["hit_rate"].append(1 if hit else 0)
        metrics["mrr"].append(1/first_rank if first_rank else 0)
        metrics["doc_type_accuracy"].append(doc_type_correct / len(test_case["expected_chunks"]))
    
    # Assert minimum accuracy
    assert sum(metrics["hit_rate"]) / len(metrics["hit_rate"]) >= 0.85, \
        f"Hit rate below threshold: {metrics}"
    assert sum(metrics["mrr"]) / len(metrics["mrr"]) >= 0.6, \
        f"MRR below threshold: {metrics}"
    
    print(f"✅ Retrieval Accuracy:")
    print(f"  Hit Rate: {sum(metrics['hit_rate']) / len(metrics['hit_rate']):.2%}")
    print(f"  MRR: {sum(metrics['mrr']) / len(metrics['mrr']):.3f}")
    print(f"  Doc Type Accuracy: {sum(metrics['doc_type_accuracy']) / len(metrics['doc_type_accuracy']):.2%}")
```

---

### **Priority 2: Chunking Quality Validation** (Week 2)

#### A. **Chunk Coherence Score**

Measure if chunks are semantically complete:

```python
# tests/test_chunk_quality.py
from app.core.document_processing.chunker import SUTDocumentChunker
from openai import OpenAI
import numpy as np

def test_chunk_coherence():
    """Test that chunks are semantically coherent."""
    chunker = SUTDocumentChunker()
    
    # Load sample SUT section
    with open("data/SUT.pdf") as f:
        text = pdf_loader.load_pdf(f)[:10000]  # Sample
    
    chunks = chunker.chunk_document(text)
    
    # Coherence metric: sentence boundary preservation
    incomplete_chunks = []
    for chunk in chunks:
        content = chunk.content.strip()
        
        # Check if chunk ends with sentence delimiter
        if not content[-1] in ".!?":
            incomplete_chunks.append(chunk.chunk_id)
        
        # Check if chunk starts with lowercase (mid-sentence)
        if content[0].islower():
            incomplete_chunks.append(chunk.chunk_id)
    
    coherence_rate = 1 - (len(incomplete_chunks) / len(chunks))
    
    print(f"Chunk Coherence: {coherence_rate:.2%}")
    print(f"Incomplete chunks: {len(incomplete_chunks)}/{len(chunks)}")
    
    # Allow 10% tolerance (some chunks naturally split at section boundaries)
    assert coherence_rate >= 0.90, f"Too many incoherent chunks: {incomplete_chunks}"
```

#### B. **Critical Information Loss Detection**

Ensure important terms aren't split across chunks:

```python
def test_no_critical_term_splitting():
    """Test that medical terms aren't split across chunk boundaries."""
    chunker = SUTDocumentChunker()
    
    critical_terms = [
        "Uzman Hekim Raporu",
        "Sağlık Kurulu Raporu",
        "nöropatik ağrı",
        "LDL kolesterol",
        "statin direnci",
        "EK-4/D Listesi"
    ]
    
    chunks = chunker.chunk_document(sample_text)
    
    # Check if any term is split
    split_terms = []
    for term in critical_terms:
        words = term.split()
        if len(words) > 1:
            # Check if first word is at end of chunk and second at start of next
            for i in range(len(chunks) - 1):
                chunk1_end = chunks[i].content[-50:].lower()
                chunk2_start = chunks[i+1].content[:50].lower()
                
                if words[0].lower() in chunk1_end and words[1].lower() in chunk2_start:
                    split_terms.append((term, i))
    
    assert len(split_terms) == 0, f"Terms split across boundaries: {split_terms}"
```

---

### **Priority 3: Embedding Quality Analysis** (Week 2)

#### A. **Semantic Similarity Validation**

Test that similar content produces similar embeddings:

```python
def test_embedding_similarity():
    """Test that semantically similar chunks have high cosine similarity."""
    embedding_gen = EmbeddingGenerator()
    
    # Similar content pairs
    pairs = [
        (
            "Ezetimib statin ile birlikte kullanılır. LDL düşürmede etkilidir.",
            "Ezetimib statinlerle kombinasyonda kullanılabilir. LDL kolesterol azaltır."
        ),
        (
            "Sağlık Kurulu Raporu ile reçete edilir.",
            "Sağlık Kurulu Raporu gereklidir."
        )
    ]
    
    for text1, text2 in pairs:
        emb1 = embedding_gen.create_query_embedding(text1)
        emb2 = embedding_gen.create_query_embedding(text2)
        
        # Cosine similarity
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        
        print(f"Similarity: {similarity:.3f}")
        print(f"  Text 1: {text1[:50]}...")
        print(f"  Text 2: {text2[:50]}...")
        
        # Similar content should have >0.7 similarity
        assert similarity >= 0.70, f"Low similarity for similar content: {similarity}"
```

#### B. **Turkish Language Handling**

Verify embeddings handle Turkish characters correctly:

```python
def test_turkish_embedding_quality():
    """Test that Turkish-specific characters are handled correctly."""
    embedding_gen = EmbeddingGenerator()
    
    # Test Turkish characters
    turkish_text = "Şeker hastalığı için özel rapor gereklidir. Çünkü sürekli kullanım şarttır."
    ascii_text = "Seker hastaligi icin ozel rapor gereklidir. Cunku surekli kullanim sarttir."
    
    emb_turkish = embedding_gen.create_query_embedding(turkish_text)
    emb_ascii = embedding_gen.create_query_embedding(ascii_text)
    
    # Should be different (not just ASCII conversion)
    similarity = np.dot(emb_turkish, emb_ascii) / (
        np.linalg.norm(emb_turkish) * np.linalg.norm(emb_ascii)
    )
    
    # Not exact match, but should be similar (0.6-0.9)
    assert 0.60 <= similarity <= 0.90, \
        f"Turkish handling issue: similarity={similarity} (should be 0.6-0.9)"
    
    print(f"✅ Turkish character handling OK: similarity={similarity:.3f}")
```

---

### **Priority 4: Hybrid Search Optimization** (Week 3)

Your current hybrid search combines keyword + semantic. Let's optimize the weights:

#### Current Implementation Analysis

```python
# From retriever.py
def _hybrid_rerank(
    keyword_results,    # Drug index exact matches (5.0x boost)
    semantic_results,   # Vector similarity
    drug_name,
    top_k,
    keyword_boost=5.0
):
    # Keyword exact matches: 5.0x
    # Content partial matches: 2.0x
    # Semantic-only matches: 1.0x
```

**Recommendation:** Test different boost values

```python
# tests/test_hybrid_search_tuning.py
import pytest
from app.core.rag.retriever import RAGRetriever

@pytest.mark.parametrize("keyword_boost", [2.0, 5.0, 10.0])
def test_keyword_boost_optimization(golden_set, keyword_boost):
    """Find optimal keyword boost value."""
    retriever = RAGRetriever(vector_store)
    retriever._hybrid_rerank.keyword_boost = keyword_boost
    
    # Run retrieval tests
    metrics = evaluate_retrieval(golden_set, retriever)
    
    print(f"Keyword Boost: {keyword_boost}")
    print(f"  Hit Rate: {metrics['hit_rate']:.2%}")
    print(f"  MRR: {metrics['mrr']:.3f}")
    
    return metrics

# Find best boost value
results = []
for boost in [2.0, 5.0, 10.0]:
    metrics = test_keyword_boost_optimization(golden_set, boost)
    results.append((boost, metrics))

best_boost = max(results, key=lambda x: x[1]['mrr'])[0]
print(f"\n🎯 Optimal keyword boost: {best_boost}")
```

---

### **Priority 5: Advanced Chunking Experiments** (Week 4)

Your semantic chunking is good, but let's test alternatives:

#### A. **Hybrid Chunking with Section Headers**

```python
# Modify chunker.py
def _hybrid_chunking_v2(self, text: str) -> List[Chunk]:
    """
    Enhanced hybrid: Section-based with subsection preservation.
    
    Improvements:
    1. Never split section headers from their content
    2. Keep subsections (4.2.28.1) together
    3. Preserve condition lists intact
    """
    lines = text.split('\n')
    chunks = []
    current_section = []
    current_header = None
    
    for line in lines:
        # Detect section header (e.g., "4.2.28 Ezetimib")
        if self._is_section_header(line):
            # Save previous section
            if current_section:
                chunks.append(self._create_section_chunk(
                    header=current_header,
                    content=current_section
                ))
            
            current_header = line
            current_section = [line]
        else:
            current_section.append(line)
            
            # Size check - but don't split if in condition list
            if len('\n'.join(current_section)) > MAX_CHUNK_SIZE:
                if not self._in_condition_list(current_section[-10:]):
                    # Safe to split
                    chunks.append(self._create_section_chunk(
                        header=current_header,
                        content=current_section
                    ))
                    current_section = []
                    current_header = None
    
    return chunks

def _in_condition_list(self, lines: List[str]) -> bool:
    """Check if we're in a numbered/bulleted condition list."""
    list_indicators = [
        r'^\s*\d+\.',  # "1. "
        r'^\s*[a-z]\)',  # "a) "
        r'^\s*[-•]',  # "- " or "• "
    ]
    
    import re
    recent_list_items = sum(
        1 for line in lines
        if any(re.match(pattern, line) for pattern in list_indicators)
    )
    
    return recent_list_items >= 2  # At least 2 list items in last 10 lines
```

#### B. **Sentence-Window Chunking**

Alternative strategy for testing:

```python
def _sentence_window_chunking(self, text: str) -> List[Chunk]:
    """
    Sentence-window chunking: Fixed number of sentences per chunk.
    
    Pros: Clean boundaries, good for Q&A
    Cons: May break section logic
    """
    sentences = self._split_sentences(text)
    
    window_size = 8  # ~8 sentences per chunk
    overlap = 2  # 2-sentence overlap
    
    chunks = []
    for i in range(0, len(sentences), window_size - overlap):
        window = sentences[i:i + window_size]
        chunk_text = ' '.join(window)
        
        if len(chunk_text) >= MIN_CHUNK_SIZE:
            chunks.append(self._create_chunk(
                text=chunk_text,
                idx=len(chunks),
                start_ref=i,
                end_ref=i + len(window)
            ))
    
    return chunks
```

**Test Comparison:**

```python
# tests/test_chunking_strategies.py
@pytest.mark.parametrize("strategy", ["semantic", "hybrid_v2", "sentence_window"])
def test_chunking_strategy_comparison(strategy, golden_set):
    """Compare different chunking strategies on retrieval accuracy."""
    
    # Re-index with strategy
    chunker = SUTDocumentChunker(strategy=strategy)
    # ... rebuild index ...
    
    # Test retrieval
    metrics = evaluate_retrieval(golden_set, retriever)
    
    print(f"\nStrategy: {strategy}")
    print(f"  Hit Rate: {metrics['hit_rate']:.2%}")
    print(f"  MRR: {metrics['mrr']:.3f}")
    print(f"  Avg Chunk Size: {metrics['avg_chunk_size']:.0f} chars")
    
    return metrics
```

---

## 🧪 Complete Testing Suite

Create `tests/test_rag_system.py`:

```python
"""Comprehensive RAG system tests."""

import pytest
from pathlib import Path
import json

from app.core.rag.faiss_store import FAISSVectorStore
from app.core.rag.retriever import RAGRetriever
from app.core.document_processing.chunker import SUTDocumentChunker
from app.core.document_processing.embeddings import EmbeddingGenerator

@pytest.fixture(scope="module")
def rag_system():
    """Initialize RAG system for testing."""
    vector_store = FAISSVectorStore()
    vector_store.load()
    retriever = RAGRetriever(vector_store)
    return retriever

class TestMetadataCompleteness:
    """Test that all chunks have required metadata."""
    
    def test_metadata_fields_present(self):
        """Verify all chunks have doc_type and doc_source."""
        with open("data/faiss_metadata.json") as f:
            metadata = json.load(f)
        
        required_fields = ["id", "content", "doc_type", "doc_source", "section"]
        
        for i, chunk_meta in enumerate(metadata):
            for field in required_fields:
                assert field in chunk_meta, \
                    f"Chunk {i} missing field '{field}': {chunk_meta.get('id')}"
        
        print(f"✅ All {len(metadata)} chunks have complete metadata")
    
    def test_doc_type_values(self):
        """Verify doc_type has valid values."""
        with open("data/faiss_metadata.json") as f:
            metadata = json.load(f)
        
        valid_doc_types = ["SUT", "EK-4/D", "EK-4/E", "EK-4/F", "EK-4/G"]
        
        doc_type_counts = {}
        for chunk_meta in metadata:
            doc_type = chunk_meta.get("doc_type")
            assert doc_type in valid_doc_types, \
                f"Invalid doc_type '{doc_type}' in chunk {chunk_meta.get('id')}"
            
            doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1
        
        print(f"✅ Document type distribution:")
        for doc_type, count in sorted(doc_type_counts.items()):
            print(f"  {doc_type}: {count} chunks")

class TestRetrievalAccuracy:
    """Test retrieval system accuracy."""
    
    @pytest.fixture
    def golden_set(self):
        """Load golden dataset."""
        path = Path("tests/fixtures/retrieval_golden_set.json")
        if not path.exists():
            pytest.skip("Golden dataset not created yet")
        
        with open(path) as f:
            return json.load(f)
    
    def test_hit_rate(self, rag_system, golden_set):
        """Test hit rate metric."""
        # Implementation from Priority 1
        pass
    
    def test_mrr(self, rag_system, golden_set):
        """Test MRR metric."""
        pass
    
    def test_multi_document_retrieval(self, rag_system):
        """Test that EK-4 documents are retrieved when referenced."""
        from app.models.report import Drug, Diagnosis
        
        drug = Drug(etkin_madde="GABAPENTİN", form="Ağızdan tablet")
        diagnosis = Diagnosis(tanim="20.00 – EK-4/D Listesinde Yer Almayan Hastalıklar")
        
        chunks, _ = rag_system.retrieve_relevant_chunks(
            drug=drug,
            diagnosis=diagnosis,
            report_text="Tanı: 20.00 – EK-4/D Listesinde Yer Almayan Hastalıklar, G62.9 POLİNÖROPATİ",
            top_k=5
        )
        
        # Should have chunks from both SUT and EK-4/D
        doc_types = set(c["metadata"].get("doc_type") for c in chunks)
        
        assert "SUT" in doc_types, "No SUT chunks retrieved"
        assert "EK-4/D" in doc_types, "No EK-4/D chunks retrieved despite reference"
        
        print(f"✅ Multi-document retrieval working: {doc_types}")

class TestChunkQuality:
    """Test chunk quality metrics."""
    
    def test_chunk_size_distribution(self):
        """Test that chunk sizes are within expected range."""
        with open("data/faiss_metadata.json") as f:
            metadata = json.load(f)
        
        sizes = [len(c["content"]) for c in metadata]
        
        avg_size = sum(sizes) / len(sizes)
        min_size = min(sizes)
        max_size = max(sizes)
        
        print(f"\n📊 Chunk Size Statistics:")
        print(f"  Average: {avg_size:.0f} chars")
        print(f"  Min: {min_size} chars")
        print(f"  Max: {max_size} chars")
        print(f"  Target: {CHUNK_SIZE} chars")
        
        # Most chunks should be within 50% of target
        in_range = sum(1 for s in sizes if CHUNK_SIZE * 0.5 <= s <= CHUNK_SIZE * 1.5)
        pct_in_range = in_range / len(sizes)
        
        assert pct_in_range >= 0.70, \
            f"Only {pct_in_range:.1%} chunks in target range"
    
    def test_chunk_coherence(self):
        """Test chunk coherence (from Priority 2)."""
        pass

class TestEmbeddingQuality:
    """Test embedding quality."""
    
    def test_embedding_dimension(self):
        """Verify embeddings have correct dimension."""
        vector_store = FAISSVectorStore()
        vector_store.load()
        
        assert vector_store.dimension == EMBEDDING_DIMENSION, \
            f"Dimension mismatch: {vector_store.dimension} != {EMBEDDING_DIMENSION}"
    
    def test_turkish_language_handling(self):
        """Test Turkish character handling (from Priority 3)."""
        pass
```

---

## 📈 Monitoring & Metrics Dashboard

Create `scripts/analyze_rag_performance.py`:

```python
"""Analyze RAG system performance and generate reports."""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

def analyze_metadata_coverage():
    """Analyze metadata field coverage."""
    with open("data/faiss_metadata.json") as f:
        metadata = json.load(f)
    
    field_coverage = defaultdict(int)
    for chunk in metadata:
        for field in chunk.keys():
            field_coverage[field] += 1
    
    print("📊 Metadata Coverage:")
    for field, count in sorted(field_coverage.items()):
        pct = count / len(metadata) * 100
        print(f"  {field}: {count}/{len(metadata)} ({pct:.1f}%)")

def analyze_chunk_distribution():
    """Analyze chunk size distribution."""
    with open("data/faiss_metadata.json") as f:
        metadata = json.load(f)
    
    sizes = [len(c["content"]) for c in metadata]
    
    print("\n📊 Chunk Size Distribution:")
    print(f"  Mean: {np.mean(sizes):.0f} chars")
    print(f"  Median: {np.median(sizes):.0f} chars")
    print(f"  Std Dev: {np.std(sizes):.0f} chars")
    print(f"  Min: {min(sizes)} chars")
    print(f"  Max: {max(sizes)} chars")
    
    # Histogram
    plt.figure(figsize=(10, 6))
    plt.hist(sizes, bins=50, edgecolor='black')
    plt.axvline(np.mean(sizes), color='r', linestyle='--', label=f'Mean: {np.mean(sizes):.0f}')
    plt.xlabel('Chunk Size (characters)')
    plt.ylabel('Frequency')
    plt.title('Chunk Size Distribution')
    plt.legend()
    plt.savefig('docs/chunk_size_distribution.png')
    print("  📈 Saved histogram: docs/chunk_size_distribution.png")

def analyze_doc_type_distribution():
    """Analyze document type distribution."""
    with open("data/faiss_metadata.json") as f:
        metadata = json.load(f)
    
    doc_type_counts = defaultdict(int)
    for chunk in metadata:
        doc_type = chunk.get("doc_type", "MISSING")
        doc_type_counts[doc_type] += 1
    
    print("\n📊 Document Type Distribution:")
    total = len(metadata)
    for doc_type, count in sorted(doc_type_counts.items()):
        pct = count / total * 100
        print(f"  {doc_type}: {count} chunks ({pct:.1f}%)")

def analyze_keyword_coverage():
    """Analyze drug keyword coverage."""
    with open("data/faiss_metadata.json") as f:
        metadata = json.load(f)
    
    drug_related = sum(1 for c in metadata if c.get("drug_related", False))
    has_etkin_madde = sum(1 for c in metadata if c.get("etkin_madde", []))
    
    print("\n📊 Drug Keyword Coverage:")
    print(f"  Drug-related chunks: {drug_related}/{len(metadata)} ({drug_related/len(metadata)*100:.1f}%)")
    print(f"  Chunks with etkin_madde: {has_etkin_madde}/{len(metadata)} ({has_etkin_madde/len(metadata)*100:.1f}%)")

if __name__ == "__main__":
    print("🔍 RAG System Performance Analysis\n" + "="*50)
    
    analyze_metadata_coverage()
    analyze_chunk_distribution()
    analyze_doc_type_distribution()
    analyze_keyword_coverage()
    
    print("\n✅ Analysis complete!")
```

---

## 🎯 Action Plan Timeline

### **Week 1: Foundation**
- [ ] Rebuild FAISS index with complete metadata (`python scripts/setup_faiss.py`)
- [ ] Run `scripts/analyze_rag_performance.py` to establish baseline
- [ ] Create golden evaluation dataset (10-20 test cases from `patient_report.txt`)

### **Week 2: Testing**
- [ ] Implement `test_retrieval_accuracy.py`
- [ ] Implement `test_chunk_quality.py`
- [ ] Implement `test_embedding_quality.py`
- [ ] Run full test suite and document metrics

### **Week 3: Optimization**
- [ ] Test hybrid search boost values (2.0, 5.0, 10.0)
- [ ] Experiment with top_k values (3, 5, 7)
- [ ] A/B test chunking strategies
- [ ] Measure impact on accuracy

### **Week 4: Advanced**
- [ ] Implement enhanced chunking strategies
- [ ] Add query expansion (synonyms for Turkish medical terms)
- [ ] Implement result re-ranking with cross-encoder
- [ ] Final accuracy validation

---

## 🔬 Quick Wins (Implement Now)

### **1. Add Logging for Retrieval Analysis**

Add to `retriever.py`:

```python
def retrieve_relevant_chunks(self, drug, diagnosis, patient, top_k, report_text):
    # ... existing code ...
    
    # LOG RETRIEVAL RESULTS
    self.logger.info(f"🔍 Retrieval Results for {drug.etkin_madde}:")
    for i, chunk in enumerate(final_results[:5], 1):
        self.logger.info(f"  [{i}] Score: {chunk['score']:.3f} | "
                        f"Doc: {chunk['metadata'].get('doc_type', 'UNKNOWN')} | "
                        f"Match: {chunk.get('match_type', 'unknown')} | "
                        f"Section: {chunk['metadata'].get('section', 'N/A')}")
        self.logger.debug(f"      Content: {chunk['metadata']['content'][:100]}...")
    
    return final_results, timings
```

### **2. Add Metadata Validation on Startup**

Add to `faiss_store.py`:

```python
def load(self):
    """Load FAISS index with metadata validation."""
    # ... existing load code ...
    
    # VALIDATE METADATA
    if self.metadata:
        sample = self.metadata[0]
        required_fields = ["id", "content", "doc_type", "doc_source"]
        missing_fields = [f for f in required_fields if f not in sample]
        
        if missing_fields:
            self.logger.error(f"❌ Metadata missing required fields: {missing_fields}")
            self.logger.error(f"   Please rebuild index with: python scripts/setup_faiss.py")
            raise ValueError(f"Incomplete metadata. Missing: {missing_fields}")
        
        self.logger.info(f"✅ Metadata validation passed ({len(required_fields)} required fields)")
```

### **3. Add Quick Accuracy Check**

Create `scripts/quick_accuracy_check.py`:

```python
"""Quick sanity check for retrieval accuracy."""

from app.core.rag.faiss_store import FAISSVectorStore
from app.core.rag.retriever import RAGRetriever
from app.models.report import Drug, Diagnosis

def test_known_good_cases():
    """Test known-good retrieval cases."""
    vector_store = FAISSVectorStore()
    vector_store.load()
    retriever = RAGRetriever(vector_store)
    
    test_cases = [
        {
            "name": "Ezetimib for Hyperlipidemia",
            "drug": "EZETİMİB",
            "diagnosis": "E78.4 HİPERLİPİDEMİ",
            "expected_terms": ["ezetimib", "statin", "LDL"]
        },
        {
            "name": "Gabapentin for Neuropathy (EK-4/D)",
            "drug": "GABAPENTİN",
            "diagnosis": "20.00 – EK-4/D Listesinde Yer Almayan Hastalıklar, G62.9 POLİNÖROPATİ",
            "expected_terms": ["gabapentin", "nöropatik"],
            "expected_doc_types": ["SUT", "EK-4/D"]
        }
    ]
    
    for test in test_cases:
        print(f"\n🧪 Testing: {test['name']}")
        
        drug = Drug(etkin_madde=test["drug"], form="Ağızdan tablet")
        diagnosis = Diagnosis(tanim=test["diagnosis"])
        
        chunks, _ = retriever.retrieve_relevant_chunks(
            drug=drug,
            diagnosis=diagnosis,
            report_text=test.get("diagnosis", ""),
            top_k=5
        )
        
        # Check expected terms
        found_terms = []
        for chunk in chunks[:3]:
            content = chunk["metadata"]["content"].lower()
            for term in test["expected_terms"]:
                if term.lower() in content:
                    found_terms.append(term)
        
        coverage = len(set(found_terms)) / len(test["expected_terms"])
        
        print(f"  Term Coverage: {coverage:.1%} ({len(set(found_terms))}/{len(test['expected_terms'])})")
        
        # Check doc types if specified
        if "expected_doc_types" in test:
            doc_types = set(c["metadata"].get("doc_type") for c in chunks)
            for expected in test["expected_doc_types"]:
                if expected in doc_types:
                    print(f"  ✅ Found {expected} chunks")
                else:
                    print(f"  ❌ Missing {expected} chunks")
        
        if coverage >= 0.67:  # At least 2/3 terms found
            print(f"  ✅ PASS")
        else:
            print(f"  ❌ FAIL - Low term coverage")

if __name__ == "__main__":
    test_known_good_cases()
```

---

## 💡 Key Insights

### **Your System is Already Good** ✨

1. **Semantic chunking** is the right choice for regulatory documents
2. **Hybrid search** (keyword + semantic) is best practice
3. **Multi-document retrieval** architecture is solid
4. **Qwen3 embeddings** are excellent for Turkish

### **The Gaps** 🎯

1. **No measurement** = Can't improve systematically
2. **Missing metadata** = Multi-doc retrieval broken
3. **No validation** = Don't know when accuracy degrades

### **The Fix** 🔧

1. **Create golden dataset** (Priority 1)
2. **Rebuild index** with complete metadata
3. **Add tests** for continuous validation
4. **Measure everything** with logging

---

## 📚 Additional Resources

### **Chunking Research**
- [LlamaIndex Chunking Guide](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/)
- [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/)

### **RAG Evaluation**
- [RAGAS Framework](https://docs.ragas.io/) - Automated RAG evaluation
- [TruLens](https://www.trulens.org/) - RAG observability

### **Embedding Models**
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) - Multilingual embeddings benchmark
- [Qwen3 Embeddings](https://huggingface.co/Alibaba-NLP/gte-Qwen2-1.5B-instruct) - Your current model

---

## 🎉 Summary

**Your chunking and embeddings are NOT the problem.**

The real opportunities:
1. ✅ **Rebuild FAISS index** (critical - do this first!)
2. 📊 **Create evaluation dataset** (measure accuracy)
3. 🧪 **Add automated tests** (prevent regressions)
4. 🔍 **Add logging** (understand retrieval behavior)
5. ⚡ **Tune hyperparameters** (boost values, top_k)

**Start with the quick wins** (logging + validation), then build the evaluation framework. Don't optimize chunking until you can measure the impact!

---

**Next Steps:**
1. Run `python scripts/setup_faiss.py` to rebuild index
2. Run `scripts/analyze_rag_performance.py` to see current state
3. Create golden dataset from your test reports
4. Implement automated testing

**Questions?** Let me know which priority you want to tackle first!
