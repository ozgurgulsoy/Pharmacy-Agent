# Pharmacy Agent - Web UI

Modern web interface for the Pharmacy SUT Checker application, built with **FastAPI** and **Tailwind CSS**.

## Quick Start

```bash
# 1. Install dependencies (first time)
pip install -r requirements.txt

# 2. Setup FAISS index (first time)
python scripts/setup_faiss.py

# 3. Configure environment
cp .env.example .env
# Add your OPENAI_API_KEY to .env

# 4. Start the server
./start.sh
```

Then open **http://localhost:8000** in your browser.

## Usage

1. **Paste Report** - Copy patient report text into the textarea
2. **Click "Analiz Et"** - Start the analysis
3. **View Results** - See detailed eligibility for each drug

## Features

- 📝 **Report Input** - Simple text paste interface
- 🔍 **Real-time Analysis** - Fast processing with loading states
- 💊 **Drug Results** - Color-coded eligibility status
  - 🟢 Green: SGK covered
  - 🟡 Yellow: Conditional
  - 🔴 Red: Not covered
- ✅ **Condition Checking** - Met/unmet requirements
- 📖 **SUT References** - Exact regulation citations
- ⚠️ **Warnings** - Important alerts
- 📊 **Performance Metrics** - Processing time breakdown

## API Endpoints

- `GET /` - Web UI
- `POST /api/analyze` - Analyze patient report
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation

## Tech Stack

- **Backend:** FastAPI (Python)
- **Frontend:** Tailwind CSS + Vanilla JavaScript
- **Vector DB:** FAISS (local, fast)
- **LLM:** OpenAI GPT-4
- **Server:** Uvicorn

## Development

```bash
# Start with auto-reload
source venv/bin/activate
python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

## Makefile Commands

```bash
make help          # Show all commands
make install       # Install dependencies
make setup-faiss   # Setup FAISS index
make start         # Start server
make clean         # Clean temporary files
```

## Project Structure

```
.
├── src/api/app.py              # FastAPI server
├── web/
│   ├── templates/index.html    # Web UI
│   └── static/js/app.js        # Frontend JavaScript
├── start.sh                    # Startup script
└── requirements.txt            # Python dependencies
```

## Troubleshooting

**FAISS index not found:**
```bash
python scripts/setup_faiss.py
```

**Port 8000 in use:**
```bash
lsof -ti:8000 | xargs kill -9
```

**Check logs:**
```bash
tail -f python-api.log
```

---

**Simple. Fast. Effective.** ✨
