"""
Test script for EK-4 detector functionality.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.parsers.ek4_detector import EK4Detector


def test_ek4_detector():
    """Test EK-4 reference detection."""
    
    detector = EK4Detector()
    
    # Test case 1: Single EK-4/D reference
    text1 = """
    Tanı Bilgileri
    Tanı:
    20.00 – EK-4/D Listesinde Yer Almayan Hastalıklar
    G62.9 POLİNÖROPATİ, TANIMLANMAMIŞ
    Başlangıç: 06/10/2025
    Bitiş: 06/04/2026
    """
    
    print("=" * 60)
    print("TEST 1: Single EK-4/D reference")
    print("=" * 60)
    refs = detector.detect(text1)
    print(f"Found {len(refs)} reference(s):")
    for ref in refs:
        print(f"  - {ref.full_text} -> {ref.document_name}")
    assert len(refs) == 1
    assert refs[0].variant == "D"
    print("✓ Test 1 passed\n")
    
    # Test case 2: Multiple EK-4 references
    text2 = """
    Tanı: EK-4/D ve EK-4/E listesinde yer alan hastalıklar
    Ek olarak EK-4/F kapsamında değerlendirilir.
    """
    
    print("=" * 60)
    print("TEST 2: Multiple EK-4 references")
    print("=" * 60)
    refs = detector.detect(text2)
    print(f"Found {len(refs)} reference(s):")
    for ref in refs:
        print(f"  - {ref.full_text} -> {ref.document_name}")
    assert len(refs) == 3
    variants = {ref.variant for ref in refs}
    assert variants == {"D", "E", "F"}
    print("✓ Test 2 passed\n")
    
    # Test case 3: No EK-4 references
    text3 = """
    Normal SUT hastalık tanısı
    ICD-10: E11.9
    Diyabet tedavisi için başvuru
    """
    
    print("=" * 60)
    print("TEST 3: No EK-4 references")
    print("=" * 60)
    refs = detector.detect(text3)
    print(f"Found {len(refs)} reference(s)")
    assert len(refs) == 0
    print("✓ Test 3 passed\n")
    
    # Test case 4: Case insensitive
    text4 = "ek-4/d ve EK-4/G hastalıkları"
    
    print("=" * 60)
    print("TEST 4: Case insensitive matching")
    print("=" * 60)
    refs = detector.detect(text4)
    print(f"Found {len(refs)} reference(s):")
    for ref in refs:
        print(f"  - {ref.full_text} -> {ref.document_name}")
    assert len(refs) == 2
    print("✓ Test 4 passed\n")
    
    # Test case 5: Unknown variant
    text5 = "EK-4/X ve EK-4/Z hastalıkları"
    
    print("=" * 60)
    print("TEST 5: Unknown variants (should be ignored)")
    print("=" * 60)
    refs = detector.detect(text5)
    print(f"Found {len(refs)} reference(s)")
    assert len(refs) == 0
    print("✓ Test 5 passed\n")
    
    # Test helper methods
    print("=" * 60)
    print("TEST 6: Helper methods")
    print("=" * 60)
    print(f"Has EK-4 in text1: {detector.has_ek4_reference(text1)}")
    print(f"Has EK-4 in text3: {detector.has_ek4_reference(text3)}")
    print(f"All variants: {detector.get_all_variants()}")
    print(f"All documents: {detector.get_all_documents()}")
    print(f"Document for 'D': {detector.get_document_path('D')}")
    assert detector.has_ek4_reference(text1) == True
    assert detector.has_ek4_reference(text3) == False
    print("✓ Test 6 passed\n")
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_ek4_detector()
