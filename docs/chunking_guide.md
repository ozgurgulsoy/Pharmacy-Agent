# Chunking Strategy Guide

## Overview

Choosing the right chunking strategy is crucial for RAG (Retrieval-Augmented Generation) performance. This guide explains the different strategies implemented in the Pharmacy Agent and how to optimize them.

## The Chunking Tradeoff

### Small Chunks (256-512 tokens)
**✅ Pros:**
- High precision - embeddings represent specific concepts
- Better for exact fact retrieval
- Faster similarity searches

**❌ Cons:**
- Context fragmentation - might lose surrounding information
- "This is why it's ineffective" without knowing what "it" refers to
- May require retrieving more chunks to get complete context

### Large Chunks (512-1024+ tokens)
**✅ Pros:**
- High context - complete paragraphs/sections
- Better for thematic/summary questions
- Less fragmentation

**❌ Cons:**
- Lower precision (retrieval noise)
- Embedding becomes "average" of multiple ideas
- Specific queries may not match well
- Longer chunks cost more tokens in LLM context

## Implemented Strategies

### 1. Semantic Chunking ✨ RECOMMENDED

**What it does:** Preserves paragraph boundaries and logical structure

**Best for:**
- Documents with clear paragraph structure
- Maintaining coherent ideas
- Medical/regulatory documents (like SUT)

**Configuration:**
```bash
CHUNKING_STRATEGY=semantic
CHUNK_SIZE=2048        # Max size before splitting
MIN_CHUNK_SIZE=512     # Minimum viable chunk
MAX_CHUNK_SIZE=4096    # Hard limit
CHUNK_OVERLAP=256      # ~12.5% overlap
PRESERVE_PARAGRAPHS=true
```

**How it works:**
1. Splits by paragraphs (double newline `\n\n`)
2. Combines paragraphs until MAX_CHUNK_SIZE
3. For oversized paragraphs, splits by sentences
4. Maintains overlap between chunks

### 2. Fixed Chunking

**What it does:** Traditional character-based splitting with overlap

**Best for:**
- Consistent chunk sizes
- Documents without clear structure
- Simple baseline testing

**Configuration:**
```bash
CHUNKING_STRATEGY=fixed
CHUNK_SIZE=2048
CHUNK_OVERLAP=256
```

**How it works:**
1. Splits text every CHUNK_SIZE characters
2. Overlaps CHUNK_OVERLAP characters
3. No respect for paragraph/sentence boundaries

### 3. Hybrid Chunking (Default)

**What it does:** Combines section headers with size constraints

**Best for:**
- Structured documents with section headers (like SUT)
- Regulatory documents with numbered sections
- Documents with clear hierarchical structure

**Configuration:**
```bash
CHUNKING_STRATEGY=hybrid
CHUNK_SIZE=2048
CHUNK_OVERLAP=256
```

**How it works:**
1. Detects section headers (e.g., "4.2.28", "4.2.28.A")
2. Chunks at section boundaries
3. If section too large, splits with overlap
4. Preserves section metadata

## Choosing Chunk Size

### Our Model Limits

**Embedding Model:** `text-embedding-3-small`
- Max tokens: **8,191 tokens**
- We have plenty of room!

**LLM Context Window:** `gpt-4o-mini`
- Max tokens: **128,000 tokens**
- Again, plenty of room!

### Recommended Starting Points

| Document Type | Strategy | Size (chars) | Size (tokens) | Overlap |
|--------------|----------|--------------|---------------|---------|
| SUT (Regulatory) | `hybrid` | 2048 | ~512 | 256 (12.5%) |
| Medical Records | `semantic` | 2048 | ~512 | 256 (12.5%) |
| General Text | `semantic` | 1024 | ~256 | 128 (12.5%) |
| Code | `semantic` | 4096 | ~1024 | 512 (12.5%) |

### Chunk Overlap: Your Safety Net

**Purpose:** Prevents context fragmentation at chunk boundaries

**Rule of thumb:** 10-20% of chunk size

**Example with 2048 char chunks:**
```
Chunk 1: [0-2048]
Chunk 2: [1792-3840]  ← 256 chars overlap with Chunk 1
Chunk 3: [3584-5632]  ← 256 chars overlap with Chunk 2
```

If a critical sentence is at position 2000, it appears in both Chunk 1 and Chunk 2!

## Testing & Optimization

### Step 1: Create Your Golden Question Set

Create 10-20 test questions where you **know** the answer is in your document:

```python
GOLDEN_QUESTIONS = [
    EvaluationQuestion(
        question="Ezetimib için hangi şartlar gerekli?",
        expected_section="4.2.28",
        expected_keywords=["ezetimib", "kolesterol", "LDL"],
        description="Tests specific drug condition retrieval"
    ),
    # Add more...
]
```

### Step 2: Run Evaluation

