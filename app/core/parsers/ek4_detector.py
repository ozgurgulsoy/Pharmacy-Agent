"""
EK-4 reference detector for patient reports.
Detects references like "EK-4/D", "EK-4/E", etc. in report text.
"""

import re
import logging
from typing import List, Set, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EK4Reference:
    """Represents a detected EK-4 reference."""
    full_text: str  # e.g., "EK-4/D"
    variant: str  # e.g., "D", "E", "F", "G"
    document_name: str  # e.g., "20201207-1230-sut-ek-4-d-38dbc.pdf"
    
    def __hash__(self):
        return hash(self.full_text)
    
    def __eq__(self, other):
        if isinstance(other, EK4Reference):
            return self.full_text == other.full_text
        return False


class EK4Detector:
    """
    Detects EK-4 document references in patient reports.
    
    EK-4 references appear in the format: "EK-4/X" where X is a letter (D, E, F, G).
    When detected, the system needs to check both SUT and the specific EK-4 document.
    """
    
    # Mapping from EK-4 variant letter to PDF filename
    EK4_DOCUMENTS = {
        "D": "20201207-1230-sut-ek-4-d-38dbc.pdf",
        "E": "20201207-1231-sut-ek-4-e-24c20.pdf",
        "F": "20201207-1232-sut-ek-4-f-8f928.pdf",
        "G": "20201207-1233-sut-ek-4-g-1a6a1.pdf",
    }
    
    # Pattern to match EK-4 references: "EK-4/X" where X is a letter
    # Matches both "EK-4/D" and "EK-4/D Listesinde" formats
    EK4_PATTERN = re.compile(
        r'\bEK-4/([A-Z])\b',
        re.IGNORECASE | re.UNICODE
    )
    
    # Additional pattern for diagnosis codes like "20.00 – EK-4/D Listesinde..."
    EK4_DIAGNOSIS_PATTERN = re.compile(
        r'(?:EK-4/([A-Z]))\s+Liste',
        re.IGNORECASE | re.UNICODE
    )
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def detect(self, text: str) -> List[EK4Reference]:
        """
        Detect all EK-4 references in the given text.
        
        Args:
            text: Patient report text to scan
            
        Returns:
            List of unique EK4Reference objects found in the text
            
        Example:
            >>> detector = EK4Detector()
            >>> refs = detector.detect("Tanı: EK-4/D Listesinde Yer Almayan...")
            >>> refs[0].variant
            'D'
        """
        if not text:
            return []
        
        references: Set[EK4Reference] = set()
        
        # Search with both patterns
        for pattern in [self.EK4_PATTERN, self.EK4_DIAGNOSIS_PATTERN]:
            matches = pattern.finditer(text)
            
            for match in matches:
                full_text = match.group(0)  # e.g., "EK-4/D" or "EK-4/D Liste"
                variant = match.group(1).upper()  # e.g., "D"
                
                # Check if we have a document for this variant
                if variant in self.EK4_DOCUMENTS:
                    document_name = self.EK4_DOCUMENTS[variant]
                    ref = EK4Reference(
                        full_text=f"EK-4/{variant}",  # Normalize format
                        variant=variant,
                        document_name=document_name
                    )
                    references.add(ref)
                    self.logger.debug(f"Detected EK-4 reference: {full_text} -> {document_name}")
                else:
                    self.logger.warning(f"Detected unknown EK-4 variant: {variant}")
        
        result = list(references)
        if result:
            self.logger.info(f"Found {len(result)} unique EK-4 reference(s): {[r.full_text for r in result]}")
        else:
            self.logger.debug("No EK-4 references found in text")
        
        return result
    
    def has_ek4_reference(self, text: str) -> bool:
        """
        Quick check if text contains any EK-4 reference.
        
        Args:
            text: Text to check
            
        Returns:
            True if any EK-4 reference is found
        """
        return bool(self.EK4_PATTERN.search(text))
    
    def get_document_path(self, variant: str) -> Optional[str]:
        """
        Get the PDF filename for a specific EK-4 variant.
        
        Args:
            variant: EK-4 variant letter (D, E, F, or G)
            
        Returns:
            PDF filename or None if variant is unknown
        """
        return self.EK4_DOCUMENTS.get(variant.upper())
    
    def get_all_variants(self) -> List[str]:
        """Get all supported EK-4 variants."""
        return list(self.EK4_DOCUMENTS.keys())
    
    def get_all_documents(self) -> List[str]:
        """Get all EK-4 document filenames."""
        return list(self.EK4_DOCUMENTS.values())
