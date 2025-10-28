# 🚀 Immediate Performance Fixes

## TL;DR - Do These 3 Things NOW

### 1️⃣ Add Debug Logging to Find Why Batch is Failing (2 minutes)
### 2️⃣ Batch Embeddings API Calls (10 minutes)  
### 3️⃣ Profile Report Parsing (5 minutes)

**Expected Result**: 150s → 50-60s (3× faster)

---

## Fix #1: Debug Batch LLM (CRITICAL)

Your batch implementation exists but might be silently failing. Add logging to find out why.

**File**: `src/llm/eligibility_checker.py`

**Add this at line ~108** (in `check_multiple_drugs` method):

```python
def check_multiple_drugs(self, drugs, diagnoses, patient, doctor, sut_chunks_per_drug, explanations=None):
    """Check multiple drugs for eligibility."""
    if not drugs:
        return []
    
    primary_diagnosis = diagnoses[0] if diagnoses else Diagnosis(
        icd10_code="UNKNOWN",
        tanim="Tanı belirtilmemiş"
    )

    # **ADD THIS LOGGING** 👇
    import time
    batch_start = time.time()
    self.logger.info(f"🔍 Starting eligibility check for {len(drugs)} drugs")
    self.logger.info(f"   Using batched LLM call strategy")
    
    try:
        self.logger.info(f"🚀 Attempting batched LLM call for all {len(drugs)} drugs")
        results = self._check_all_drugs_batched(
            drugs=drugs,
            diagnosis=primary_diagnosis,
            patient=patient,
            doctor=doctor,
            sut_chunks_per_drug=sut_chunks_per_drug,
            explanations=explanations
        )
        
        batch_elapsed = time.time() - batch_start
        self.logger.info(f"✅ Batched check SUCCEEDED in {batch_elapsed:.2f}s")
        self.logger.info(f"   Average: {batch_elapsed/len(drugs):.2f}s per drug")
        self.logger.info(f"   Results received: {len(results)}")
        
        return results
        
    except Exception as e:
        self.logger.error(f"❌ Batched LLM call FAILED: {type(e).__name__}: {e}")
        self.logger.exception("Full stack trace:")
        self.logger.warning(f"⚠️  Falling back to sequential processing for {len(drugs)} drugs")
        
        # EXISTING fallback code
        results = []
        for i, drug in enumerate(drugs, 1):
            self.logger.info(f"   Processing drug {i}/{len(drugs)}: {drug.etkin_madde}")
            drug_start = time.time()
            
            sut_chunks = sut_chunks_per_drug.get(drug.etkin_madde, [])
            result = self.check_eligibility(...)
            
            drug_elapsed = time.time() - drug_start
            self.logger.info(f"   ✓ Completed in {drug_elapsed:.2f}s")
            
            results.append(result)
        
        total_elapsed = time.time() - batch_start
        self.logger.warning(f"⚠️  Sequential fallback completed in {total_elapsed:.2f}s")
        
        return results
```

**Run your test again and check logs** - you'll see exactly where it's failing!

---

## Fix #2: Batch Embedding Creation (HIGH IMPACT)

**File**: `src/rag/retriever.py`

**Replace** the `retrieve_for_multiple_drugs` method (around line 138):

