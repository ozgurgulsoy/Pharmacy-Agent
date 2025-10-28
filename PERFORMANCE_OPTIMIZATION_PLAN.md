# 🚀 Pharmacy Agent - Performance Optimization Plan

## Current Performance Analysis

### Metrics Breakdown (5 drugs):
```
Total Time:              150.93s (2.5 minutes)
├─ Report Parsing:       44.28s  (29.3%)  ⚠️ SLOW
├─ RAG Retrieval:         2.12s  (1.4%)   ✅ GOOD
│  ├─ Keyword Search:     0.00s  (O(1))   ✅ EXCELLENT
│  ├─ Embedding:          2.11s           ⚠️ CAN OPTIMIZE
│  ├─ Vector Search:      0.01s           ✅ EXCELLENT
│  └─ Reranking:          0.00s           ✅ EXCELLENT
└─ Eligibility Check:   104.52s  (69.3%)  🔴 CRITICAL BOTTLENECK
   └─ Per drug:          20.90s           🔴 TOO SLOW
```

**Performance Grade**: 🐌 Very Slow (should be <10s for 5 drugs)

---

## 🔴 Critical Issues

### Issue #1: Sequential LLM Calls in Eligibility Checking
**Impact**: 69% of total time (104.5s)

**Current Problem**:
- Despite having `_check_all_drugs_batched()`, it appears to be falling back to sequential calls
- Each drug takes ~21 seconds → 5 drugs = 105 seconds
- **Root Cause**: Likely exception in batch method causing fallback to sequential processing

**Expected with proper batching**: 
- 1 LLM call for all 5 drugs → ~25-30s total (5× speedup)

---

### Issue #2: Sequential Embedding Creation
**Impact**: 2.1s (could be <0.5s)

**Current Problem**:
```python
# In retriever.py - retrieve_for_multiple_drugs()
for drug in drugs:
    chunks, timings = self.retrieve_relevant_chunks(...)  # Sequential!
    # Each creates embedding separately
```

**Solution**: Batch embedding API calls
```python
# Instead of N calls:
for drug in drugs:
    embedding = create_query_embedding(query)  # 421ms each

# Make 1 batched call:
queries = [build_query(drug) for drug in drugs]
embeddings = client.embeddings.create(
    model="text-embedding-3-small",
    input=queries  # Batch all at once!
)
# Expected: ~500ms total for 5 drugs
```

---

### Issue #3: Report Parsing Taking 44s
**Impact**: 29% of total time

**Possible Causes**:
1. Using LLM calls for extraction (instead of regex/NLP)
2. Sequential processing of sections
3. Inefficient string operations

**Investigation Needed**: Check if `InputParser` is making LLM calls

---

## 🎯 Optimization Strategy

### Phase 1: Quick Wins (Expected: 150s → 50s)

#### 1.1 Fix Batch LLM Eligibility Checking
**Target**: 104s → 25s (4× faster)

**Action**: Debug why `_check_all_drugs_batched()` is failing

```python
# Add detailed logging in eligibility_checker.py
def check_multiple_drugs(...):
    try:
        logger.info(f"🚀 Attempting batched check for {len(drugs)} drugs")
        results = self._check_all_drugs_batched(...)
        logger.info(f"✅ Batched check succeeded in {time}s")
        return results
    except Exception as e:
        logger.error(f"❌ Batch failed: {e}, falling back to sequential")
        logger.exception(e)  # Full stack trace
        # Fallback...
```

**Potential Issues**:
- JSON parsing errors (LLM not returning proper format)
- Token limit exceeded (too many drugs in one prompt)
- Rate limiting

**Solutions**:
- Add retry logic
- Split into sub-batches if needed (2-3 drugs per batch)
- Better error handling in JSON parsing

---

#### 1.2 Batch Embedding Creation
**Target**: 2.1s → 0.5s (4× faster)

**Current Code** (src/rag/retriever.py):
```python
def retrieve_for_multiple_drugs(...):
    results = {}
    for drug in drugs:
        # Each creates separate embedding
        chunks, timings = self.retrieve_relevant_chunks(drug, ...)
```

**Optimized Code**:
```python
def retrieve_for_multiple_drugs(...):
    # 1. Build all queries first
    queries = []
    query_metadata = []
    for drug in drugs:
        query_text = self._build_query_text(drug, diagnosis, patient)
        queries.append(query_text)
        query_metadata.append({"drug": drug})
    
    # 2. Batch create embeddings (1 API call)
    start = time.time()
    if self.embedding_generator.provider == "openai":
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=queries  # Batch all at once!
        )
        embeddings = [item.embedding for item in response.data]
    else:
        # Ollama doesn't support batching, keep sequential
        embeddings = [
            self.embedding_generator.create_query_embedding(q) 
            for q in queries
        ]
    embedding_time = (time.time() - start) * 1000
    
    # 3. Now do vector search for each
    results = {}
    for drug, embedding, meta in zip(drugs, embeddings, query_metadata):
        # Search with pre-computed embedding
        chunks = self._search_with_embedding(
            drug=drug,
            embedding=embedding,
            diagnosis=diagnosis,
            patient=patient,
            top_k=top_k_per_drug
        )
        results[drug.etkin_madde] = chunks
    
    return results, timings
```

