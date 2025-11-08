"""SUT document chunking and metadata enrichment utilities.

This module implements multiple chunking strategies:
1. Semantic Chunking: Preserves paragraphs and logical structure
2. Fixed Chunking: Traditional size-based splitting with overlap
3. Hybrid Chunking: Combines semantic boundaries with size limits
"""

import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from app.models.eligibility import Chunk, ChunkMetadata
from app.config.settings import (
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

    def __init__(self, strategy: str = CHUNKING_STRATEGY, doc_type: str = "SUT", doc_source: str = "9.5.17229.pdf"):
        """
        Initialize the chunker.
        
        Args:
            strategy: Chunking strategy ("semantic", "fixed", or "hybrid")
            doc_type: Document type identifier (e.g., "SUT", "EK-4/D")
            doc_source: Source filename for metadata
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.strategy = strategy
        self.doc_type = doc_type
        self.doc_source = doc_source
        self.logger.info(f"Initialized chunker with strategy: {strategy}, doc_type: {doc_type}")

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
        if not text:
            return ""

        normalized = text.replace('\r\n', '\n').replace('\r', '\n')
        cleaned_lines: List[str] = []
        previous_blank = False

        for raw_line in normalized.split('\n'):
            stripped = raw_line.strip()

            # Sayfa başlıklarını kaldır ("=== Sayfa 12 ===")
            if stripped.startswith("=== Sayfa") and stripped.endswith("==="):
                middle = stripped[8:-3].strip()
                middle_digits = middle.replace("Sayfa", "").strip()
                if middle_digits.replace(' ', '').isdigit():
                    continue

            if not stripped:
                if not previous_blank:
                    cleaned_lines.append("")
                previous_blank = True
                continue

            cleaned_lines.append(stripped)
            previous_blank = False

        cleaned_text = '\n'.join(cleaned_lines).strip()
        return cleaned_text

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
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
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
        sentences = self._split_sentences(paragraph)

        chunks = []
        current_text: List[str] = []
        current_size = 0

        for sentence_text in sentences:
            sentence_size = len(sentence_text)

            if current_size + sentence_size > CHUNK_SIZE and current_text:
                chunk_text = ' '.join(current_text).strip()
                if chunk_text:
                    chunks.append(self._create_chunk(chunk_text, len(chunks), para_idx, para_idx))

                if CHUNK_OVERLAP > 0 and current_text:
                    last_sentence = current_text[-1]
                    current_text = [last_sentence, sentence_text]
                    current_size = len(' '.join(current_text))
                else:
                    current_text = [sentence_text]
                    current_size = sentence_size
            else:
                current_text.append(sentence_text)
                current_size += sentence_size

        if current_text:
            chunk_text = ' '.join(current_text).strip()
            if chunk_text:
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
        # Create chunk ID with document type prefix
        doc_prefix = self.doc_type.lower().replace("/", "_").replace("-", "_")
        chunk_id = f"{doc_prefix}_chunk_{idx:04d}"
        
        metadata = self._enrich_metadata(text, start_ref, end_ref)
        # Add document source metadata
        metadata.doc_type = self.doc_type
        metadata.doc_source = self.doc_source
        
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
        return bool(self._normalize_section_token(line.strip()))

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

    def _normalize_section_token(self, text: str) -> str:
        """Satırdaki ilk section benzeri token'ı normalize eder."""
        if not text:
            return ""

        first_token = text.strip().split()[0].rstrip(':;,')
        if not first_token:
            return ""

        parts = first_token.split('.')
        if len(parts) < 3:
            return ""

        numeric_parts = parts[:3]
        if not all(part.isdigit() for part in numeric_parts):
            return ""

        remainder = parts[3:]
        if remainder and not all(segment.isalnum() for segment in remainder):
            return ""

        normalized = '.'.join(numeric_parts)
        if remainder:
            normalized += '.' + '.'.join(remainder)
        return normalized

    def _split_sentences(self, paragraph: str) -> List[str]:
        """Basit cümle bölme yardımcı metodu."""
        sentences: List[str] = []
        start = 0
        length = len(paragraph)

        for idx, char in enumerate(paragraph):
            if char in '.?!':
                next_idx = idx + 1
                while next_idx < length and paragraph[next_idx] in ' \t\n\r':
                    next_idx += 1
                sentence = paragraph[start:next_idx].strip()
                if sentence:
                    sentences.append(sentence)
                start = next_idx

        if start < length:
            tail = paragraph[start:].strip()
            if tail:
                sentences.append(tail)

        return sentences if sentences else [paragraph.strip()]

    def _tokenize_lower(self, text: str) -> List[str]:
        """Metni küçük harfli token'lara böler."""
        tokens: List[str] = []
        current: List[str] = []
        for char in text.lower():
            if char.isalnum() or char in ['ç', 'ğ', 'ı', 'ö', 'ş', 'ü']:
                current.append(char)
            else:
                if current:
                    tokens.append(''.join(current))
                    current = []
        if current:
            tokens.append(''.join(current))
        return tokens

    def _tokenize_preserve(self, text: str) -> List[str]:
        """Metni noktalama işaretlerini koruyarak token'lara böler."""
        tokens: List[str] = []
        current: List[str] = []
        for char in text:
            if char.isalnum() or char in ['.', '-', '_']:
                current.append(char)
            else:
                if current:
                    tokens.append(''.join(current))
                    current = []
        if current:
            tokens.append(''.join(current))
        return tokens

    def _looks_like_icd_code(self, token: str) -> bool:
        """Basit kontrollerle ICD koduna benzerliği denetler."""
        if len(token) < 3:
            return False
        first = token[0]
        if not first.isalpha() or not first.isupper():
            return False

        idx = 1
        digits = []
        while idx < len(token) and token[idx].isdigit():
            digits.append(token[idx])
            idx += 1

        if len(digits) < 2:
            return False

        if idx == len(token):
            return True

        if token[idx] != '.':
            return False

        decimal_part = token[idx + 1:]
        return decimal_part.isdigit() and len(decimal_part) > 0

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
            token = self._normalize_section_token(line.strip())
            if token:
                return token
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
        base_terms = {
            "ezetimib", "statin", "atorvastatin", "rosuvastatin", "simvastatin", "niasin",
            "metoprolol", "bisoprolol", "carvedilol", "clopidogrel", "aspirin", "warfarin",
            "interferon", "glatiramer", "teriflunomid", "dimetil", "fumarat", "fingolimod",
            "natalizumab", "alemtuzumab", "okrelizumab", "kladribin", "fampiridin",
            "iloprost", "bosentan", "masitentan", "sildenafil", "riociguat", "seleksipag",
            "tadalafil", "epoprostenol", "treprostinil", "ambrisentan",
            "bevacizumab", "ranibizumab", "aflibersept", "deksametazon", "verteporfin",
            "dienogest", "progesteron", "östrojen", "östradiol", "tibolon",
            "evokumab", "prokumab"
        }

        suffixes = ("mab", "stat", "pril")

        tokens = self._tokenize_lower(text)
        etkin_maddeler: Dict[str, None] = {}

        for token in tokens:
            if token in base_terms:
                etkin_maddeler[token] = None
                continue

            for suffix in suffixes:
                if token.endswith(suffix) and len(token) > len(suffix) + 1:
                    etkin_maddeler[token] = None
                    break

        return list(etkin_maddeler.keys())

    def _extract_keywords(self, text: str) -> List[str]:
        """Metinden önemli anahtar kelimeleri çıkarır."""
        keywords = []

        tokens_preserve = self._tokenize_preserve(text)

        # Tanı kodları (ICD-10 benzeri)
        for token in tokens_preserve:
            candidate = token.strip(',.')
            if self._looks_like_icd_code(candidate):
                keywords.append(candidate)

        # Yaş, süre gibi sayısal değerler
        words = self._tokenize_lower(text)
        units = {"yaş", "ay", "hafta", "yıl"}
        for idx in range(len(words) - 1):
            if words[idx].isdigit() and words[idx + 1] in units:
                keywords.append(f"{words[idx]}{words[idx + 1]}")

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