```python
def retrieve_for_multiple_drugs(
    self,
    drugs: List[Drug],
    diagnosis: Optional[Diagnosis] = None,
    patient: Optional[PatientInfo] = None,
    top_k_per_drug: int = 5
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Birden fazla ilaç için chunk'ları getirir.
    OPTIMIZED: Batches embedding creation for all drugs at once.
    """
    if not drugs:
        return {}, {}
    
    import time
    
    self.logger.info(f"🔍 Retrieving chunks for {len(drugs)} drugs (batched)")
    total_start = time.time()
    
    # 🚀 OPTIMIZATION: Build ALL queries first
    queries = []
    query_metadata = []
    
    query_build_start = time.time()
    for drug in drugs:
        query_text = self._build_query_text(drug, diagnosis, patient)
        queries.append(query_text)
        query_metadata.append({"drug": drug, "query": query_text})
    query_build_time = (time.time() - query_build_start) * 1000
    
    # 🚀 OPTIMIZATION: Batch create ALL embeddings in 1 API call
    embedding_start = time.time()
    
    if self.embedding_generator.provider == "openai":
        # Batch embedding creation (much faster!)
        self.logger.info(f"   Creating embeddings for {len(queries)} queries (batched)")
        
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=queries,  # Send all queries at once!
            encoding_format="float"
        )
        embeddings = [item.embedding for item in response.data]
        
    else:
        # Ollama doesn't support batching yet
        self.logger.info(f"   Creating embeddings for {len(queries)} queries (sequential - Ollama)")
        embeddings = [
            self.embedding_generator.create_query_embedding(q) 
            for q in queries
        ]
    
    embedding_time = (time.time() - embedding_start) * 1000
    self.logger.info(f"   ✓ All embeddings created in {embedding_time:.1f}ms")
    
    # Now do vector search + hybrid reranking for each drug
    results = {}
    all_timings = []
    
    search_start = time.time()
    for drug, embedding, meta in zip(drugs, embeddings, query_metadata):
        drug_start = time.time()
        
        # Keyword search (O(1))
        keyword_start = time.time()
        keyword_results = self._keyword_search(drug.etkin_madde)
        keyword_time = (time.time() - keyword_start) * 1000
        
        # Vector search with pre-computed embedding (no API call!)
        vector_start = time.time()
        semantic_results = self.vector_store.search(
            query_embedding=embedding,
            top_k=top_k_per_drug * 2,
            filters={"drug_related": True} if self._has_metadata_filter() else None
        )
        vector_time = (time.time() - vector_start) * 1000
        
        # Hybrid rerank
        rerank_start = time.time()
        final_results = self._hybrid_rerank(
            keyword_results=keyword_results,
            semantic_results=semantic_results,
            drug_name=drug.etkin_madde,
            top_k=top_k_per_drug
        )
        rerank_time = (time.time() - rerank_start) * 1000
        
        results[drug.etkin_madde] = final_results
        
        drug_total = (time.time() - drug_start) * 1000
        all_timings.append({
            'keyword_search': keyword_time,
            'embedding_creation': 0,  # Already done in batch
            'vector_search': vector_time,
            'reranking': rerank_time,
            'total': drug_total
        })
    
    search_time = (time.time() - search_start) * 1000
    total_time = (time.time() - total_start) * 1000
    
    # Aggregate timings
    aggregate = {
        'query_building': query_build_time,
        'embedding_creation': embedding_time,  # Total for ALL drugs
        'keyword_search': sum(t['keyword_search'] for t in all_timings),
        'vector_search': sum(t['vector_search'] for t in all_timings),
        'reranking': sum(t['reranking'] for t in all_timings),
        'total': total_time,
        'avg_per_drug': total_time / len(drugs)
    }
    
    self.logger.info(f"✓ Retrieved chunks for {len(drugs)} drugs in {total_time:.1f}ms")
    self.logger.info(f"  Breakdown: Query build: {query_build_time:.1f}ms, "
                    f"Embeddings (batched): {embedding_time:.1f}ms, "
                    f"Search+Rerank: {search_time:.1f}ms")
    
    return results, aggregate
```

**Expected improvement**: 2.1s → 0.5s (4× faster for embeddings)

---

## Fix #3: Profile Report Parsing

**File**: `src/parsers/input_parser.py`

**Add timing** to the `parse_report` method:

```python
def parse_report(self, raw_text: str) -> ParsedReport:
    """Parse raw report text into structured data."""
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    total_start = time.time()
    logger.info("📋 Starting report parsing")
    
    # Time each extraction step
    t1 = time.time()
    drugs = self.drug_extractor.extract_drugs(raw_text)
    drug_time = (time.time() - t1) * 1000
    logger.info(f"   Drug extraction: {drug_time:.1f}ms ({len(drugs)} drugs)")
    
    t2 = time.time()
    diagnoses = self.diagnosis_extractor.extract_diagnoses(raw_text)
    diagnosis_time = (time.time() - t2) * 1000
    logger.info(f"   Diagnosis extraction: {diagnosis_time:.1f}ms ({len(diagnoses)} diagnoses)")
    
    t3 = time.time()
    patient = self.patient_extractor.extract_patient_info(raw_text)
    patient_time = (time.time() - t3) * 1000
    logger.info(f"   Patient extraction: {patient_time:.1f}ms")
    
    t4 = time.time()
    doctor = self.doctor_extractor.extract_doctor_info(raw_text)
    doctor_time = (time.time() - t4) * 1000
    logger.info(f"   Doctor extraction: {doctor_time:.1f}ms")
    
    t5 = time.time()
    # ... rest of parsing ...
    misc_time = (time.time() - t5) * 1000
    
    total_time = (time.time() - total_start) * 1000
    logger.info(f"✓ Total parsing: {total_time:.1f}ms")
    logger.info(f"  Breakdown - Drugs: {drug_time:.1f}ms, "
               f"Diagnosis: {diagnosis_time:.1f}ms, "
               f"Patient: {patient_time:.1f}ms, "
               f"Doctor: {doctor_time:.1f}ms, "
               f"Other: {misc_time:.1f}ms")
    
    # If total > 5000ms, warn
    if total_time > 5000:
        logger.warning(f"⚠️  Parsing took {total_time/1000:.1f}s - investigate slow extractors!")
    
    return ParsedReport(...)
```

