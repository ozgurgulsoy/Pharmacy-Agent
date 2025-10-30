.PHONY: help install setup-faiss start test clean

# Default target
help:
	@echo "Pharmacy Agent - Commands"
	@echo "========================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make setup-faiss  - Setup FAISS index (first time only)"
	@echo ""
	@echo "Run Commands:"
	@echo "  make start        - Start FastAPI server"
	@echo ""
	@echo "Development:"
	@echo "  make test         - Run tests"
	@echo "  make clean        - Clean logs and temporary files"
	@echo ""

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	python3 -m venv venv || true
	. venv/bin/activate && pip install -r requirements.txt
	@echo ""
	@echo "✓ Installation complete!"

# Setup FAISS index
setup-faiss:
	@echo "Setting up FAISS index..."
	. venv/bin/activate && python scripts/setup_faiss.py
	@echo "✓ FAISS index ready!"

# Start FastAPI server
start:
	@echo "Starting FastAPI server..."
	./start.sh

# Run tests
test:
	@echo "Running tests..."
	. venv/bin/activate && python -m pytest tests/ -v

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	rm -f python-api.log
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✓ Cleanup complete!"
