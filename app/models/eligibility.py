"""Data models for eligibility analysis results."""

from dataclasses import dataclass
from typing import List, Optional, Literal


@dataclass
class Condition:
    """Uygunluk koşulu model."""
    description: str
    is_met: Optional[bool]  # True/False/None (belirlenemedi)
    required_info: Optional[str] = None  # Eksik bilgi varsa


@dataclass
class EligibilityResult:
    """İlaç uygunluk sonucu model."""
    drug_name: str
    status: Literal["ELIGIBLE", "NOT_ELIGIBLE", "CONDITIONAL"]
    confidence: float  # 0.0 - 1.0
    sut_reference: str  # "4.2.28.C (satır 12528-12550)"
    conditions: List[Condition]
    explanation: str  # Türkçe açıklama
    warnings: List[str]


@dataclass
class ChunkMetadata:
    """SUT chunk metadata model."""
    section: str              # "4.2.28" (madde numarası)
    topic: str                # "Lipid düşürücü ilaçlar"
    etkin_madde: List[str]    # ["ezetimib", "statin"]
    keywords: List[str]       # önemli terimler
    drug_related: bool
    has_conditions: bool
    doc_type: str = "SUT"     # Document type: "SUT", "EK-4/D", "EK-4/E", etc.
    doc_source: str = ""      # Source filename for traceability


@dataclass
class Chunk:
    """SUT doküman chunk model."""
    chunk_id: str
    content: str
    metadata: ChunkMetadata
    start_line: int
    end_line: int


@dataclass
class RetrievedChunk:
    """Retrieved chunk with score."""
    chunk: Chunk
    score: float