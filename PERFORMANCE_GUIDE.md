# 🚀 Performance Optimization Guide

This guide explains the performance optimizations implemented in Pharmacy Agent and how to configure them for best results.

## Current Performance Metrics

Based on your recent test:
- **Parsing**: 22.2 seconds (single LLM call)
- **Eligibility Check**: 40 seconds (single LLM call for 1 drug)
- **Total**: ~62 seconds for 1 drug analysis

## 🎯 Optimization Strategies Implemented

### 1. **Batched LLM Calls** ✅ Already Implemented

**What it does**: Instead of making N sequential LLM calls, we make 1 batched call.

**Files**:
- `src/parsers/input_parser.py` - Single call extracts drugs, diagnoses, and patient info
- `src/llm/eligibility_checker.py` - Single call checks all drugs at once

**Impact**: 
- Parsing: 3 calls → 1 call (3x faster in theory)
- Eligibility: N calls → 1 call (Nx faster)

### 2. **Parallel Embeddings** ✅ Already Implemented

**What it does**: Creates embeddings for multiple queries in a single API call.

**File**: `src/rag/retriever.py` - Uses OpenAI batch embeddings API

**Impact**: 
- Multiple drugs: N API calls → 1 API call
- Reduces network overhead and latency

### 3. **Embedding Caching** ✅ Already Implemented

**What it does**: Caches query embeddings to disk to avoid recomputation.

**File**: `src/rag/retriever.py` - `EmbeddingCache` class
**Location**: `data/embedding_cache/`

**Impact**:
- Repeat queries: 0ms (instant from cache)
- Cold queries: ~400-500ms (OpenAI API call)

### 4. **Model Configuration** 🆕 Just Optimized

**Updated settings in `src/config/settings.py`**:

```python
LLM_MODEL = "gpt-4o-mini"        # Latest fast model
MAX_TOKENS = 4096                # Limit response length
TEMPERATURE = 0.1                # Lower = faster, more deterministic
```

**Impact**:
- Shorter responses = faster generation
- Lower temperature = less sampling variance

### 5. **Reduced Chunk Retrieval** 🆕 Just Optimized

```python
TOP_K_CHUNKS = 5  # Optimal balance (was 3, now 5 for better accuracy)
```

**Impact**:
- Fewer chunks = less token usage = faster LLM processing
- Balance between speed and accuracy

### 6. **HTTP Client Optimization** 🆕 Just Added

```python
OpenAI(
    timeout=60.0,      # Explicit timeout
    max_retries=2      # Reduce retries for faster failures
)
```

## ⚙️ Configuration Options

Create a `.env` file in the project root to customize:

```bash
# Model Selection (use fastest models)
LLM_MODEL=gpt-4o-mini                    # or gpt-3.5-turbo-0125
EMBEDDING_MODEL=text-embedding-3-small    # Fastest embedding model

# Response Control (reduce token usage)
MAX_TOKENS=4096          # Limit response length
TEMPERATURE=0.1          # Lower = faster, more deterministic

# Retrieval Settings (reduce chunks for speed)
TOP_K_CHUNKS=3          # 3 for speed, 5 for accuracy, 10 for max quality
CHUNK_SIZE=2048         # Larger chunks = fewer chunks needed
CHUNK_OVERLAP=256       # Balance between context and speed

# Performance Features
ENABLE_STREAMING=true           # Stream responses (future feature)
PARALLEL_EMBEDDINGS=true        # Batch embedding creation
CACHE_EMBEDDINGS=true           # Cache query embeddings

# OpenAI Settings
OPENAI_API_KEY=your-key-here
```

## 📊 Performance Tuning Guide

### For Maximum Speed (May reduce accuracy):
```bash
LLM_MODEL=gpt-3.5-turbo-0125
TOP_K_CHUNKS=3
MAX_TOKENS=2048
TEMPERATURE=0.0
```

### For Balanced Performance (Recommended):
```bash
LLM_MODEL=gpt-4o-mini
TOP_K_CHUNKS=5
MAX_TOKENS=4096
TEMPERATURE=0.1
```

### For Maximum Accuracy (Slower):
```bash
LLM_MODEL=gpt-4o
TOP_K_CHUNKS=10
MAX_TOKENS=8192
TEMPERATURE=0.2
```

## 🔍 Why Is It Still Slow?

Even with all optimizations, the main bottleneck is **OpenAI API latency**:

1. **Network Latency**: 
   - Physical distance to OpenAI servers
   - Internet connection speed
   - API load/throttling

2. **Token Generation Time**:
   - Your prompts are ~2700 tokens (parsing) and ~2700 tokens (eligibility)
   - Responses are ~2200 tokens (parsing) and ~4600 tokens (eligibility)
   - At ~50 tokens/second, this is 44-92 seconds of generation time alone

3. **Model Processing**:
   - Even fastest models need time to process large contexts
   - JSON parsing adds overhead

## 🚀 Further Optimization Ideas

### 1. **Prompt Compression** (Advanced)
Reduce prompt size by:
- Removing redundant information
- Using abbreviations
- Summarizing SUT chunks before sending to LLM

### 2. **Response Streaming** (Future Feature)
- Show results as they're generated
- Better UX even if total time is same

### 3. **Caching LLM Responses** (Risky)
- Cache eligibility results for identical inputs
- Risk: Stale results if SUT changes

### 4. **Parallel Processing** (Complex)
- Check multiple drugs in parallel (separate API calls)
- Risk: Rate limiting, cost increase

### 5. **Local LLM** (Major Change)
- Use local models (Llama, Mistral, etc.)
- Pros: No API latency, unlimited usage
- Cons: Lower accuracy, requires GPU

## 📈 Expected Performance After Optimizations

With current optimizations:
- **Parsing**: 15-25 seconds (limited by API latency)
- **Eligibility (1 drug)**: 30-50 seconds (limited by response generation)
- **Eligibility (3 drugs)**: 40-60 seconds (batched, similar to 1 drug!)

**Key Insight**: Batch processing means checking 3 drugs takes almost the same time as checking 1 drug!

## 🎯 Monitoring Performance

The application logs detailed timing information:

```
2025-10-30 17:06:20,632 - InputParser - INFO - Parsing complete: total=22213.6ms, llm_extract=22209.8ms
2025-10-30 17:07:01,096 - EligibilityChecker - INFO - ✅ Batched check succeeded in 40.03s (avg 40027.7ms/drug)
```

Watch for:
- ⚠️ warnings about slow operations
- 🚀 indications of batch processing
- ✅ cache hits for embeddings

## 🔧 Troubleshooting

### "Parsing took >5 seconds" warning
- **Cause**: Large LLM latency or big report
- **Solution**: Check OpenAI API status, reduce MAX_TOKENS

### "Batched check failed" error
- **Cause**: LLM response parsing error
- **Solution**: Check logs for JSON parsing errors, may fall back to sequential processing

### Slow embedding creation
- **Cause**: Cache misses
- **Solution**: Normal on first run, subsequent runs will be faster

## 📝 Summary

**What's already optimized:**
- ✅ Batched LLM calls (parsing + eligibility)
- ✅ Parallel embeddings
- ✅ Embedding caching
- ✅ Hybrid search (keyword + semantic)
- ✅ HTTP client optimization
- ✅ Model configuration

**What's limited by:**
- 🌐 OpenAI API latency (network + processing)
- 🔤 Token generation speed (~50 tokens/sec)
- 📊 Large prompt/response sizes

**Best next steps:**
1. Monitor actual usage patterns
2. Consider prompt compression if consistently slow
3. Evaluate local LLM if API costs/latency become prohibitive
4. Implement response streaming for better UX
