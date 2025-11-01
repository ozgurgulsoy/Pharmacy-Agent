# OpenRouter Configuration - Pharmacy Agent

## ✅ Configuration Complete

Your Pharmacy Agent is now configured to use **OpenRouter** instead of direct OpenAI API calls.

## 🎯 Current Configuration

### Model
- **Provider**: OpenRouter
- **Model**: `openai/gpt-oss-120b`
- **Speed**: Fast (3-8 seconds per call)
- **Cost**: **LOW** (paid via OpenRouter)

### API Keys
- ✅ OpenRouter API Key: Configured
- ✅ OpenAI API Key: Configured (for embeddings only)

### Performance Settings
- **MAX_BATCH_SIZE**: 10 (enables batching for up to 10 drugs)
- **Timeout**: 120 seconds (sufficient for large batched requests)
- **Retries**: 2 (better reliability)

## 📊 Expected Performance

### Before (with slow models)
- **Sequential Processing**: 86-167 seconds
- **Per Drug**: 17-33 seconds
- **Total for 5 drugs**: 86-167s

### After (with Gemini 2.0 Flash)
- **Batched Processing**: ~10-15 seconds total
- **Per Drug** (if fallback): 1-3 seconds
- **Speed Improvement**: **8-15x faster** ⚡

## 🚀 How to Use

1. **Restart your server**:
   ```bash
   # Stop current server (Ctrl+C)
   source venv/bin/activate
   python run.py
   ```

2. **Test with a medical report** - you should see:
   - `Initialized OpenRouter client with model: google/gemini-2.0-flash-exp:free`
   - `🚀 Sending LLM request (model=google/gemini-2.0-flash-exp:free, ...)`
   - Much faster response times

## 🔧 Alternative Fast Models

You can switch to other fast FREE models by updating `LLM_MODEL` in `.env`:

### Fastest Options
```env
# OpenAI model via OpenRouter (AVOID RATE LIMITS) - CURRENTLY USED
LLM_MODEL=openai/gpt-oss-120b

# Ultra-fast, latest Gemini (rate-limited)
LLM_MODEL=google/gemini-2.0-flash-exp:free

# Fast, stable, good for Turkish (rate-limited)
LLM_MODEL=google/gemini-flash-1.5:free

# Fast, good reasoning (rate-limited)
LLM_MODEL=meta-llama/llama-3.2-3b-instruct:free
```

## 📝 What Changed

### Files Modified
1. **`.env`**:
   - Added `OPENROUTER_API_KEY`
   - Changed `LLM_PROVIDER=openrouter`
   - Set `LLM_MODEL=google/gemini-2.0-flash-exp:free`
   - Set `MAX_BATCH_SIZE=10`

2. **`app/config/settings.py`**:
   - Added OpenRouter configuration variables
   - Updated validation to support OpenRouter
   - Updated default model

3. **`app/core/llm/openai_client.py`**:
   - Added OpenRouter provider support
   - Configured base URL and headers
   - Increased timeout for batch requests

## 🐛 Troubleshooting

### If you get timeout errors:
Increase timeout in `.env`:
```env
OPENROUTER_TIMEOUT=180
```

### If batched processing fails:
The system will automatically fall back to sequential processing. Check:
1. Model supports JSON output
2. Prompt isn't too large (>25k tokens)

### If you want to use paid models:
Update `.env` with paid OpenRouter models (faster, more reliable):
```env
# Paid options (better quality, faster)
LLM_MODEL=anthropic/claude-3.5-sonnet
LLM_MODEL=openai/gpt-4o
LLM_MODEL=google/gemini-pro-1.5
```

## 💡 Tips

1. **Gemini 2.0 Flash** is FREE and very fast - perfect for Turkish text
2. **Batch processing** works best with 1-10 drugs
3. **Sequential fallback** activates automatically if batching fails
4. **Monitor costs** at https://openrouter.ai/activity (free tier has limits)

## 📚 Resources

- OpenRouter Dashboard: https://openrouter.ai/
- Model List: https://openrouter.ai/models
- API Documentation: https://openrouter.ai/docs