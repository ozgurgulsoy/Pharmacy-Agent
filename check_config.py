#!/usr/bin/env python3
"""
Quick configuration checker for Pharmacy Agent.
Shows current settings and performance configuration.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.config import settings
    
    print("\n" + "="*70)
    print(" 🔧 PHARMACY AGENT - CURRENT CONFIGURATION")
    print("="*70)
    
    print("\n📌 API CONFIGURATION")
    print("-" * 70)
    api_key = settings.OPENAI_API_KEY
    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"  OpenAI API Key:        {masked_key} ✓")
    else:
        print(f"  OpenAI API Key:        ❌ NOT SET")
    
    print("\n🤖 MODEL CONFIGURATION")
    print("-" * 70)
    print(f"  LLM Model:             {settings.LLM_MODEL}")
    print(f"  Embedding Model:       {settings.EMBEDDING_MODEL}")
    print(f"  Max Tokens:            {settings.MAX_TOKENS}")
    print(f"  Temperature:           {settings.TEMPERATURE}")
    
    print("\n📊 RETRIEVAL SETTINGS")
    print("-" * 70)
    print(f"  Chunking Strategy:     {settings.CHUNKING_STRATEGY}")
    print(f"  Chunk Size:            {settings.CHUNK_SIZE} chars")
    print(f"  Chunk Overlap:         {settings.CHUNK_OVERLAP} chars")
    print(f"  Top K Chunks:          {settings.TOP_K_CHUNKS}")
    
    print("\n⚡ PERFORMANCE FEATURES")
    print("-" * 70)
    print(f"  Streaming:             {'✓ Enabled' if settings.ENABLE_STREAMING else '✗ Disabled'}")
    print(f"  Parallel Embeddings:   {'✓ Enabled' if settings.PARALLEL_EMBEDDINGS else '✗ Disabled'}")
    print(f"  Cache Embeddings:      {'✓ Enabled' if settings.CACHE_EMBEDDINGS else '✗ Disabled'}")
    
    print("\n📁 FILE PATHS")
    print("-" * 70)
    print(f"  FAISS Index:           {settings.FAISS_INDEX_PATH}")
    faiss_exists = os.path.exists(settings.FAISS_INDEX_PATH)
    print(f"                         {'✓ Exists' if faiss_exists else '❌ NOT FOUND'}")
    
    print(f"  FAISS Metadata:        {settings.FAISS_METADATA_PATH}")
    metadata_exists = os.path.exists(settings.FAISS_METADATA_PATH)
    print(f"                         {'✓ Exists' if metadata_exists else '❌ NOT FOUND'}")
    
    print(f"  SUT PDF:               {settings.SUT_PDF_PATH}")
    pdf_exists = os.path.exists(settings.SUT_PDF_PATH)
    print(f"                         {'✓ Exists' if pdf_exists else '❌ NOT FOUND'}")
    
    print("\n🌍 LANGUAGE & OUTPUT")
    print("-" * 70)
    print(f"  Output Language:       {settings.OUTPUT_LANGUAGE}")
    
    # Performance assessment
    print("\n📈 PERFORMANCE ASSESSMENT")
    print("-" * 70)
    
    # Model assessment
    if settings.LLM_MODEL in ["gpt-4o-mini", "gpt-3.5-turbo-0125"]:
        print("  ✅ Using fast model")
    elif "gpt-4" in settings.LLM_MODEL:
        print("  ⚠️  Using slow model (gpt-4) - consider gpt-4o-mini")
    else:
        print(f"  ℹ️  Using: {settings.LLM_MODEL}")
    
    # Chunk assessment
    if settings.TOP_K_CHUNKS <= 3:
        print("  ⚡ Fast retrieval (3 chunks) - may miss context")
    elif settings.TOP_K_CHUNKS <= 5:
        print("  ✅ Balanced retrieval (5 chunks)")
    else:
        print("  🎯 Thorough retrieval (10+ chunks) - slower but comprehensive")
    
    # Cache assessment
    if settings.CACHE_EMBEDDINGS:
        cache_dir = Path("data/embedding_cache")
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.pkl"))
            print(f"  ✅ Embedding cache active ({len(cache_files)} cached queries)")
        else:
            print("  ⚠️  Embedding cache enabled but no cache files yet")
    else:
        print("  ❌ Embedding cache disabled - queries will be slower")
    
    # Overall recommendation
    print("\n💡 RECOMMENDATION")
    print("-" * 70)
    
    if not api_key:
        print("  ❌ Set OPENAI_API_KEY in .env file")
    elif not faiss_exists:
        print("  ❌ Run: python scripts/setup_faiss.py")
    elif settings.LLM_MODEL == "gpt-4o-mini" and settings.TOP_K_CHUNKS == 5:
        print("  ✅ Configuration is optimal!")
    elif "gpt-4" in settings.LLM_MODEL and "mini" not in settings.LLM_MODEL:
        print("  ⚠️  Consider using gpt-4o-mini for faster responses")
    else:
        print("  ✅ Configuration looks good!")
    
    print("\n🚀 NEXT STEPS")
    print("-" * 70)
    print("  1. Test performance:   python benchmark_performance.py")
    print("  2. Start server:       python run.py")
    print("  3. Read guide:         cat PERFORMANCE_GUIDE.md")
    print("="*70)
    print()
    
except ImportError as e:
    print(f"\n❌ Error importing settings: {e}")
    print("\nMake sure you're in the project root directory.")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
