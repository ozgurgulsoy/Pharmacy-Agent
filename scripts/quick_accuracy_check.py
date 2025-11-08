"""Quick sanity check for retrieval accuracy.

Run this after rebuilding the FAISS index to verify basic retrieval works.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.rag.faiss_store import FAISSVectorStore
from app.core.rag.retriever import RAGRetriever
from app.models.report import Drug, Diagnosis

def test_known_good_cases():
    """Test known-good retrieval cases."""
    print("🧪 Quick Accuracy Check")
    print("=" * 60)
    
    # Initialize retriever
    print("\n📥 Loading FAISS index...")
    try:
        vector_store = FAISSVectorStore()
        vector_store.load()
        retriever = RAGRetriever(vector_store)
    except Exception as e:
        print(f"❌ Failed to load FAISS index: {e}")
        print(f"   Action: Run 'python scripts/setup_faiss.py' to build index")
        return
    
    # Get stats
    stats = vector_store.get_stats()
    print(f"✅ Loaded {stats['dimension']}-dimensional index with {stats['total_vectors']} vectors")
    
    # Comprehensive test cases from patient_report.txt
    test_cases = [
        # Case 1: Single document - SUT only
        {
            "name": "Ezetimib for Hyperlipidemia (SUT only)",
            "drug": "EZETİMİB",
            "diagnosis": "E78.4 HİPERLİPİDEMİ",
            "diagnosis_details": "En az 6 ay boyunca statinlerle tedavi edilmiş olmasına rağmen LDL düzeyi 100'ün üzerinde kalan hasta",
            "expected_terms": ["ezetimib", "statin", "LDL"],
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.67  # At least 2/3 terms
        },
        # Case 2: Multi-document - SUT + EK-4/D
        {
            "name": "Gabapentin for Neuropathy (Multi-doc: SUT + EK-4/D)",
            "drug": "GABAPENTİN",
            "diagnosis": "20.00 – EK-4/D Listesinde Yer Almayan Hastalıklar, G62.9 POLİNÖROPATİ",
            "diagnosis_details": "NÖROPATİK AĞRI",
            "expected_terms": ["gabapentin", "nöropatik"],
            "expected_doc_types": ["SUT", "EK-4/D"],
            "min_coverage": 0.50  # At least 1/2 terms
        },
        # Case 3: Cardiovascular - Antiplatelet
        {
            "name": "Klopidogrel for Coronary Artery Disease",
            "drug": "KLOPİDOGREL HİDROJEN SÜLFAT",
            "diagnosis": "I25.0 Koroner arter hastalığı",
            "diagnosis_details": "Hasta 12.01.2022 tarihinde kurumumuzda koroner anjiyo olmuştur",
            "expected_terms": ["koroner", "arter"],
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.50
        },
        # Case 4: Beta-blocker for hypertension (GENERIC - class-based approval)
        {
            "name": "Metoprolol for Hypertension",
            "drug": "METOPROLOL",
            "diagnosis": "I10 Esansiyel (Primer) Hipertansiyon",
            "diagnosis_details": "Monoterapi ile kontrol altına alınamamış hipertansiyon",
            "expected_terms": ["beta-bloker", "hipertansiyon", "kardiyovasküler"],  # Search by CLASS not specific drug
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.33  # Lower threshold - generic drugs referenced by class
        },
        # Case 5: Angiotensin receptor blocker (GENERIC - class-based approval)
        {
            "name": "Irbesartan for Hypertension",
            "drug": "IRBESARTAN",
            "diagnosis": "I10 Esansiyel (Primer) Hipertansiyon",
            "diagnosis_details": "Kan basıncı kontrolü için kombinasyon tedavisi",
            "expected_terms": ["arb", "anjiotensin", "hipertansiyon"],  # Search by CLASS not specific drug
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.33  # Lower threshold - generic drugs referenced by class
        },
        # Case 6: Statin for hyperlipidemia
        {
            "name": "Atorvastatin for Hyperlipidemia",
            "drug": "ATORVASTATİN KALSİYUM 40 MG",
            "diagnosis": "E78.4 Hiperkolesterolemi, Hiperlipidemi",
            "diagnosis_details": "HASTA 19.01.2023 TARİHİNDE KÖÜ DE ANJİO OLMUŞTUR. LDL DEĞERİ: 107.8",
            "expected_terms": ["atorvastatin", "LDL", "kolesterol"],
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.50
        },
        # Case 7: Rheumatology - DMARD
        {
            "name": "Leflunomid for Rheumatoid Arthritis",
            "drug": "LEFLUNOMID",
            "diagnosis": "M06.82 Romatoid Artrit",
            "diagnosis_details": "DİĞER ROMATOİD ARTRİT, TANIMLANMIŞ, KOL",
            "expected_terms": ["leflunomid", "romatoid"],
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.50
        },
        # Case 8: Dermatology - Biological for Psoriasis
        {
            "name": "Ixekizumab for Plaque Psoriasis",
            "drug": "İKSEKİZUMAB",
            "diagnosis": "L40.0 Psoriasis Vulgaris",
            "diagnosis_details": "ORTA VEYA ŞİDDETLİ PLAK TİPİ PSÖRİYAZİS PASI SKORU: 12",
            "expected_terms": ["psöriaz", "plak"],  # Focus on condition, not drug name (biologics often use brand names)
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.67
        },
        # Case 9: Osteoporosis
        {
            "name": "Alendronate for Osteoporosis",
            "drug": "ALENDRONAT SODYUM",
            "diagnosis": "M81.0 Postmenapozal Osteoporoz",
            "diagnosis_details": "25/03/2025 BAKILAN TOTAL LUMBAL T SKORU (L1–L4): -2,5 VE PATOLOJİK KIRIK ÖYKÜSÜ MEVCUT",
            "expected_terms": ["osteoporoz", "kemik"],
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.50
        },
        # Case 10: Alpha-blocker for hypertension (GENERIC - class-based approval)
        {
            "name": "Doxazosin for Hypertension",
            "drug": "DOKSAZOSİN MEZİLAT",
            "diagnosis": "I10 Esansiyel (Primer) Hipertansiyon",
            "diagnosis_details": "Kombinasyon tedavisi gereksinimi",
            "expected_terms": ["alfa-bloker", "hipertansiyon", "kombinasyon"],  # Search by CLASS
            "expected_doc_types": ["SUT"],
            "min_coverage": 0.33
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n{'─' * 60}")
        print(f"🧪 Test: {test['name']}")
        print(f"   Drug: {test['drug']}")
        print(f"   Diagnosis: {test['diagnosis'][:50]}...")
        
        try:
            from datetime import date
            
            # Create Drug object with all required fields
            drug = Drug(
                kod="TEST",
                etkin_madde=test["drug"],
                form="Ağızdan tablet",
                tedavi_sema="Günde 1 x 1.0",
                miktar=1,
                eklenme_zamani=date.today()
            )
            
            diagnosis = Diagnosis(tanim=test["diagnosis"], icd10_code="TEST")
            
            chunks, timings = retriever.retrieve_relevant_chunks(
                drug=drug,
                diagnosis=diagnosis,
                report_text=test["diagnosis"],  # Use diagnosis as report_text for EK-4 detection
                top_k=5
            )
            
            print(f"\n   Retrieved {len(chunks)} chunks in {timings.get('total', 0):.1f}ms")
            
            # Check expected terms
            found_terms = []
            for chunk in chunks[:3]:
                content = chunk["metadata"]["content"].lower()
                for term in test["expected_terms"]:
                    if term.lower() in content:
                        found_terms.append(term)
            
            found_unique = set(found_terms)
            coverage = len(found_unique) / len(test["expected_terms"])
            
            print(f"\n   📊 Term Coverage: {coverage:.1%} ({len(found_unique)}/{len(test['expected_terms'])})")
            print(f"      Expected: {test['expected_terms']}")
            print(f"      Found: {list(found_unique)}")
            
            # Check doc types
            doc_types = set(c["metadata"].get("doc_type", "UNKNOWN") for c in chunks)
            print(f"\n   📄 Document Types: {sorted(doc_types)}")
            
            doc_type_match = True
            for expected_type in test["expected_doc_types"]:
                if expected_type in doc_types:
                    print(f"      ✅ Found {expected_type} chunks")
                else:
                    print(f"      ❌ Missing {expected_type} chunks")
                    doc_type_match = False
            
            # Show top 3 chunks
            print(f"\n   🔍 Top 3 Chunks:")
            for i, chunk in enumerate(chunks[:3], 1):
                doc_type = chunk["metadata"].get("doc_type", "UNKNOWN")
                score = chunk.get("score", 0)
                match_type = chunk.get("match_type", "unknown")
                section = chunk["metadata"].get("section", "N/A")
                content_preview = chunk["metadata"]["content"][:80].replace("\n", " ")
                
                print(f"      [{i}] Score: {score:.3f} | {doc_type} | {match_type} | §{section}")
                print(f"          {content_preview}...")
            
            # Overall result
            min_coverage = test.get("min_coverage", 0.67)  # Default 67% coverage
            if coverage >= min_coverage and doc_type_match:
                print(f"\n   ✅ PASS")
                passed += 1
            else:
                print(f"\n   ❌ FAIL")
                if coverage < min_coverage:
                    print(f"      Reason: Low term coverage ({coverage:.1%} < {min_coverage:.1%})")
                if not doc_type_match:
                    print(f"      Reason: Missing expected document types")
                failed += 1
                
        except Exception as e:
            print(f"\n   ❌ ERROR: {e}")
            failed += 1
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"📊 Test Summary:")
    print(f"   Total Tests: {passed + failed}")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   Success Rate: {passed / (passed + failed) * 100:.1f}%")
    
    # Category breakdown
    sut_only_tests = [t for t in test_cases if t["expected_doc_types"] == ["SUT"]]
    multi_doc_tests = [t for t in test_cases if len(t["expected_doc_types"]) > 1]
    
    print(f"\n📋 Test Categories:")
    print(f"   SUT-only tests: {len(sut_only_tests)}")
    print(f"   Multi-document tests: {len(multi_doc_tests)}")
    
    # Performance stats
    print(f"\n⚡ Performance:")
    print(f"   Average retrieval time: Not tracked (add timing if needed)")
    
    if failed == 0:
        print(f"\n🎉 All tests passed! Your RAG system is working correctly.")
        print(f"\n✅ System Status: PRODUCTION READY")
        print(f"   - Single-document retrieval: ✅ Working")
        print(f"   - Multi-document retrieval: ✅ Working")
        print(f"   - Term coverage: ✅ Excellent")
    else:
        success_rate = passed / (passed + failed)
        if success_rate >= 0.8:
            print(f"\n✅ Good performance! Most tests passed ({success_rate:.1%})")
            print(f"   Review failed tests for minor improvements.")
        elif success_rate >= 0.6:
            print(f"\n⚠️  Acceptable performance ({success_rate:.1%})")
            print(f"   Some optimization recommended.")
        else:
            print(f"\n❌ System needs attention ({success_rate:.1%} pass rate)")
        
        print(f"\nCommon issues:")
        print(f"  1. Missing doc_type metadata → Run: python scripts/setup_faiss.py")
        print(f"  2. Low term coverage → Check chunking strategy or embedding quality")
        print(f"  3. Missing EK-4 chunks → Verify EK-4 detection logic")
        print(f"\nNext steps:")
        print(f"  - Review failed test output above")
        print(f"  - Check if expected terms are actually in SUT/EK-4 documents")
        print(f"  - Consider adjusting min_coverage thresholds")

if __name__ == "__main__":
    test_known_good_cases()
