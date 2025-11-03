"""Prompt templates for LLM."""

from typing import List, Dict, Any, Optional
from app.models.report import Drug, Diagnosis, PatientInfo


# Extraction System Prompts
DRUG_EXTRACTION_SYSTEM_PROMPT = """Sen bir tıbbi rapor analizcisisin. Verilen rapor metninden ilaç bilgilerini çıkarman gerekiyor.

Her ilaç için şu bilgileri JSON formatında çıkar:
- etkin_madde: İlacın etkin maddesi
- kod: İlaç kodu
- form: İlaç formu (tablet, ampul, vb.)
- tedavi_sema: Tedavi şeması
- eklenme_zamani: Rapora eklenme tarihi (DD/MM/YYYY formatında)

Eğer bir bilgi bulunamazsa "UNKNOWN" yaz.

Çıktı formatı:
{
  "drugs": [
    {
      "etkin_madde": "string",
      "kod": "string",
      "form": "string",
      "tedavi_sema": "string",
      "eklenme_zamani": "DD/MM/YYYY veya UNKNOWN"
    }
  ]
}
"""

DIAGNOSIS_EXTRACTION_SYSTEM_PROMPT = """Sen bir tıbbi rapor analizcisisin. Verilen rapor metninden tanı bilgilerini çıkarman gerekiyor.

Her tanı için şu bilgileri JSON formatında çıkar:
- tanim: Tanı açıklaması
- icd10_code: ICD-10 tanı kodu
- baslangic: Tanı başlangıç tarihi (DD/MM/YYYY formatında)
- bitis: Tanı bitiş tarihi (DD/MM/YYYY formatında)

Eğer bir bilgi bulunamazsa "UNKNOWN" yaz.

Çıktı formatı:
{
  "diagnoses": [
    {
      "tanim": "string",
      "icd10_code": "string",
      "baslangic": "DD/MM/YYYY veya UNKNOWN",
      "bitis": "DD/MM/YYYY veya UNKNOWN"
    }
  ]
}
"""

PATIENT_EXTRACTION_SYSTEM_PROMPT = """Sen bir tıbbi rapor analizcisisin. Verilen rapor metninden hasta bilgilerini çıkarman gerekiyor.

Şu bilgileri JSON formatında çıkar:
- cinsiyet: Hastanın cinsiyeti (ERKEK/KADIN)
- dogum_tarihi: Doğum tarihi (DD/MM/YYYY formatında)
- yas: Yaş (sayı olarak)

Eğer bir bilgi bulunamazsa null kullan.

Çıktı formatı:
{
  "cinsiyet": "string veya null",
  "dogum_tarihi": "DD/MM/YYYY veya null",
  "yas": number veya null
}
"""

# Full Report Extraction Prompt
FULL_REPORT_EXTRACTION_SYSTEM_PROMPT = """Sen bir tıbbi rapor analiz uzmanısın. Aşağıdaki rapordan tüm yapısal bilgileri çıkarman gerekiyor.

Yanıtını sadece geçerli JSON olarak ver. JSON şeması:
{
  "report": {
    "id": "string veya UNKNOWN",
    "date": "DD/MM/YYYY veya UNKNOWN",
    "hospital_code": "string veya UNKNOWN"
  },
  "doctor": {
    "name": "string veya UNKNOWN",
    "specialty": "string veya UNKNOWN",
    "diploma": "string veya UNKNOWN"
  },
  "patient": {
    "cinsiyet": "ERKEK|KADIN|UNKNOWN|null",
    "dogum_tarihi": "DD/MM/YYYY veya UNKNOWN veya null",
    "yas": number veya null
  },
  "diagnoses": [
    {
      "icd10_code": "string veya UNKNOWN",
      "tanim": "string veya UNKNOWN",
      "baslangic": "DD/MM/YYYY veya UNKNOWN",
      "bitis": "DD/MM/YYYY veya UNKNOWN"
    }
  ],
  "drugs": [
    {
      "kod": "string veya UNKNOWN",
      "etkin_madde": "string",
      "form": "string veya UNKNOWN",
      "tedavi_sema": "string veya UNKNOWN",
      "miktar": number,
      "eklenme_zamani": "DD/MM/YYYY veya UNKNOWN"
    }
  ],
  "explanations": "string veya null"
}

Kurallar:
- Tarihler DD/MM/YYYY formatında olmalı. Tarih yoksa "UNKNOWN" yaz.
- Metinde bulunmayan değerler için "UNKNOWN" veya null kullan.
- Açıklamalar bölümü varsa kısa bir özet olarak "explanations" alanına yaz, yoksa null kullan.
- JSON dışında metin ekleme.
"""

