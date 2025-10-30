#!/usr/bin/env python3
"""
Pharmacy Agent - Web Application Launcher
Simple click-to-run script for the web UI.
"""

import sys
import os
import subprocess
from pathlib import Path

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def print_header():
    """Print startup header."""
    print(f"{BLUE}╔══════════════════════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║          PHARMACY AGENT WEB APPLICATION                 ║{NC}")
    print(f"{BLUE}╚══════════════════════════════════════════════════════════╝{NC}")
    print()


def check_requirements():
    """Check if all requirements are met."""
    project_root = Path(__file__).parent
    
    # Check virtual environment
    venv_path = project_root / "venv"
    if not venv_path.exists():
        print(f"{RED}✗ Virtual environment not found!{NC}")
        print(f"{YELLOW}Please create it first:{NC}")
        print("  python3 -m venv venv")
        print("  source venv/bin/activate")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    
    # Check FAISS index
    faiss_index = project_root / "data" / "faiss_index"
    if not faiss_index.exists():
        print(f"{YELLOW}⚠ FAISS index not found. Running setup...{NC}")
        python_exe = venv_path / "bin" / "python"
        setup_script = project_root / "scripts" / "setup_faiss.py"
        subprocess.run([str(python_exe), str(setup_script)], check=True)
    
    # Check .env file
    env_file = project_root / ".env"
    if not env_file.exists():
        print(f"{RED}✗ .env file not found!{NC}")
        print(f"{YELLOW}Please create it from .env.example and add your OPENAI_API_KEY{NC}")
        sys.exit(1)
    
    # Check OPENAI_API_KEY
    with open(env_file) as f:
        env_content = f.read()
        if "OPENAI_API_KEY" not in env_content or "sk-" not in env_content:
            print(f"{RED}✗ OPENAI_API_KEY not set in .env file!{NC}")
            sys.exit(1)
    
    print(f"{GREEN}✓ Environment setup complete{NC}")
    print()


def start_server():
    """Start the FastAPI server."""
    project_root = Path(__file__).parent
    python_exe = project_root / "venv" / "bin" / "python"
    
    print(f"{BLUE}Starting FastAPI server...{NC}")
    print()
    print(f"{GREEN}╔══════════════════════════════════════════════════════════╗{NC}")
    print(f"{GREEN}║                 🚀 SERVER RUNNING                        ║{NC}")
    print(f"{GREEN}╚══════════════════════════════════════════════════════════╝{NC}")
    print()
    print(f"  {BLUE}Web UI:{NC}        http://localhost:8000")
    print(f"  {BLUE}API Docs:{NC}      http://localhost:8000/docs")
    print()
    print(f"{YELLOW}Press Ctrl+C to stop the server{NC}")
    print()
    
    # Change to project root
    os.chdir(project_root)
    
    # Run uvicorn
    try:
        subprocess.run([
            str(python_exe), "-m", "uvicorn",
            "src.api.app:app",
            "--host", "0.0.0.0",
            "--port", "8000"
        ], check=True)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutting down...{NC}")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"{RED}✗ Server failed to start: {e}{NC}")
        sys.exit(1)


def main():
    """Main entry point."""
    print_header()
    check_requirements()
    start_server()


if __name__ == "__main__":
    main()