---

#### 1.3 Optimize Report Parsing
**Target**: 44s → 2s (if using LLM) or <1s (if using regex)

**Investigation Steps**:
1. Check if `InputParser.parse_report()` calls OpenAI
2. If yes, consider:
   - Using regex for structured data
   - Using smaller/faster model (gpt-3.5-turbo)
   - Caching common patterns

**Recommendation**: 
- Use **regex/string parsing** for structured report fields
- Only use LLM for **ambiguous** sections (explanations, unstructured text)

---

### Phase 2: Advanced Optimizations (Expected: 50s → 15s)

#### 2.1 Parallel LLM Calls with asyncio
```python
import asyncio
from openai import AsyncOpenAI

class EligibilityChecker:
    def __init__(self):
        self.async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    async def check_eligibility_async(self, drug, ...):
        response = await self.async_client.chat.completions.create(...)
        return self._parse_response(response, drug.etkin_madde)
    
    async def check_multiple_drugs_parallel(self, drugs, ...):
        # Run all checks in parallel
        tasks = [
            self.check_eligibility_async(drug, ...)
            for drug in drugs
        ]
        results = await asyncio.gather(*tasks)
        return results
```

**Expected**: 5 parallel calls → ~25s (limited by OpenAI rate limits)

---

#### 2.2 Implement Caching
```python
from functools import lru_cache
import hashlib

class RAGRetriever:
    def __init__(self):
        self.embedding_cache = {}
    
    def create_query_embedding(self, query_text: str):
        # Cache embeddings for identical queries
        cache_key = hashlib.md5(query_text.encode()).hexdigest()
        
        if cache_key in self.embedding_cache:
            logger.info("✅ Cache hit for embedding")
            return self.embedding_cache[cache_key]
        
        embedding = self.embedding_generator.create_query_embedding(query_text)
        self.embedding_cache[cache_key] = embedding
        return embedding
```

---

#### 2.3 Use Faster Embedding Model
**Current**: `qwen3-embedding:8b` (Ollama) → 421ms per embedding

**Options**:
1. **OpenAI text-embedding-3-small**: ~100ms per embedding, supports batching
2. **Sentence Transformers (local)**: ~50ms per embedding, no API calls

```python
# Option: Use local embedding model
from sentence_transformers import SentenceTransformer

class EmbeddingGenerator:
    def __init__(self):
        # Use lightweight local model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        # 384 dimensions, very fast
    
    def create_embeddings_batch(self, texts: List[str]):
        # Batch encoding
        embeddings = self.model.encode(texts, batch_size=32)
        return embeddings.tolist()
```

**Expected**: 2.1s → 0.2s (10× faster)

---

### Phase 3: Infrastructure Optimizations

#### 3.1 GPU Acceleration for Embeddings (if using local model)
```bash
# Use CUDA if available
pip install sentence-transformers[cuda]
```

#### 3.2 FAISS GPU Index
```python
import faiss

# If GPU available
if faiss.get_num_gpus() > 0:
    gpu_resource = faiss.StandardGpuResources()
    index = faiss.index_cpu_to_gpu(gpu_resource, 0, index)
```

#### 3.3 Streaming LLM Responses
```python
# For better perceived performance
async def check_eligibility_streaming(self, ...):
    stream = await self.client.chat.completions.create(
        ...,
        stream=True
    )
    
    async for chunk in stream:
        # Process partial results as they arrive
        yield chunk
```

---

## 📈 Expected Performance Improvements

### Baseline (Current)
```
Total: 150.93s
├─ Parsing:      44.28s
├─ RAG:           2.12s
└─ Eligibility: 104.52s
```

### After Phase 1 (Quick Wins)
```
Total: ~50s (3× faster)
├─ Parsing:       2.00s  (regex-based)
├─ RAG:           0.50s  (batched embeddings)
└─ Eligibility:  25.00s  (batched LLM)
```

### After Phase 2 (Advanced)
```
Total: ~15s (10× faster)
├─ Parsing:       1.00s  (optimized)
├─ RAG:           0.20s  (local embeddings)
└─ Eligibility:  12.00s  (parallel + caching)
```

### Target (Optimal)
```
Total: <10s (15× faster)
├─ Parsing:       0.50s
├─ RAG:           0.10s
└─ Eligibility:   8.00s
```

**Performance Grade**: ✨ Very Good

---

