# Quick Start: Optimizing Your Chunking Strategy

## TL;DR

Run this to find the best chunking configuration for your SUT document:

```bash
python scripts/evaluate_chunking.py --run-all-tests
```

## What You Need to Know

### 1. Current Configuration (Improved Defaults)

Your system now uses **semantic chunking** with these optimized defaults:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Strategy | `semantic` | Preserves paragraph boundaries |
| Chunk Size | 2048 chars (~512 tokens) | Balanced context/precision |
| Overlap | 256 chars (12.5%) | Prevents fragmentation |
| Min Chunk | 512 chars | Avoids tiny chunks |
| Max Chunk | 4096 chars | Hard limit for large paragraphs |

### 2. Why These Changes Matter

**Before (Old Settings):**
```
CHUNK_SIZE=1000 chars (~200 tokens)
CHUNK_OVERLAP=200 chars (20%)
Strategy: Hybrid only
```
- ⚠️ Small chunks = context fragmentation
- ⚠️ High overlap = wasted storage
- ⚠️ No flexibility to test other strategies

**After (New Settings):**
```
CHUNK_SIZE=2048 chars (~512 tokens)
CHUNK_OVERLAP=256 chars (12.5%)
Strategy: Semantic/Fixed/Hybrid (configurable)
```
- ✅ Larger chunks = better context
- ✅ Efficient overlap
- ✅ Multiple strategies to test
- ✅ Evaluation framework included

### 3. Quick Test

Test the new configuration:

```bash
# 1. Rebuild FAISS index with new chunking
python scripts/setup_faiss.py

# 2. Test with a sample query
python -m src.cli.main analyze data/patient_report.txt
```

## Detailed Evaluation Process

### Step 1: Prepare Golden Questions

Edit `scripts/evaluate_chunking.py` and customize the test questions:

```python
GOLDEN_QUESTIONS = [
    EvaluationQuestion(
        question="Your specific question about SUT?",
        expected_section="4.2.28",  # Expected section number
        expected_keywords=["keyword1", "keyword2"],
        description="What this tests"
    ),
    # Add 10-20 questions total
]
```

### Step 2: Run Comprehensive Evaluation

This tests 9 different configurations (3 strategies × 3 sizes):

```bash
cd "/Users/ozguromergulsoy/Desktop/Pharmacy Agent"
python scripts/evaluate_chunking.py --run-all-tests
```

**What it does:**
1. Tests semantic, fixed, and hybrid strategies
2. Tests chunk sizes: 1024, 2048, 4096 characters
3. Measures: section match rate, keyword coverage, similarity
4. Saves results to `data/chunking_evaluation_YYYYMMDD_HHMMSS.json`
5. Prints summary with best configuration

**Expected output:**
```
==========================================
EVALUATION SUMMARY
==========================================
Strategy     Size     Overlap  Chunks   Section    Keywords   Similarity
--------------------------------------------------------------------------------
semantic     1024     12.5%    450      85.0%      78.5%      0.842
semantic     2048     12.5%    225      90.0%      85.2%      0.856
semantic     4096     12.5%    112      75.0%      82.1%      0.834
...

🏆 BEST CONFIGURATION:
   Strategy: semantic
   Chunk Size: 2048 chars (~512 tokens)
   Section Match Rate: 90.0%
   Keyword Coverage: 85.2%
==========================================
```

### Step 3: Test Single Configuration

If you want to test a specific configuration:

```bash
# Test semantic chunking with 2048 char chunks
python scripts/evaluate_chunking.py \
    --strategy semantic \
    --chunk-size 2048 \
    --overlap 256

# Test large chunks
python scripts/evaluate_chunking.py \
    --strategy semantic \
    --chunk-size 4096 \
    --overlap 512
```

### Step 4: Apply Best Configuration

Once you find the best configuration:

**Option A: Use Environment Variables (Temporary)**
```bash
export CHUNKING_STRATEGY=semantic
export CHUNK_SIZE=2048
export CHUNK_OVERLAP=256
python scripts/setup_faiss.py
```

**Option B: Update .env File (Permanent)**
```bash
# Edit .env file
CHUNKING_STRATEGY=semantic
CHUNK_SIZE=2048
CHUNK_OVERLAP=256
MIN_CHUNK_SIZE=512
MAX_CHUNK_SIZE=4096
```

Then rebuild:
```bash
python scripts/setup_faiss.py
```

## Understanding the Results

