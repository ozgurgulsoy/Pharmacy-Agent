#!/bin/bash

# Pharmacy Agent - Simple FastAPI Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          PHARMACY AGENT WEB APPLICATION                 ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${RED}✗ Virtual environment not found!${NC}"
    echo -e "${YELLOW}Please create it first:${NC}"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Check if FAISS index exists
if [ ! -f "$PROJECT_ROOT/data/faiss_index" ]; then
    echo -e "${YELLOW}⚠ FAISS index not found. Running setup...${NC}"
    source "$PROJECT_ROOT/venv/bin/activate"
    python "$PROJECT_ROOT/scripts/setup_faiss.py"
fi

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${RED}✗ .env file not found!${NC}"
    echo -e "${YELLOW}Please create it from .env.example and add your OPENAI_API_KEY${NC}"
    exit 1
fi

# Load environment variables
source "$PROJECT_ROOT/.env"

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}✗ OPENAI_API_KEY not set in .env file!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment setup complete${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start FastAPI server
echo -e "${BLUE}Starting FastAPI server...${NC}"
source "$PROJECT_ROOT/venv/bin/activate"
cd "$PROJECT_ROOT"

# Check if uvicorn is installed
if ! python -c "import uvicorn" 2>/dev/null; then
    echo -e "${YELLOW}Installing uvicorn...${NC}"
    pip install uvicorn
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 🚀 SERVER RUNNING                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}Web UI:${NC}        http://localhost:8000"
echo -e "  ${BLUE}API Docs:${NC}      http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Run server
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
