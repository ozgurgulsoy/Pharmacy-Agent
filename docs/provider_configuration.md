# Provider Configuration - Clarification

## Current Setup

Your Pharmacy Agent is configured to use:

### LLM (Language Model)
- **Provider**: OpenRouter
- **Model**: `google/gemini-2.0-flash-001` (Google Gemini 2.0 Flash)
- **Purpose**: Eligibility checking and decision-making

### Embeddings
- **Provider**: OpenRouter
- **Sub-provider**: Nebius
- **Model**: `qwen/qwen3-embedding-8b` (Qwen3 Embedding 8B)
- **Dimension**: 4096
- **Purpose**: Vector representations for RAG retrieval

## What Was Fixed

### Issue
The code didn't properly recognize that you can use **Nebius embeddings through OpenRouter**. The validation logic only checked for "openrouter" or "openai" as embedding providers.

### Solution
Updated `app/config/settings.py` to:

1. **Added `OPENROUTER_EMBEDDING_PROVIDER`** variable
   - Captures which provider is used through OpenRouter (e.g., "nebius")
   
2. **Updated validation logic**
   - Now recognizes "nebius" as a valid provider through OpenRouter
   - Validates that OPENROUTER_API_KEY exists when using Nebius

3. **Updated comments**
   - Clarified that EMBEDDING_PROVIDER can be "openrouter", "openai", or "nebius"
   - Noted that Nebius is accessed through OpenRouter

## Configuration in `.env`

```bash
# LLM Configuration
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here

# Embedding Configuration
EMBEDDING_PROVIDER=openrouter
OPENROUTER_EMBEDDING_PROVIDER=nebius  # Nebius models via OpenRouter
EMBEDDING_MODEL=qwen/qwen3-embedding-8b
EMBEDDING_DIMENSION=4096
```

## How It Works

```
┌─────────────────────────────────────────────┐
│          Your Application                    │
└────────────┬────────────────────────────────┘
             │
             ├─── LLM Requests ────────────────────┐
             │                                     │
             │                                     ▼
             │                         ┌───────────────────────┐
             │                         │   OpenRouter          │
             │                         │   ↓                   │
             │                         │   Google Gemini 2.0   │
             │                         └───────────────────────┘
             │
             ├─── Embedding Requests ──────────────┐
             │                                     │
             │                                     ▼
             │                         ┌───────────────────────┐
             │                         │   OpenRouter          │
             │                         │   ↓                   │
             │                         │   Nebius              │
             │                         │   ↓                   │
             │                         │   Qwen3 Embedding 8B  │
             │                         └───────────────────────┘
             │
             └─────────────────────────────────────┘
```

## Why This Setup?

### Advantages
1. **Single API Key**: Use OpenRouter for both LLM and embeddings
2. **Turkish Support**: Qwen3 embeddings support Turkish language well
3. **Cost-Effective**: Nebius provides competitive pricing
4. **High Quality**: Gemini 2.0 Flash for reasoning, Qwen3 for embeddings
5. **Flexibility**: Easy to switch providers through OpenRouter

### Model Specifications

| Component | Provider | Model | Dimension | Purpose |
|-----------|----------|-------|-----------|---------|
| LLM | OpenRouter → Google | Gemini 2.0 Flash | - | Decision Making |
| Embeddings | OpenRouter → Nebius | Qwen3-8B | 4096 | Vector Search |

## Validation

The config now properly validates:

1. ✅ OPENROUTER_API_KEY required when using OpenRouter
2. ✅ Recognizes Nebius as valid provider through OpenRouter
3. ✅ Supports both direct and sub-provider configurations
4. ✅ No conflicts between LLM and embedding providers

## Testing

```bash
# Verify settings load correctly
python3 -c "from app.config.settings import *; print(f'Embedding via {OPENROUTER_EMBEDDING_PROVIDER}')"
# Output: Embedding via nebius
```

## No Action Required

✅ The fix has been applied to `app/config/settings.py`  
✅ Your existing `.env` configuration is now properly recognized  
✅ No changes needed to your environment variables  
✅ The system will work correctly with Nebius embeddings via OpenRouter  

---

**Status**: ✅ Fixed  
**Impact**: Configuration validation now properly supports Nebius embeddings through OpenRouter  
**Backward Compatible**: Yes, existing configurations still work  
