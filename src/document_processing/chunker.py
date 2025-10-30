"""SUT document chunking and metadata enrichment utilities.

This module implements multiple chunking strategies:
1. Semantic Chunking: Preserves paragraphs and logical structure
2. Fixed Chunking: Traditional size-based splitting with overlap
3. Hybrid Chunking: Combines semantic boundaries with size limits
"""

import logging
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from models.eligibility import Chunk, ChunkMetadata
from config.settings import (
    CHUNK_SIZE, 
    CHUNK_OVERLAP, 
    CHUNKING_STRATEGY,
    MIN_CHUNK_SIZE,
    MAX_CHUNK_SIZE,
    PRESERVE_PARAGRAPHS
)

logger = logging.getLogger(__name__)


class SUTDocumentChunker:
    """
    SUT dokümanını anlamlı parçalara bölen sınıf.
    
    Supports multiple chunking strategies:
    - semantic: Preserves paragraph boundaries and logical structure
    - fixed: Traditional character-based chunking with overlap
    - hybrid: Section-based chunking with size constraints (default)
    """

    def __init__(self, strategy: str = CHUNKING_STRATEGY):
        """
        Initialize the chunker.
        
        Args:
            strategy: Chunking strategy ("semantic", "fixed", or "hybrid")
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.strategy = strategy
        self.logger.info(f"Initialized chunker with strategy: {strategy}")

    def chunk_document(self, text: str) -> List[Chunk]:
        """
        SUT dokümanını chunk'lara böler.

        Args:
            text: Ham SUT metni

        Returns:
            Chunk listesi
        """
        self.logger.info(f"Starting document chunking with strategy: {self.strategy}...")

        # Önce metni temizle
        cleaned_text = self._clean_text(text)

        # Strategy'ye göre chunking yap
        if self.strategy == "semantic":
            chunks = self._semantic_chunking(cleaned_text)
        elif self.strategy == "fixed":
            chunks = self._fixed_chunking(cleaned_text)
        else:  # hybrid (default)
            chunks = self._hybrid_chunking(cleaned_text)

        self.logger.info(f"Created {len(chunks)} chunks")
        return chunks

    def _clean_text(self, text: str) -> str:
        """Metni temizler ve normalize eder."""
        # Sayfa başlıklarını kaldır
        text = re.sub(r'=== Sayfa \d+ ===', '', text)

        # Fazla boşlukları temizle
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

        return text.strip()

    # ==================== Chunking Strategies ====================

    def _semantic_chunking(self, text: str) -> List[Chunk]:
        """
        Semantic chunking: Preserves paragraph boundaries and logical structure.
        Best for: Maintaining context and coherent ideas.
        
        Args:
            text: Cleaned text
            
        Returns:
            List of chunks
        """
        self.logger.info("Using semantic chunking strategy")
        
        # Split by paragraphs (double newline)
        paragraphs = re.split(r'\n\n+', text)
        
        chunks = []
        current_chunk_text = []
        current_chunk_size = 0
        chunk_start_idx = 0
        
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue
                
            para_size = len(para)
            
            # If single paragraph exceeds MAX_CHUNK_SIZE, split it
            if para_size > MAX_CHUNK_SIZE:
                # Save current chunk if exists
                if current_chunk_text:
                    chunk_text = '\n\n'.join(current_chunk_text)
                    chunks.append(self._create_chunk(chunk_text, len(chunks), chunk_start_idx, i-1))
                    current_chunk_text = []
                    current_chunk_size = 0
                
                # Split large paragraph into smaller chunks
                sub_chunks = self._split_large_paragraph(para, i)
                chunks.extend(sub_chunks)
                chunk_start_idx = i + 1
                
            # If adding this paragraph would exceed MAX_CHUNK_SIZE, save current chunk
            elif current_chunk_size + para_size > MAX_CHUNK_SIZE and current_chunk_text:
                chunk_text = '\n\n'.join(current_chunk_text)
                chunks.append(self._create_chunk(chunk_text, len(chunks), chunk_start_idx, i-1))
                
                # Start new chunk with overlap
                if CHUNK_OVERLAP > 0 and current_chunk_text:
                    # Keep last paragraph for overlap
                    overlap_text = current_chunk_text[-1]
                    current_chunk_text = [overlap_text, para]
                    current_chunk_size = len(overlap_text) + para_size
                else:
                    current_chunk_text = [para]
                    current_chunk_size = para_size
                chunk_start_idx = i
                
            # Add paragraph to current chunk
            else:
                current_chunk_text.append(para)
                current_chunk_size += para_size
        
        # Add final chunk
        if current_chunk_text:
            chunk_text = '\n\n'.join(current_chunk_text)
            if len(chunk_text) >= MIN_CHUNK_SIZE:
                chunks.append(self._create_chunk(chunk_text, len(chunks), chunk_start_idx, len(paragraphs)-1))
        
        return chunks

    def _fixed_chunking(self, text: str) -> List[Chunk]:
        """
        Fixed-size chunking: Traditional character-based splitting with overlap.
        Best for: Consistent chunk sizes, simple implementation.
        
        Args:
            text: Cleaned text
            
        Returns:
            List of chunks
        """
        self.logger.info("Using fixed chunking strategy")
        
        chunks = []
        text_length = len(text)
        start = 0
        chunk_idx = 0
        
        while start < text_length:
            # Extract chunk
            end = min(start + CHUNK_SIZE, text_length)
            chunk_text = text[start:end].strip()
            
            if chunk_text and len(chunk_text) >= MIN_CHUNK_SIZE:
                chunks.append(self._create_chunk(chunk_text, chunk_idx, start, end))
                chunk_idx += 1
            
            # Move to next chunk with overlap
            start = end - CHUNK_OVERLAP
            
            # Prevent infinite loop
            if end >= text_length:
                break
        
        return chunks

    def _hybrid_chunking(self, text: str) -> List[Chunk]:
        """
        Hybrid chunking: Combines section boundaries with size constraints.
        Best for: Structured documents like SUT with section headers.
        
        Args:
            text: Cleaned text
            
        Returns:
            List of chunks
        """
        self.logger.info("Using hybrid chunking strategy")
        
        lines = text.split('\n')
        section_chunks = self._chunk_by_sections(lines)
        
        chunks = []
        for i, (chunk_text, start_line, end_line) in enumerate(section_chunks):
            chunks.append(self._create_chunk(chunk_text, i, start_line, end_line))
        
        return chunks

    def _split_large_paragraph(self, paragraph: str, para_idx: int) -> List[Chunk]:
        """
        Split a large paragraph into smaller chunks by sentences.
        
        Args:
            paragraph: Large paragraph text
            para_idx: Paragraph index
            
        Returns:
            List of chunks
        """
        # Split by sentences (Turkish sentence endings)
        sentences = re.split(r'([.!?]\s+)', paragraph)
        
        chunks = []
        current_text = []
        current_size = 0
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            separator = sentences[i+1] if i+1 < len(sentences) else ""
            sentence_full = sentence + separator
            sentence_size = len(sentence_full)
            
            if current_size + sentence_size > CHUNK_SIZE and current_text:
                chunk_text = ''.join(current_text)
                chunks.append(self._create_chunk(chunk_text, len(chunks), para_idx, para_idx))
                
                # Overlap: keep last sentence
                if CHUNK_OVERLAP > 0:
                    current_text = [current_text[-1], sentence_full]
                    current_size = len(current_text[-1]) + sentence_size
                else:
                    current_text = [sentence_full]
                    current_size = sentence_size
            else:
                current_text.append(sentence_full)
                current_size += sentence_size
        
        if current_text:
            chunk_text = ''.join(current_text)
            chunks.append(self._create_chunk(chunk_text, len(chunks), para_idx, para_idx))
        
        return chunks

    def _create_chunk(self, text: str, idx: int, start_ref: int, end_ref: int) -> Chunk:
        """
        Create a chunk object with metadata.
        
        Args:
            text: Chunk text
            idx: Chunk index
            start_ref: Start reference (line or paragraph index)
            end_ref: End reference
            
        Returns:
            Chunk object
        """
        chunk_id = f"sut_chunk_{idx:04d}"
        metadata = self._enrich_metadata(text, start_ref, end_ref)
        
        return Chunk(
            chunk_id=chunk_id,
            content=text,
            metadata=metadata,
            start_line=start_ref,
            end_line=end_ref
        )

    def _chunk_by_sections(self, lines: List[str]) -> List[tuple[str, int, int]]:
        """
        Metni madde bazlı bölümlere ayırır.

        Returns:
            List of (chunk_text, start_line, end_line)
        """
        chunks = []
        current_chunk = []
        current_start = 0
        current_length = 0

        for i, line in enumerate(lines):
            current_chunk.append(line)
            current_length += len(line)

            # Madde başı kontrolü (örn: "4.2.28")
            if self._is_section_header(line):
                # Önceki chunk'ı kaydet
                if current_chunk and i > current_start:
                    chunk_text = '\n'.join(current_chunk[:-1])  # Son satır hariç
                    if chunk_text.strip():
                        chunks.append((chunk_text, current_start, i-1))

                # Yeni chunk başlat
                current_chunk = [line]
                current_start = i
                current_length = len(line)

            # Chunk boyutu limiti
            elif current_length >= CHUNK_SIZE:
                chunk_text = '\n'.join(current_chunk)
                chunks.append((chunk_text, current_start, i))

                # Overlap için geri git
                overlap_lines = self._get_overlap_lines(current_chunk, CHUNK_OVERLAP)
                current_chunk = overlap_lines
                current_start = i - len(overlap_lines) + 1
                current_length = sum(len(line) for line in overlap_lines)

        # Son chunk'ı ekle
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append((chunk_text, current_start, len(lines)-1))

        return chunks

    def _is_section_header(self, line: str) -> bool:
        """Satırın madde başı olup olmadığını kontrol eder."""
        # Örnek: "4.2.28", "4.2.28.A", "4.2.28.C"
        pattern = r'^\d+\.\d+\.\d+(\.\w+)?'
        return bool(re.match(pattern, line.strip()))

    def _get_overlap_lines(self, lines: List[str], overlap_chars: int) -> List[str]:
        """Overlap için gerekli satırları döndürür."""
        overlap_lines = []
        total_chars = 0

        for line in reversed(lines):
            if total_chars >= overlap_chars:
                break
            overlap_lines.insert(0, line)
            total_chars += len(line)

        return overlap_lines

    def _enrich_metadata(self, chunk_text: str, start_line: int, end_line: int) -> ChunkMetadata:
        """Chunk için metadata oluşturur."""
        # Section çıkar
        section = self._extract_section(chunk_text)

        # Topic çıkar
        topic = self._extract_topic(chunk_text)

        # Etkin maddeler çıkar
        etkin_madde = self._extract_etkin_maddeler(chunk_text)

        # Keywords çıkar
        keywords = self._extract_keywords(chunk_text)

        # Drug related kontrolü
        drug_related = self._is_drug_related(chunk_text)

        # Conditions kontrolü
        has_conditions = self._has_conditions(chunk_text)

        return ChunkMetadata(
            section=section,
            topic=topic,
            etkin_madde=etkin_madde,
            keywords=keywords,
            drug_related=drug_related,
            has_conditions=has_conditions
        )

    def _extract_section(self, text: str) -> str:
        """Metinden section numarasını çıkarır."""
        lines = text.split('\n')
        for line in lines[:5]:  # İlk 5 satırda ara
            match = re.search(r'(\d+\.\d+\.\d+(?:\.\w+)?)', line.strip())
            if match:
                return match.group(1)
        return ""

    def _extract_topic(self, text: str) -> str:
        """Metinden topic çıkarır."""
        # İlk anlamlı satırı topic olarak al
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in lines[:3]:
            if len(line) > 10 and not line[0].isdigit():
                return line[:100]  # İlk 100 karakter
        return "Genel"

    def _extract_etkin_maddeler(self, text: str) -> List[str]:
        """Metinden etkin maddeleri çıkarır."""
        # Comprehensive Turkish drug patterns - optimized for single pass
        drug_patterns = [
            # Statins & lipid medications
            r'\b(ezetimib|statin|atorvastatin|rosuvastatin|simvastatin|niasin)\b',
            # Beta blockers & cardiovascular
            r'\b(metoprolol|bisoprolol|carvedilol|clopidogrel|aspirin|warfarin)\b',
            # MS medications
            r'\b(interferon|glatiramer|teriflunomid|dimetil fumarat|fingolimod|natalizumab|alemtuzumab|okrelizumab|kladribin|fampiridin)\b',
            # Pulmonary hypertension
            r'\b(iloprost|bosentan|masitentan|sildenafil|riociguat|seleksipag|tadalafil|epoprostenol|treprostinil|ambrisentan)\b',
            # Ophthalmology (Anti-VEGF)
            r'\b(bevacizumab|ranibizumab|aflibersept|deksametazon|verteporfin)\b',
            # Hormones
            r'\b(dienogest|progesteron|östrojen|östradiol|tibolon)\b',
            # Other patterns with Turkish suffixes
            r'\b(\w+mab|\w+stat|\w+pril|e?vok?umab|prokumab)\b',
        ]

        etkin_maddeler = []
        text_lower = text.lower()

        # Single pass through all patterns
        for pattern in drug_patterns:
            matches = re.findall(pattern, text_lower)
            etkin_maddeler.extend(matches)

        return list(set(etkin_maddeler))  # Remove duplicates

    def _extract_keywords(self, text: str) -> List[str]:
        """Metinden önemli anahtar kelimeleri çıkarır."""
        keywords = []

        # Tanı kodları
        diagnosis_matches = re.findall(r'\b[A-Z]\d{2}(?:\.\d+)?\b', text)
        keywords.extend(diagnosis_matches)

        # Yaş, süre gibi sayısal değerler
        age_matches = re.findall(r'\b(\d{1,3})\s*(yaş|ay|hafta|yıl)\b', text.lower())
        keywords.extend([f"{num}{unit}" for num, unit in age_matches])

        # Özel terimler
        special_terms = [
            "kardiyoloji", "iç hastalıkları", "endokrinoloji",
            "hipertansiyon", "diabet", "kolesterol",
            "uzman hekim", "raporu", "tedavi"
        ]

        text_lower = text.lower()
        for term in special_terms:
            if term in text_lower:
                keywords.append(term)

        return list(set(keywords))  # Tekrarları kaldır

    def _is_drug_related(self, text: str) -> bool:
        """Metnin ilaçla ilgili olup olmadığını kontrol eder."""
        drug_indicators = [
            "ilaç", "etkin madde", "doz", "tedavi",
            "kullanım", "reçete", "farmakolojik"
        ]

        text_lower = text.lower()
        return any(indicator in text_lower for indicator in drug_indicators)

    def _has_conditions(self, text: str) -> bool:
        """Metinde koşul ifadeleri olup olmadığını kontrol eder."""
        condition_indicators = [
            "gerekli", "şart", "koşul", "ancak",
            "yalnızca", "sadece", "mutlaka",
            "en az", "en fazla", "üstünde", "altında"
        ]

        text_lower = text.lower()
        return any(indicator in text_lower for indicator in condition_indicators)