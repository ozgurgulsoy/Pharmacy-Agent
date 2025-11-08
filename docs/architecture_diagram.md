# Multi-Document RAG Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PATIENT REPORT                               │
│  "Tanı: EK-4/D Listesinde Yer Almayan Hastalıklar"                 │
│  "G62.9 POLİNÖROPATİ"                                               │
│  "İlaç: Gabapentin 300mg - 3x1"                                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INPUT PARSER                                      │
│  • Extracts: Patient info, Diagnosis, Drugs, Doctor                │
│  • Normalizes: ICD codes, Drug names, Dates                         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   EK-4 DETECTOR                                      │
│  Pattern: EK-4/[A-Z]                                                 │
│  Result: Found EK-4/D → 20201207-1230-sut-ek-4-d-38dbc.pdf         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
            ┌────────────┴─────────────┐
            │                          │
            ▼                          ▼
┌───────────────────────┐   ┌──────────────────────┐
│   Query SUT           │   │   Query EK-4/D       │
│   • top_k = 5         │   │   • top_k = 5        │
│   • doc_type = "SUT"  │   │   • doc_type="EK-4/D"│
└──────────┬────────────┘   └──────────┬───────────┘
           │                           │
           └───────────┬───────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 FAISS VECTOR STORE                                   │
│  Index: 505 chunks total                                            │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐     │
│  │  SUT         │  EK-4/D      │  EK-4/E      │  EK-4/F      │     │
│  │  ~480 chunks │  ~6 chunks   │  ~6 chunks   │  ~6 chunks   │     │
│  │  doc_type:   │  doc_type:   │  doc_type:   │  doc_type:   │     │
│  │  "SUT"       │  "EK-4/D"    │  "EK-4/E"    │  "EK-4/F"    │     │
│  └──────────────┴──────────────┴──────────────┴──────────────┘     │
│                                                                      │
│  Embedding: Qwen3-8B (4096 dim)                                     │
│  Search: Cosine similarity + Keyword boosting                       │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 HYBRID RERANKER                                      │
│  Combines:                                                           │
│  • Keyword matches (drug index) → 5.0x boost                        │
│  • Partial matches (drug in text) → 2.0x boost                      │
│  • Semantic matches → 1.0x base                                     │
│                                                                      │
│  Result: Top 10 chunks (5 SUT + 5 EK-4/D)                          │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              ELIGIBILITY CHECKER (LLM)                               │
│  Model: Google Gemini 2.0 Flash                                     │
│  Context:                                                            │
│  • Patient: Age, TC, Name                                           │
│  • Diagnosis: ICD-10, Description                                   │
│  • Drug: Name, Form, Dosage                                         │
│  • SUT Chunks: 5 relevant sections                                  │
│  • EK-4 Chunks: 5 relevant sections                                 │
│                                                                      │
│  Analysis: Checks BOTH SUT and EK-4/D conditions                    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ELIGIBILITY RESULT                                │
│  {                                                                   │
│    "drug_name": "Gabapentin",                                       │
│    "status": "ELIGIBLE",                                            │
│    "confidence": 0.95,                                              │
│    "sut_reference": "SUT + EK-4/D",                                 │
│    "conditions": [                                                  │
│      {"description": "EK-4/D listesinde", "is_met": true},         │
│      {"description": "Polinöropati tanısı", "is_met": true}        │
│    ],                                                               │
│    "explanation": "Gabapentin EK-4/D kapsamında uygun"             │
│  }                                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. EK-4 Detector
- **Input**: Raw report text
- **Output**: List of EK4Reference objects
- **Logic**: Regex pattern matching for `EK-4/[D|E|F|G]`
- **Performance**: <1ms

### 2. Multi-Document Query Strategy

#### Without EK-4 (Default):
```
Query → SUT Index → Top-K → Rerank → Result
Time: ~100-200ms
```

#### With EK-4/D:
```
Query → SUT Index → Top-K SUT chunks
     → EK-4/D Index → Top-K EK-4 chunks
     → Combine → Rerank → Result
Time: ~120-240ms (+20-40ms)
```

### 3. Hybrid Ranking

```
Score = Keyword Match? → 5.0x boost
      + Partial Match? → 2.0x boost
      + Semantic Score → 1.0x base
```

### 4. FAISS Index Structure

```json
{
  "chunk_id": "sut_chunk_0001",
  "content": "4.2.28 Lipid düşürücü ilaçlar...",
  "metadata": {
    "doc_type": "SUT",
    "doc_source": "SUT.pdf",
    "section": "4.2.28",
    "etkin_madde": ["ezetimib", "statin"],
    "drug_related": true,
    "has_conditions": true
  },
  "embedding": [0.123, 0.456, ...] // 4096-dim
}
```

## Data Flow Summary

```
Report → Parse → Detect EK-4 → Query Multi-Docs → Rerank → LLM → Result
  1ms     5ms       1ms           100-200ms        5ms    500ms   ~1s
```

## Key Optimizations

1. **Lazy Loading**: Only query EK-4 when detected
2. **Single Index**: Combined FAISS for fast search
3. **Keyword Boosting**: Exact matches prioritized
4. **Embedding Cache**: Avoid recomputation
5. **Batch Processing**: Multiple drugs in one LLM call

## Scalability

- **Current**: 5 documents, 505 chunks
- **Limit**: ~10K chunks before considering separate indices
- **Memory**: ~20MB for embeddings + 5MB for FAISS
- **Query Time**: O(log n) for FAISS search
