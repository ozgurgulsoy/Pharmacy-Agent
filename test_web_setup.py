"""
Simple test to verify the FastAPI application setup.
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def test_api_import():
    """Test that the API can be imported."""
    try:
        from src.api.app import app, PharmacyAPI
        print("✓ API imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_api_routes():
    """Test that API routes are defined."""
    try:
        from src.api.app import app
        
        routes = [route.path for route in app.routes]
        
        required_routes = ['/health', '/api/analyze']
        for route in required_routes:
            if route in routes:
                print(f"✓ Route {route} exists")
            else:
                print(f"✗ Route {route} missing")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Route check failed: {e}")
        return False

def test_models():
    """Test that Pydantic models are defined correctly."""
    try:
        from src.api.app import (
            ReportRequest,
            EligibilityResponse,
            ReportInfoResponse,
            AnalysisResponse
        )
        
        # Test ReportRequest
        req = ReportRequest(report_text="Test report")
        assert req.report_text == "Test report"
        print("✓ ReportRequest model works")
        
        return True
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Web UI Setup Verification")
    print("=" * 60)
    print()
    
    tests = [
        ("API Import", test_api_import),
        ("API Routes", test_api_routes),
        ("Pydantic Models", test_models),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\nTesting: {name}")
        print("-" * 40)
        result = test_func()
        results.append(result)
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed! Web UI is ready to use.")
        print("\nNext steps:")
        print("  1. Make sure .env file has OPENAI_API_KEY")
        print("  2. Run: ./start-web.sh")
        print("  3. Open: http://localhost:3000")
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        sys.exit(1)