# Optimized System Prompt for Speed and Token Efficiency
SYSTEM_PROMPT = """SGK/SUT uzmanısın. İlaç uygunluğunu değerlendir.

KURALLAR:
- ELIGIBLE: SUT koşulları tam karşılanmış
- CONDITIONAL: Bilgi eksik veya şüpheli, ek doğrulama gerekli
- NOT_ELIGIBLE: SUT koşulları karşılanmamış

ÖNEMLI: Yanıtı KISA ve ÖZ tut. Gereksiz tekrar yapma.

ÖNEMLİ: Yanıtın sadece geçerli JSON formatında olması gerekiyor. confidence değeri 0-1 arasında olmalı. Ek açıklama metni içerme.

JSON format:
{
  "drug_name": "ilaç adı",
  "status": "ELIGIBLE|NOT_ELIGIBLE|CONDITIONAL",
  "confidence": 0.8,
  "sut_reference": "kısa referans",
  "conditions": [
    {"description": "kısa koşul", "is_met": true|false|null, "required_info": "eksik bilgi varsa"}
  ],
  "explanation": "maksimum 2-3 cümle özet açıklama",
  "warnings": ["kısa uyarılar"]
}"""

# Eligibility Check System Prompt
ELIGIBILITY_SYSTEM_PROMPT = SYSTEM_PROMPT  # Backward compatibility


# Optimized User Prompt Template for Speed
USER_PROMPT_TEMPLATE = """💊 İLAÇ: {drug_name}
🏥 TANI: {diagnosis_name} ({icd_code})
👤 HASTA: {patient_age}y, {patient_gender}
👨‍⚕️ DOKTOR: {doctor_specialty}
{explanations}

📋 SUT KURALLARI:
{sut_chunks}

GÖREV: SGK uygunluğunu değerlendir. Yanıtı KISA tut (max 500 kelime). JSON:"""


