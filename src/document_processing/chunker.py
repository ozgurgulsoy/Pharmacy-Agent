"""SUT document chunking and metadata enrichment utilities."""

import logging
import re
from typing import List, Dict, Any
from dataclasses import dataclass

from models.eligibility import Chunk, ChunkMetadata
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


class SUTDocumentChunker:
    """SUT dokümanını anlamlı parçalara bölen sınıf."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def chunk_document(self, text: str) -> List[Chunk]:
        """
        SUT dokümanını chunk'lara böler.

        Args:
            text: Ham SUT metni

        Returns:
            Chunk listesi
        """
        self.logger.info("Starting document chunking...")

        # Önce metni temizle
        cleaned_text = self._clean_text(text)

        # Satırlara böl
        lines = cleaned_text.split('\n')
        chunks = []

        # Madde bazlı chunking
        section_chunks = self._chunk_by_sections(lines)

        # Her chunk için metadata ekle
        for i, (chunk_text, start_line, end_line) in enumerate(section_chunks):
            chunk_id = f"sut_chunk_{i:04d}"

            metadata = self._enrich_metadata(chunk_text, start_line, end_line)

            chunk = Chunk(
                chunk_id=chunk_id,
                content=chunk_text,
                metadata=metadata,
                start_line=start_line,
                end_line=end_line
            )

            chunks.append(chunk)

        self.logger.info(f"Created {len(chunks)} chunks")
        return chunks

    def _clean_text(self, text: str) -> str:
        """Metni temizler ve normalize eder."""
        # Sayfa başlıklarımı kaldır
        text = re.sub(r'=== Sayfa \d+ ===', '', text)

        # Fazla boşlukları temizle
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

        return text.strip()

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