**This will reveal** which extractor is slow (likely using LLM unnecessarily).

---

## After Applying Fixes

### Run Your Test Again

```bash
cd "/Users/ozguromergulsoy/Desktop/Pharmacy Agent"
source venv/bin/activate
python -m src.cli.main
```

### Check Logs

Look for these log lines:

```
🔍 Starting eligibility check for 5 drugs
🚀 Attempting batched LLM call for all 5 drugs
✅ Batched check SUCCEEDED in 28.3s    <-- Should see this!
   Average: 5.66s per drug             <-- Much better than 20.9s!

🔍 Retrieving chunks for 5 drugs (batched)
   Creating embeddings for 5 queries (batched)
   ✓ All embeddings created in 487ms   <-- Instead of 2100ms!
```

### Expected New Metrics

```
═══════════════════════════════════════════════════════════
⚡ PERFORMANS METRİKLERİ
═══════════════════════════════════════════════════════════
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ İşlem                   ┃       Süre ┃         Detay ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ 📋 Rapor Analizi        │   2000.0ms │  (if using LLM, investigate!) │
│ 🔍 RAG Retrieval        │    500.0ms │   100.0ms/ilaç │
│   ├─ Embedding (Batch)  │    487.0ms │  All 5 at once │
│   └─ Vector Search      │     13.0ms │   FAISS lookup │
│ 💊 Uygunluk Kontrolü    │  28000.0ms │  5600.0ms/ilaç │
│                         │            │                │
│ ⏱️  TOPLAM              │  30500.0ms │        30.50s  │
└─────────────────────────┴────────────┴────────────────┘

  Performans: ✨ Çok İyi (5× faster!)
```

---

## Troubleshooting

### If Batch Still Fails

Check the error message in logs. Common issues:

**1. Token Limit Exceeded**
```python
# In _check_all_drugs_batched, split into sub-batches
if len(drugs) > 3:
    # Process in batches of 3
    results = []
    for i in range(0, len(drugs), 3):
        batch = drugs[i:i+3]
        batch_results = self._check_drugs_batch(batch, ...)
        results.extend(batch_results)
    return results
```

**2. JSON Parsing Error**
```python
# Add better error handling
try:
    response_json = self.client.chat_completion_json(...)
    results_list = response_json.get('results', [])
    
    if not results_list:
        raise ValueError("No results in LLM response")
    
except json.JSONDecodeError as e:
    logger.error(f"LLM returned invalid JSON: {e}")
    logger.debug(f"Raw response: {response_text}")
    raise
```

**3. OpenAI Rate Limit**
```python
# Add retry with exponential backoff
import time
from openai import RateLimitError

max_retries = 3
for attempt in range(max_retries):
    try:
        response = self.client.chat_completion_json(...)
        break
    except RateLimitError:
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(f"Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
        else:
            raise
```

---

## Next Steps (After These Work)

Once you confirm these 3 fixes work:

1. **If parsing is still slow (>5s)**: Replace LLM extraction with regex
2. **If batch LLM is working**: Consider async/parallel calls for even more speed
3. **If embeddings are still slow**: Try local model (sentence-transformers)

---

## Summary

| Optimization | Current | Target | Effort |
|-------------|---------|--------|--------|
| Fix batch logging | N/A | N/A | 2 min ⭐ |
| Batch embeddings | 2.1s | 0.5s | 10 min ⭐⭐ |
| Profile parsing | 44s | TBD | 5 min ⭐ |
| **TOTAL** | **150s** | **~50s** | **17 min** |

**Do these NOW** and report back with the new timings! 🚀