class PromptBuilder:
    """LLM promptları oluşturan sınıf."""

    @staticmethod
    def build_eligibility_prompt(
        drug: Drug,
        diagnosis: Diagnosis,
        patient: Optional[PatientInfo],
        doctor_name: str,
        doctor_specialty: str,
        sut_chunks: List[Dict[str, Any]],
        explanations: str = None
    ) -> str:
        """
        İlaç uygunluk kontrolü için prompt oluşturur.

        Args:
            drug: İlaç bilgisi
            diagnosis: Tanı bilgisi
            patient: Hasta bilgisi
            doctor_name: Doktor adı
            doctor_specialty: Doktor branşı
            sut_chunks: İlgili SUT chunk'ları
            explanations: Rapor açıklamaları (LDL değerleri, statin kullanımı vb.)

        Returns:
            Formatted prompt
        """
        # SUT chunks'ı formatla
        sut_text = PromptBuilder._format_sut_chunks(sut_chunks, max_chunks=3, max_chars_per_chunk=350)

        # Açıklamalar kısmını ekle (varsa)
        explanations_text = ""
        if explanations:
            explanations_text = f"\nAçıklamalar: {explanations}"

        # Prompt template'i doldur
        prompt = USER_PROMPT_TEMPLATE.format(
            drug_name=drug.etkin_madde,
            diagnosis_name=diagnosis.tanim if diagnosis else "Belirtilmemiş",
            icd_code=diagnosis.icd10_code if diagnosis else "UNKNOWN",
            patient_age=patient.yas if patient and patient.yas else "Belirtilmemiş",
            patient_gender=patient.cinsiyet if patient and patient.cinsiyet else "Belirtilmemiş",
            doctor_name=doctor_name,
            doctor_specialty=doctor_specialty,
            sut_chunks=sut_text,
            explanations=explanations_text
        )

        return prompt

    @staticmethod
    def _format_sut_chunks(chunks: List[Dict[str, Any]], max_chunks: int = 3, max_chars_per_chunk: int = 350,
                          include_page_numbers: bool = True, include_confidence: bool = True) -> str:
        """SUT chunk'larını okunabilir formata çevirir.
        
        Args:
            chunks: Chunk'lar listesi
            max_chunks: Maksimum kullanılacak chunk sayısı
            max_chars_per_chunk: Chunk başına maksimum karakter sayısı
            include_page_numbers: Sayfa numaralarını dahil et
            include_confidence: Güven puanlarını dahil et
        """
        if not chunks:
            return "❌ İlgili kural bulunamadı"

        formatted_chunks = []

        for i, chunk in enumerate(chunks[:max_chunks], 1):
            metadata = chunk.get('metadata', {})
            content = metadata.get('content', '')
            section = metadata.get('section', 'Bölüm ?')
            
            # Ek bilgileri al
            chunk_parts = [f"[{i}] {section}"]
            
            # Sayfa numarası ekle
            if include_page_numbers:
                page_info = metadata.get('page_number', metadata.get('page', ''))
                if page_info:
                    chunk_parts.append(f"Sayfa: {page_info}")
            
            # Güven puanı ekle
            if include_confidence:
                confidence = metadata.get('confidence', metadata.get('score', ''))
                if confidence is not None:
                    chunk_parts.append(f"Güven: {confidence}")
            
            # İçeriği kısalt
            if len(content) > max_chars_per_chunk:
                content = content[:max_chars_per_chunk] + "..."
            
            chunk_parts.append(content)
            
            chunk_text = "\n".join(chunk_parts)
            formatted_chunks.append(chunk_text.strip())

        return "\n\n".join(formatted_chunks)

    @staticmethod
    def build_summary_prompt(eligibility_results: List[Dict[str, Any]], format_type: str = 'markdown') -> str:
        """
        Tüm ilaçlar için özet prompt oluşturur.

        Args:
            eligibility_results: İlaç uygunluk sonuçları
            format_type: 'markdown' veya 'json' formatı

        Returns:
            Formatted summary prompt
        """
        if format_type.lower() == 'json':
            # JSON formatında tutarlı şema
            summary_data = []
            
            for i, result in enumerate(eligibility_results, 1):
                drug_name = result.get('drug_name', 'Bilinmeyen ilaç')
                status = result.get('status', 'UNKNOWN')
                confidence = result.get('confidence', 0.0)
                
                summary_item = {
                    "order": i,
                    "drug_name": drug_name,
                    "status": status,
                    "confidence": confidence,
                    "eligible": status == 'ELIGIBLE',
                    "requires_review": status == 'CONDITIONAL'
                }
                
                # Sut referansı varsa ekle
                if 'sut_reference' in result:
                    summary_item["sut_reference"] = result['sut_reference']
                
                # Uyarılar varsa ekle
                if 'warnings' in result and result['warnings']:
                    summary_item["warnings"] = result['warnings']
                
                summary_data.append(summary_item)
            
            import json
            return json.dumps(summary_data, indent=2, ensure_ascii=False)
        
        else:
            # Markdown format (mevcut)
            summary = "## İLAÇ UYGUNLUK ÖZETİ\n\n"

            for i, result in enumerate(eligibility_results, 1):
                drug_name = result.get('drug_name', 'Bilinmeyen ilaç')
                status = result.get('status', 'UNKNOWN')
                confidence = result.get('confidence', 0.0)

                emoji = {
                    'ELIGIBLE': '✅',
                    'NOT_ELIGIBLE': '❌',
                    'CONDITIONAL': '⚠️'
                }.get(status, '❓')

                summary += f"{i}. {emoji} **{drug_name}** - {status} (Güven: {confidence})\n"

            return summary