### Key Metrics

1. **Section Match Rate (Most Important)**
   - Did we retrieve the correct SUT section?
   - Target: >80%
   - If low: chunks too noisy (try smaller size) or too fragmented (try larger)

2. **Keyword Coverage**
   - What % of expected keywords appear in retrieved chunks?
   - Target: >75%
   - If low: chunks missing context (increase size or overlap)

3. **Average Similarity**
   - How confident is the embedding match?
   - Target: >0.80
   - If low: poor semantic matching (try different strategy)

4. **Chunk Statistics**
   - Total chunks: More = finer granularity, but slower search
   - Avg size: Should be consistent for fixed, variable for semantic
   - Target: 200-300 chunks for typical SUT document

### Interpreting Issues

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Low section match + high similarity | Chunks too large, averaging multiple topics | **Decrease chunk size** |
| High section match + low keyword coverage | Chunks too small, missing context | **Increase chunk size or overlap** |
| Low similarity overall | Poor chunking strategy | Try **semantic** instead of fixed |
| Too many tiny chunks | MIN_CHUNK_SIZE too low | Increase MIN_CHUNK_SIZE |
| Chunks with incomplete sentences | Using fixed strategy | Switch to **semantic** |

## Advanced: Custom Configuration

### For Different Document Types

**Medical Records (Narrative Text):**
```bash
CHUNKING_STRATEGY=semantic
CHUNK_SIZE=1536        # Smaller, focused chunks
CHUNK_OVERLAP=192      # 12.5%
PRESERVE_PARAGRAPHS=true
```

**Legal/Regulatory (Like SUT):**
```bash
CHUNKING_STRATEGY=hybrid   # Respects section headers
CHUNK_SIZE=2048
CHUNK_OVERLAP=256
```

**Mixed Content:**
```bash
CHUNKING_STRATEGY=semantic
CHUNK_SIZE=2560
CHUNK_OVERLAP=384      # 15% - higher overlap for safety
```

### Performance Tuning

**Fast Retrieval (Fewer Chunks):**
```bash
CHUNK_SIZE=4096        # Larger chunks
MIN_CHUNK_SIZE=1024
TOP_K_CHUNKS=3         # Retrieve fewer
```

**High Precision (More Chunks):**
```bash
CHUNK_SIZE=1024        # Smaller chunks
MIN_CHUNK_SIZE=256
TOP_K_CHUNKS=7         # Retrieve more
```

## Monitoring in Production

Track these metrics over time:

```bash
# Add to your monitoring dashboard
- Average section match rate
- User query success rate
- Average retrieval time
- Number of "I don't know" responses
```

## Troubleshooting

**Q: Evaluation script fails with import errors**
```bash
# Make sure you're in the right directory
cd "/Users/ozguromergulsoy/Desktop/Pharmacy Agent"

# Make sure dependencies are installed
pip install -r requirements.txt

# Run with Python module syntax
python -m scripts.evaluate_chunking --run-all-tests
```

**Q: "No module named 'src'"**
```bash
# The script adds src to path automatically, but you can also:
export PYTHONPATH="${PYTHONPATH}:/Users/ozguromergulsoy/Desktop/Pharmacy Agent/src"
```

**Q: Out of memory during evaluation**
```bash
# Reduce the number of test questions
# Or test configurations one at a time:
python scripts/evaluate_chunking.py --strategy semantic --chunk-size 2048
```

**Q: Results show all zeros**
```bash
# Check if FAISS index was created successfully
ls -lh data/faiss_index

# Check if OpenAI API key is set
echo $OPENAI_API_KEY

# Check golden questions match your document
# Edit GOLDEN_QUESTIONS in evaluate_chunking.py
```

## Next Steps

1. ✅ Review the new default configuration
2. ✅ Customize golden questions for your SUT document
3. ✅ Run comprehensive evaluation
4. ✅ Analyze results
5. ✅ Apply best configuration
6. ✅ Rebuild FAISS index
7. ✅ Test with real queries
8. ✅ Monitor and iterate

## Resources

- **Detailed Guide:** `docs/chunking_guide.md`
- **Evaluation Script:** `scripts/evaluate_chunking.py`
- **Configuration:** `src/config/settings.py`
- **Chunker Implementation:** `src/document_processing/chunker.py`

---

**Need Help?** Check the FAQ in `docs/chunking_guide.md` or review the evaluation results JSON file for detailed insights.
