#!/bin/bash
# Quick performance test script

echo "🔍 Checking configuration..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ No .env file found!"
    echo "📝 Creating .env from recommended template..."
    cp .env.recommended .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your OPENAI_API_KEY"
    echo ""
    exit 1
fi

# Check current model configuration
echo "📋 Current Configuration:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
grep "LLM_MODEL=" .env || echo "LLM_MODEL not set (will use default: gpt-5-mini ❌)"
grep "EMBEDDING_PROVIDER=" .env || echo "EMBEDDING_PROVIDER not set (will use default: ollama)"
grep "EMBEDDING_MODEL=" .env || echo "EMBEDDING_MODEL not set"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Recommend changes if needed
if grep -q "gpt-5-nano" .env 2>/dev/null || ! grep -q "LLM_MODEL=" .env 2>/dev/null; then
    echo "⚠️  WARNING: Invalid LLM model detected!"
    echo ""
    echo "Recommended changes to .env:"
    echo "  LLM_MODEL=gpt-4o-mini"
    echo "  EMBEDDING_PROVIDER=openai"
    echo "  EMBEDDING_MODEL=text-embedding-3-small"
    echo "  EMBEDDING_DIMENSION=1536"
    echo ""
    echo "Expected improvement: 82s → 25-35s (2-3× faster!)"
    echo ""
fi

# Check if API key is set
if grep -q "sk-your-actual-api-key-here" .env 2>/dev/null || ! grep -q "OPENAI_API_KEY=sk-" .env 2>/dev/null; then
    echo "❌ OPENAI_API_KEY not configured in .env"
    echo "Please add your actual OpenAI API key"
    echo ""
    exit 1
fi

echo "✅ Configuration looks good!"
echo ""
echo "🚀 Starting performance test..."
echo ""

# Activate venv if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the CLI
python3 -m src.cli.main

echo ""
echo "✅ Test complete!"
echo ""
echo "💡 Tips:"
echo "  - Look for 'model=gpt-4o-mini' in logs"
echo "  - Check if embeddings show 'batched' or 'sequential'"
echo "  - Total time should be < 40s for 5 drugs"
