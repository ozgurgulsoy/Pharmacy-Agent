"""FastAPI web service for Pharmacy SUT Checker."""

import sys
import logging
from pathlib import Path
from typing import Dict, Any

# Add app to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI

from app.config.settings import (
    OPENAI_API_KEY,
    FAISS_INDEX_PATH,
    FAISS_METADATA_PATH,
    TOP_K_CHUNKS,
)
from app.core.parsers.input_parser import InputParser
from app.core.rag.faiss_store import FAISSVectorStore
from app.core.rag.retriever import RAGRetriever
from app.core.llm.openai_client import OpenAIClientWrapper
from app.core.llm.eligibility_checker import EligibilityChecker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Pharmacy SUT Checker API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
web_static_path = project_root / "app" / "interfaces" / "web" / "static"
if web_static_path.exists():
    app.mount("/static", StaticFiles(directory=str(web_static_path)), name="static")


class ReportRequest(BaseModel):
    """Request model for report analysis."""
    report_text: str


class ConditionResponse(BaseModel):
    """Condition response model."""
    description: str
    is_met: bool | None
    required_info: str | None = None


class EligibilityResponse(BaseModel):
    """Eligibility result response model."""
    drug_name: str
    status: str
    confidence: float
    sut_reference: str
    conditions: list[ConditionResponse]
    explanation: str
    warnings: list[str]


class ReportInfoResponse(BaseModel):
    """Report information response."""
    report_id: str
    date: str
    doctor_name: str
    doctor_specialty: str
    diagnosis_code: str | None
    diagnosis_name: str | None
    drug_count: int


class AnalysisResponse(BaseModel):
    """Complete analysis response."""
    report_info: ReportInfoResponse
    results: list[EligibilityResponse]
    performance: Dict[str, float]


class PharmacyAPI:
    """Pharmacy SUT Checker API handler."""

    def __init__(self):
        self.parser = InputParser()
        self.vector_store = None
        self.retriever = None
        self.eligibility_checker = None
        self.openai_client_wrapper = None
        self.openai_client = None
        self.initialized = False

    def initialize(self):
        """Initialize the system."""
        if self.initialized:
            return

        logger.info("Initializing Pharmacy API...")

        try:
            # OpenAI client
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            self.openai_client_wrapper = OpenAIClientWrapper()
            logger.info("OpenAI client initialized")

            # FAISS vector store
            self.vector_store = FAISSVectorStore()
            self.vector_store.load(FAISS_INDEX_PATH, FAISS_METADATA_PATH)
            stats = self.vector_store.get_stats()
            logger.info(f"FAISS index loaded ({stats['total_vectors']} vectors)")

            # RAG retriever
            self.retriever = RAGRetriever(self.vector_store, self.openai_client)
            logger.info("RAG retriever initialized")

            # Eligibility checker
            self.eligibility_checker = EligibilityChecker(self.openai_client_wrapper)
            logger.info("Eligibility checker initialized")

            self.initialized = True
            logger.info("System initialized successfully")

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    def process_report(self, report_text: str) -> AnalysisResponse:
        """Process a report and return analysis results."""
        import time

        total_start = time.time()
        timings = {}

        # 1. Parse report
        parse_start = time.time()
        parsed_report = self.parser.parse_report(report_text)
        timings['parsing'] = (time.time() - parse_start) * 1000

        # 2. RAG retrieval for all drugs
        retrieval_start = time.time()
        sut_chunks_per_drug, retrieval_timings = self.retriever.retrieve_for_multiple_drugs(
            drugs=parsed_report.drugs,
            diagnosis=parsed_report.diagnoses[0] if parsed_report.diagnoses else None,
            patient=parsed_report.patient,
            top_k_per_drug=TOP_K_CHUNKS
        )
        timings['retrieval'] = (time.time() - retrieval_start) * 1000

        # 3. Eligibility check
        eligibility_start = time.time()
        results = self.eligibility_checker.check_multiple_drugs(
            drugs=parsed_report.drugs,
            diagnoses=parsed_report.diagnoses,
            patient=parsed_report.patient,
            doctor=parsed_report.doctor,
            sut_chunks_per_drug=sut_chunks_per_drug,
            explanations=parsed_report.explanations
        )
        timings['eligibility_check'] = (time.time() - eligibility_start) * 1000

        # Total time
        timings['total'] = (time.time() - total_start) * 1000

        # Build response
        report_info = ReportInfoResponse(
            report_id=parsed_report.report_id,
            date=str(parsed_report.date),
            doctor_name=parsed_report.doctor.name,
            doctor_specialty=parsed_report.doctor.specialty,
            diagnosis_code=parsed_report.diagnoses[0].icd10_code if parsed_report.diagnoses else None,
            diagnosis_name=parsed_report.diagnoses[0].tanim if parsed_report.diagnoses else None,
            drug_count=len(parsed_report.drugs)
        )

        eligibility_results = [
            EligibilityResponse(
                drug_name=r.drug_name,
                status=r.status,
                confidence=r.confidence,
                sut_reference=r.sut_reference,
                conditions=[
                    ConditionResponse(
                        description=c.description,
                        is_met=c.is_met,
                        required_info=c.required_info
                    )
                    for c in r.conditions
                ],
                explanation=r.explanation,
                warnings=r.warnings
            )
            for r in results
        ]

        return AnalysisResponse(
            report_info=report_info,
            results=eligibility_results,
            performance=timings
        )


# Global API instance
api_handler = PharmacyAPI()


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    try:
        api_handler.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        # Don't crash, allow health check to report unhealthy


@app.get("/", response_class=HTMLResponse)
async def serve_home():
    """Serve the main web UI."""
    html_path = project_root / "app" / "interfaces" / "web" / "templates" / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    
    return HTMLResponse(content=html_path.read_text(), status_code=200)


@app.get("/html/app.html", response_class=HTMLResponse)
async def redirect_old_route():
    """Redirect old route to new location."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=301)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if api_handler.initialized:
        return {"status": "healthy", "initialized": True}
    else:
        raise HTTPException(status_code=503, detail="Service not initialized")


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_report(request: ReportRequest):
    """Analyze a patient report."""
    if not api_handler.initialized:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not request.report_text or not request.report_text.strip():
        raise HTTPException(status_code=400, detail="Report text is required")

    try:
        result = api_handler.process_report(request.report_text)
        return result
    except Exception as e:
        logger.exception("Error processing report")
        raise HTTPException(status_code=500, detail=f"Error processing report: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
