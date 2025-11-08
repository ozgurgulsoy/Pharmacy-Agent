"""Analyze RAG system performance and generate reports."""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

def analyze_metadata_coverage():
    """Analyze metadata field coverage."""
    metadata_path = Path("data/faiss_metadata.json")
    
    if not metadata_path.exists():
        print("❌ FAISS metadata not found. Please run: python scripts/setup_faiss.py")
        return
    
    with open(metadata_path) as f:
        data = json.load(f)
    
    # Handle both formats: {"metadata": [...]} or [...]
    metadata = data.get("metadata", data) if isinstance(data, dict) else data
    
    if not metadata:
        print("❌ No metadata entries found")
        return
    
    print("📊 Metadata Coverage:")
    field_coverage = defaultdict(int)
    for chunk in metadata:
        for field in chunk.keys():
            field_coverage[field] += 1
    
    for field, count in sorted(field_coverage.items()):
        pct = count / len(metadata) * 100
        status = "✅" if pct == 100 else "⚠️"
        print(f"  {status} {field}: {count}/{len(metadata)} ({pct:.1f}%)")
    
    # Check for critical missing fields
    sample = metadata[0]
    required_fields = ["id", "content", "doc_type", "doc_source"]
    missing_fields = [f for f in required_fields if f not in sample]
    
    if missing_fields:
        print(f"\n❌ CRITICAL: Missing required fields: {missing_fields}")
        print(f"   Action: Run 'python scripts/setup_faiss.py' to rebuild index")
    else:
        print(f"\n✅ All required metadata fields present")

def analyze_chunk_distribution():
    """Analyze chunk size distribution."""
    metadata_path = Path("data/faiss_metadata.json")
    
    if not metadata_path.exists():
        return
    
    with open(metadata_path) as f:
        data = json.load(f)
    
    metadata = data.get("metadata", data) if isinstance(data, dict) else data
    
    if not metadata:
        return
    
    sizes = [len(c.get("content", "")) for c in metadata]
    
    print("\n📊 Chunk Size Distribution:")
    print(f"  Mean: {np.mean(sizes):.0f} chars")
    print(f"  Median: {np.median(sizes):.0f} chars")
    print(f"  Std Dev: {np.std(sizes):.0f} chars")
    print(f"  Min: {min(sizes)} chars")
    print(f"  Max: {max(sizes)} chars")
    print(f"  Target: 2048 chars (from settings)")
    
    # Analyze distribution
    in_range = sum(1 for s in sizes if 1024 <= s <= 3072)
    pct_in_range = in_range / len(sizes) * 100
    
    print(f"\n  Chunks in target range (1024-3072): {in_range}/{len(sizes)} ({pct_in_range:.1f}%)")
    
    # Quartiles
    q1 = np.percentile(sizes, 25)
    q2 = np.percentile(sizes, 50)
    q3 = np.percentile(sizes, 75)
    
    print(f"\n  Quartiles:")
    print(f"    Q1 (25%): {q1:.0f} chars")
    print(f"    Q2 (50%): {q2:.0f} chars")
    print(f"    Q3 (75%): {q3:.0f} chars")

def analyze_doc_type_distribution():
    """Analyze document type distribution."""
    metadata_path = Path("data/faiss_metadata.json")
    
    if not metadata_path.exists():
        return
    
    with open(metadata_path) as f:
        data = json.load(f)
    
    metadata = data.get("metadata", data) if isinstance(data, dict) else data
    
    if not metadata:
        return
    
    doc_type_counts = defaultdict(int)
    for chunk in metadata:
        doc_type = chunk.get("doc_type", "MISSING")
        doc_type_counts[doc_type] += 1
    
    print("\n📊 Document Type Distribution:")
    total = len(metadata)
    
    if "MISSING" in doc_type_counts:
        print(f"  ❌ MISSING doc_type: {doc_type_counts['MISSING']} chunks")
        print(f"     Action: Run 'python scripts/setup_faiss.py' to rebuild index")
    
    for doc_type, count in sorted(doc_type_counts.items()):
        pct = count / total * 100
        status = "✅" if doc_type != "MISSING" else "❌"
        print(f"  {status} {doc_type}: {count} chunks ({pct:.1f}%)")

def analyze_keyword_coverage():
    """Analyze drug keyword coverage."""
    metadata_path = Path("data/faiss_metadata.json")
    
    if not metadata_path.exists():
        return
    
    with open(metadata_path) as f:
        data = json.load(f)
    
    metadata = data.get("metadata", data) if isinstance(data, dict) else data
    
    if not metadata:
        return
    
    drug_related = sum(1 for c in metadata if c.get("drug_related", False))
    has_etkin_madde = sum(1 for c in metadata if c.get("etkin_madde", []))
    has_keywords = sum(1 for c in metadata if c.get("keywords", []))
    
    print("\n📊 Keyword Coverage:")
    print(f"  Drug-related chunks: {drug_related}/{len(metadata)} ({drug_related/len(metadata)*100:.1f}%)")
    print(f"  Chunks with etkin_madde: {has_etkin_madde}/{len(metadata)} ({has_etkin_madde/len(metadata)*100:.1f}%)")
    print(f"  Chunks with keywords: {has_keywords}/{len(metadata)} ({has_keywords/len(metadata)*100:.1f}%)")
    
    # Sample top drugs
    drug_counts = defaultdict(int)
    for chunk in metadata:
        for drug in chunk.get("etkin_madde", []):
            drug_counts[drug] += 1
    
    if drug_counts:
        print(f"\n  Top 10 Indexed Drugs:")
        for drug, count in sorted(drug_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {drug}: {count} chunks")

def analyze_section_coverage():
    """Analyze section distribution."""
    metadata_path = Path("data/faiss_metadata.json")
    
    if not metadata_path.exists():
        return
    
    with open(metadata_path) as f:
        data = json.load(f)
    
    metadata = data.get("metadata", data) if isinstance(data, dict) else data
    
    if not metadata:
        return
    
    section_counts = defaultdict(int)
    for chunk in metadata:
        section = chunk.get("section", "NO_SECTION")
        if section:
            # Get major section (e.g., "4.2" from "4.2.28")
            major_section = ".".join(section.split(".")[:2]) if "." in section else section
            section_counts[major_section] += 1
    
    print("\n📊 Section Coverage (Top 10):")
    for section, count in sorted(section_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {section}: {count} chunks")

def main():
    """Run all analyses."""
    print("🔍 RAG System Performance Analysis")
    print("=" * 60)
    
    analyze_metadata_coverage()
    analyze_chunk_distribution()
    analyze_doc_type_distribution()
    analyze_keyword_coverage()
    analyze_section_coverage()
    
    print("\n" + "=" * 60)
    print("✅ Analysis complete!")
    print("\nNext Steps:")
    print("  1. If metadata is missing doc_type/doc_source:")
    print("     → Run: python scripts/setup_faiss.py")
    print("  2. Create golden evaluation dataset:")
    print("     → See docs/RAG_ACCURACY_ANALYSIS.md (Priority 1)")
    print("  3. Run accuracy tests:")
    print("     → pytest tests/test_rag_system.py")

if __name__ == "__main__":
    main()