## 🛠️ Implementation Priority

### Week 1: Critical Fixes
1. ✅ **Fix batched eligibility checking** (69% of time)
2. ✅ **Batch embedding creation** (1.4% but easy win)
3. ✅ **Optimize report parsing** (29% of time)

**Expected Result**: 150s → 50s (usable!)

### Week 2: Advanced Optimizations
4. Implement async parallel LLM calls
5. Add embedding caching
6. Consider local embedding model

**Expected Result**: 50s → 15s (great!)

### Future: Nice to Have
7. GPU acceleration
8. Response streaming
9. Request deduplication

---

## 🎯 Immediate Action Items

### 1. Debug Batch LLM Implementation
**File**: `src/llm/eligibility_checker.py`

Add logging:
```python
def check_multiple_drugs(self, drugs, ...):
    logger.info(f"🔍 Starting check for {len(drugs)} drugs")
    start = time.time()
    
    try:
        logger.info("🚀 Attempting batched LLM call")
        results = self._check_all_drugs_batched(...)
        elapsed = time.time() - start
        logger.info(f"✅ Batched check completed in {elapsed:.2f}s")
        logger.info(f"   Average per drug: {elapsed/len(drugs):.2f}s")
        return results
    except Exception as e:
        logger.error(f"❌ Batch LLM failed: {type(e).__name__}: {e}")
        logger.exception("Full stack trace:")
        logger.warning("⚠️ Falling back to sequential processing")
        # Fallback...
```

### 2. Implement Batched Embeddings
**File**: `src/rag/retriever.py`

Refactor `retrieve_for_multiple_drugs()` to batch embedding creation

### 3. Profile Report Parsing
**File**: `src/parsers/input_parser.py`

Add timing:
```python
def parse_report(self, report_text: str):
    start = time.time()
    
    # Time each section
    t1 = time.time()
    drugs = self.drug_extractor.extract_drugs(report_text)
    logger.info(f"Drug extraction: {(time.time()-t1)*1000:.1f}ms")
    
    t2 = time.time()
    diagnoses = self.diagnosis_extractor.extract_diagnoses(report_text)
    logger.info(f"Diagnosis extraction: {(time.time()-t2)*1000:.1f}ms")
    
    # ... rest of parsing
    
    total = (time.time() - start) * 1000
    logger.info(f"Total parsing: {total:.1f}ms")
```

---

## 📊 Monitoring & Validation

### Add Performance Tracking
```python
# src/cli/main.py - in show_performance_metrics()

# Add comparison to baseline
baseline_total = 150930  # ms
improvement = ((baseline_total - timings['total']) / baseline_total) * 100

if improvement > 0:
    self.console.print(f"  📈 Improvement: {improvement:.1f}% faster than baseline")
```

### Track Key Metrics
1. **Total time per report**
2. **Time per drug**
3. **Cache hit rate** (when implemented)
4. **LLM token usage**
5. **Error rate** (batch vs sequential)

---

## ⚠️ Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Batch LLM quality degradation | High | A/B test, compare accuracy |
| OpenAI rate limits | Medium | Implement retry with backoff |
| Embedding cache invalidation | Low | Clear cache on SUT updates |
| Token limit in batch calls | Medium | Split into sub-batches |

---

## 🎓 Key Learnings

### Why Current System is Slow:

1. **N sequential LLM calls** = Most expensive operation
   - Each call: 20-30s due to network + processing
   - Solution: Batch or parallelize

2. **N sequential embedding calls** = Unnecessary API overhead
   - Each call: ~400ms
   - Solution: Use batch API

3. **Synchronous I/O** = Waiting for responses
   - Solution: Use async/await

### Performance Best Practices:

1. ✅ **Batch API calls** whenever possible
2. ✅ **Cache** repeated computations
3. ✅ **Parallelize** independent operations
4. ✅ **Profile first**, optimize later
5. ✅ **Measure everything** with detailed timing

---

## 📚 Resources

- [OpenAI Batch API](https://platform.openai.com/docs/guides/batch)
- [Async Python Guide](https://realpython.com/async-io-python/)
- [FAISS GPU](https://github.com/facebookresearch/faiss/wiki/Faiss-on-the-GPU)
- [Sentence Transformers](https://www.sbert.net/)

---

## ✅ Success Criteria

**Phase 1 Complete When**:
- [ ] Total time < 60s for 5 drugs
- [ ] Eligibility check < 30s total
- [ ] RAG retrieval < 1s total

**Phase 2 Complete When**:
- [ ] Total time < 20s for 5 drugs
- [ ] Eligibility check < 15s total
- [ ] Caching implemented with >50% hit rate

**Production Ready When**:
- [ ] Total time < 10s for 5 drugs
- [ ] 95% accuracy maintained
- [ ] Error handling robust
- [ ] Monitoring in place
