# Quick Start: Multi-Document RAG

## 🚀 Getting Started in 3 Steps

### Step 1: Re-index All Documents (Required)

```bash
cd "/Users/ozguromergulsoy/Desktop/Pharmacy Agent"
python3 scripts/setup_faiss.py
```

**What this does:**
- Processes SUT.pdf + 4 EK-4 PDFs
- Creates ~505 chunks with metadata
- Generates embeddings
- Saves combined FAISS index

**Expected time:** ~2-5 minutes

### Step 2: Test the Implementation

```bash
# Test EK-4 detector
python3 tests/test_ek4_detector.py
```

**Expected:** All 6 tests pass ✅

### Step 3: Use in Your Application

```python
from app.services.sut_checker_service import SUTCheckerService

# Initialize service
service = SUTCheckerService()
service.initialize()

# Example report with EK-4/D reference
report = """
Hasta: Ahmet Yılmaz
Tanı: EK-4/D Listesinde Yer Almayan Hastalıklar
G62.9 POLİNÖROPATİ
İlaç: Gabapentin 300mg - 3x1
"""

# Check eligibility (automatically queries SUT + EK-4/D)
result = service.check_eligibility(report, top_k=5)

# Check performance metrics
print(f"Total time: {result['performance']['total_ms']:.1f}ms")
print(f"EK-4 refs: {result['performance']['ek4_refs_detected']}")
```

---

## 📝 What Changed?

**For You:** Nothing! The system works automatically.

**Behind the Scenes:**
1. Reports are scanned for "EK-4/X" patterns
2. When found, both SUT and EK-4 docs are queried
3. Results are combined and ranked
4. LLM checks both document conditions

---

## ✅ Verification Checklist

After re-indexing, verify:

- [ ] Index created successfully (`data/faiss_index` exists)
- [ ] Metadata saved (`data/faiss_metadata.json` exists)
- [ ] ~505 total vectors indexed
- [ ] All tests pass
- [ ] Service initializes without errors

---

## 🔍 Testing Your Setup

### Test 1: No EK-4 Reference (Should work as before)
```python
report = "Tanı: E11.9 Diyabet, İlaç: Metformin 500mg"
result = service.check_eligibility(report)
# Should query SUT only
```

### Test 2: With EK-4/D Reference (Should query both)
```python
report = "Tanı: EK-4/D Listesinde, İlaç: Gabapentin"
result = service.check_eligibility(report)
# Should query SUT + EK-4/D
assert result['performance']['ek4_refs_detected'] == 1
```

---

## 📚 Documents Indexed

| Document | File | Chunks |
|----------|------|--------|
| Main SUT | `data/SUT.pdf` | ~480 |
| EK-4/D | `data/20201207-1230-sut-ek-4-d-38dbc.pdf` | ~6 |
| EK-4/E | `data/20201207-1231-sut-ek-4-e-24c20.pdf` | ~6 |
| EK-4/F | `data/20201207-1232-sut-ek-4-f-8f928.pdf` | ~6 |
| EK-4/G | `data/20201207-1233-sut-ek-4-g-1a6a1.pdf` | ~7 |
| **Total** | | **~505** |

---

## ⚡ Performance

- **Without EK-4**: Same speed as before (~100-200ms)
- **With EK-4/D**: +10-20ms overhead
- **Memory**: +5% for extra 25 chunks

---

## ❓ Troubleshooting

### Issue: "Index file not found"
**Solution:** Run `python3 scripts/setup_faiss.py` first

### Issue: "PDF not found"
**Solution:** Verify all PDFs exist in `data/` directory:
```bash
ls -la data/*.pdf
```

### Issue: Tests failing
**Solution:** Check Python environment:
```bash
python3 --version  # Should be 3.8+
pip3 list | grep -E "openai|faiss|pypdf"
```

---

## 📖 More Information

- Full documentation: `docs/multi_document_rag.md`
- Implementation details: `IMPLEMENTATION_SUMMARY.md`
- EK-4 detector code: `app/core/parsers/ek4_detector.py`

---

## 🎯 Summary

✅ **Install**: Run indexing script  
✅ **Test**: Verify with tests  
✅ **Use**: Service works automatically  
✅ **No code changes**: Backward compatible  

**That's it! You're ready to go.** 🚀