**Test single strategy:**
```bash
python scripts/evaluate_chunking.py \
    --strategy semantic \
    --chunk-size 2048 \
    --overlap 256
```

**Run comprehensive test:**
```bash
python scripts/evaluate_chunking.py --run-all-tests
```

This tests 9 different configurations:
- 3 strategies (semantic, fixed, hybrid)
- 3 chunk sizes (1024, 2048, 4096)
- Proportional overlaps (12.5%)

### Step 3: Analyze Results

The script outputs:
- **Section Match Rate:** Did we retrieve the right section?
- **Keyword Coverage:** What % of expected keywords appeared?
- **Average Similarity:** How confident was the retrieval?
- **Chunk Statistics:** Sizes, counts, etc.

### Step 4: Iterate

**Symptoms → Solutions:**

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| "I don't know" answers | Chunks too large/noisy | ↓ Decrease chunk size |
| Partial/confused answers | Chunks too small | ↑ Increase chunk size or overlap |
| Missing context | No overlap | ↑ Increase overlap to 15-20% |
| Wrong section retrieved | Embedding noise | Try semantic chunking |
| Slow retrieval | Too many chunks | ↑ Increase chunk size |

## Configuration Examples

### Conservative (High Context)
```bash
CHUNKING_STRATEGY=semantic
CHUNK_SIZE=3072          # ~768 tokens
CHUNK_OVERLAP=512        # ~16.7% overlap
MIN_CHUNK_SIZE=1024
MAX_CHUNK_SIZE=6144
TOP_K_CHUNKS=3
```

### Balanced (Recommended)
```bash
CHUNKING_STRATEGY=semantic
CHUNK_SIZE=2048          # ~512 tokens
CHUNK_OVERLAP=256        # ~12.5% overlap
MIN_CHUNK_SIZE=512
MAX_CHUNK_SIZE=4096
TOP_K_CHUNKS=5
```

### Aggressive (High Precision)
```bash
CHUNKING_STRATEGY=semantic
CHUNK_SIZE=1024          # ~256 tokens
CHUNK_OVERLAP=128        # ~12.5% overlap
MIN_CHUNK_SIZE=256
MAX_CHUNK_SIZE=2048
TOP_K_CHUNKS=7
```

## Environment Variables

Add to your `.env` file:

```bash
# Chunking Configuration
CHUNKING_STRATEGY=semantic       # semantic, fixed, or hybrid
CHUNK_SIZE=2048                  # characters
CHUNK_OVERLAP=256                # characters
MIN_CHUNK_SIZE=512               # minimum viable chunk
MAX_CHUNK_SIZE=4096              # maximum chunk size
PRESERVE_PARAGRAPHS=true         # preserve paragraph boundaries
TOP_K_CHUNKS=5                   # number of chunks to retrieve

# Embedding Configuration
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_PROVIDER=openai
EMBEDDING_DIMENSION=1536
```

## Advanced: Custom Chunking

To implement custom chunking logic:

1. Add new method to `SUTDocumentChunker`:

```python
def _custom_chunking(self, text: str) -> List[Chunk]:
    """Your custom chunking logic."""
    # Your implementation
    pass
```

2. Update `chunk_document()` method:

```python
elif self.strategy == "custom":
    chunks = self._custom_chunking(cleaned_text)
```

3. Add to settings:

```python
CHUNKING_STRATEGY: str = os.getenv("CHUNKING_STRATEGY", "custom")
```

## Monitoring & Metrics

Track these metrics over time:

1. **Retrieval Quality**
   - Section match rate
   - Keyword coverage
   - User satisfaction scores

2. **Performance**
   - Average chunk size
   - Number of chunks
   - Retrieval latency

3. **Cost**
   - Embedding API calls
   - LLM context token usage
   - Storage size

## Resources

- [Video: Choosing the right Chunk Size for RAG](https://www.youtube.com/watch?v=...)
- [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)

## FAQ

**Q: What's the "right" chunk size?**  
A: There's no universal answer. Test with your specific data and questions. Start with 2048 chars (~512 tokens) and iterate.

**Q: Should I always use semantic chunking?**  
A: For structured documents like PDFs with paragraphs, yes. For unstructured text, fixed might be simpler.

**Q: How much overlap is too much?**  
A: More than 25% is usually wasteful. Stick to 10-20%.

**Q: Can chunks be different sizes?**  
A: Yes! Semantic and hybrid strategies produce variable-sized chunks, which is often better than forcing uniform sizes.

**Q: Should I rebuild the index after changing chunk size?**  
A: Yes! Chunk size changes require re-chunking, re-embedding, and rebuilding the FAISS index.

---

**Next Steps:**
1. Review your current chunking configuration
2. Create your golden question set
3. Run `evaluate_chunking.py --run-all-tests`
4. Analyze results and adjust parameters
5. Rebuild FAISS index with optimal settings
