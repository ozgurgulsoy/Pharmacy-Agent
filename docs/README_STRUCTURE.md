# Pharmacy Agent - Project Structure (Feature-Based)

## 📁 Directory Structure

```
pharmacy-agent/
├── app/                          # Main application package
│   ├── core/                     # Core business logic
│   │   ├── parsers/             # Report parsing modules
│   │   │   ├── input_parser.py
│   │   │   ├── drug_extractor.py
│   │   │   ├── diagnosis_extractor.py
│   │   │   └── patient_extractor.py
│   │   ├── document_processing/ # PDF & chunking
│   │   │   ├── pdf_loader.py
│   │   │   ├── chunker.py
│   │   │   ├── embeddings.py
│   │   │   └── sut_processor.py
│   │   ├── rag/                 # RAG engine
│   │   │   ├── faiss_store.py
│   │   │   └── retriever.py
│   │   └── llm/                 # LLM integration
│   │       ├── openai_client.py
│   │       ├── prompts.py
│   │       └── eligibility_checker.py
│   ├── models/                   # Data models & schemas
│   │   ├── report.py
│   │   ├── drug.py
│   │   ├── diagnosis.py
│   │   └── eligibility.py
│   ├── services/                 # High-level orchestrators
│   │   └── sut_checker_service.py
│   ├── interfaces/               # User interfaces
│   │   ├── cli/                 # Command-line interface
│   │   │   └── main.py
│   │   ├── api/                 # REST API (FastAPI)
│   │   │   └── app.py
│   │   └── web/                 # Web UI
│   │       ├── static/
│   │       │   └── js/
│   │       │       └── app.js
│   │       └── templates/
│   │           └── index.html
│   └── config/                   # Configuration
│       └── settings.py
├── data/                         # Data files
│   ├── 9.5.17229.pdf            # SUT document
│   ├── faiss_index              # FAISS index
│   ├── faiss_metadata.json      # Metadata
│   └── embedding_cache/         # Cache
├── scripts/                      # Utility scripts
│   └── setup_faiss.py           # Index SUT document
├── docs/                         # Documentation
│   ├── chunking_guide.md
│   └── CHUNKING_QUICKSTART.md
├── tests/                        # Tests (mirrors app/)
│   ├── core/
│   ├── models/
│   └── services/
├── .env                          # Environment variables
├── .gitignore
├── requirements.txt
├── run.py                        # Quick launcher (Web UI)
└── architecture.md               # Architecture docs
```

## 🎯 Design Principles

### Feature-Based Structure
- **Core**: Business logic organized by feature domain
- **Services**: High-level orchestrators that combine core components
- **Interfaces**: Multiple UI options (CLI, API, Web)
- **Models**: Shared data structures
- **Config**: Centralized configuration

### Benefits
- ✅ **Clear separation of concerns**: Each directory has a single responsibility
- ✅ **Easy navigation**: Features are grouped logically
- ✅ **Testable**: Each module can be tested independently
- ✅ **Scalable**: Easy to add new features or interfaces
- ✅ **Maintainable**: Changes are localized to specific areas

## 📦 Key Components

### Core (`app/core/`)
Business logic organized by domain:

- **parsers/**: Extract structured data from patient reports
- **document_processing/**: Handle PDF, chunking, embeddings
- **rag/**: Vector database and retrieval logic
- **llm/**: OpenAI integration and prompt management

### Models (`app/models/`)
Pydantic/dataclass models for type safety:

- `report.py`: ParsedReport, PatientInfo, Doctor
- `drug.py`: Drug information
- `diagnosis.py`: Diagnosis with ICD-10 codes
- `eligibility.py`: EligibilityResult, Condition

### Services (`app/services/`)
High-level orchestrators:

- `sut_checker_service.py`: Main service combining all components
  - Single initialization point
  - Clean API for report analysis
  - Centralized error handling

### Interfaces (`app/interfaces/`)
Multiple ways to interact with the system:

- **CLI** (`cli/main.py`): Rich terminal interface
- **API** (`api/app.py`): FastAPI REST endpoints
- **Web** (`web/`): Browser-based UI

## 🚀 Usage

### Web Interface (Recommended)
```bash
python run.py
# Visit http://localhost:8000
```

### CLI Interface
```bash
python -m app.interfaces.cli.main
```

### API Interface
```bash
uvicorn app.interfaces.api.app:app --reload
# API docs: http://localhost:8000/docs
```

### Using the Service Directly (in code)
```python
from app.services.sut_checker_service import SUTCheckerService

service = SUTCheckerService()
service.initialize()

result = service.check_eligibility(report_text)
```

## 🔧 Development

### Adding a New Feature

**1. Core Logic** (`app/core/`)
```python
# app/core/new_feature/processor.py
class NewFeatureProcessor:
    def process(self, data):
        # Implementation
        pass
```

**2. Service Integration** (`app/services/`)
```python
# Update sut_checker_service.py or create new service
from app.core.new_feature.processor import NewFeatureProcessor

class SUTCheckerService:
    def new_feature_method(self):
        processor = NewFeatureProcessor()
        return processor.process()
```

**3. Interface** (`app/interfaces/`)
```python
# Add endpoint in app/interfaces/api/app.py
@app.post("/api/new-feature")
async def new_feature(request: Request):
    return api_handler.service.new_feature_method()
```

### Testing Structure
```
tests/
├── core/
│   ├── test_parsers.py
│   ├── test_rag.py
│   └── test_llm.py
├── models/
│   └── test_models.py
└── services/
    └── test_sut_checker_service.py
```

## 🔄 Migration from Old Structure

The old structure was:
```
src/
├── parsers/
├── document_processing/
├── rag/
├── llm/
├── models/
├── config/
├── cli/
└── api/
```

**Key Changes:**
1. `src/` → `app/` (more standard Python naming)
2. Added `app/core/` to group business logic
3. Added `app/services/` for orchestration
4. Moved UI to `app/interfaces/`
5. Moved `web/` inside `app/interfaces/web/`

**Import Changes:**
```python
# Old
from parsers.input_parser import InputParser

# New
from app.core.parsers.input_parser import InputParser
```

## 📚 Additional Resources

- See `architecture.md` for detailed system architecture
- See `docs/` for specific feature documentation
- API documentation: Run server and visit `/docs`

## 🎓 Best Practices

1. **Never import from interfaces to core**: Core should be independent
2. **Services orchestrate core**: Don't put business logic in services
3. **Models are shared**: All layers can import from models
4. **Config is centralized**: Single source of truth for settings
5. **Test each layer**: Core → Services → Interfaces

## 🔗 Next Steps

- [ ] Add comprehensive tests
- [ ] Create API versioning (v1, v2)
- [ ] Add database support (if needed)
- [ ] Add authentication/authorization
- [ ] Create Docker deployment
