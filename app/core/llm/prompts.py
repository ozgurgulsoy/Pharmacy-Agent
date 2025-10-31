"""Prompt templates for LLM."""

from typing import List, Dict, Any
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

# Optimized System Prompt for Speed and Token Efficiency
SYSTEM_PROMPT = """SGK/SUT uzmanısın. İlaç uygunluğunu değerlendir.

KURALLAR:
- ELIGIBLE: SUT koşulları tam karşılanmış
- CONDITIONAL: Bilgi eksik veya şüpheli, ek doğrulama gerekli  
- NOT_ELIGIBLE: SUT koşulları karşılanmamış

ÖNEMLI: Yanıtı KISA ve ÖZ tut. Gereksiz tekrar yapma.

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
        patient: PatientInfo,
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
        sut_text = PromptBuilder._format_sut_chunks(sut_chunks)

        # Açıklamalar kısmını ekle (varsa)
        explanations_text = ""
        if explanations:
            explanations_text = f"\nAçıklamalar: {explanations}"

        # Prompt template'i doldur
        prompt = USER_PROMPT_TEMPLATE.format(
            drug_name=drug.etkin_madde,
            drug_code=drug.kod,
            drug_form=drug.form,
            drug_schema=drug.tedavi_sema,
            diagnosis_name=diagnosis.tanim if diagnosis else "Belirtilmemiş",
            icd_code=diagnosis.icd10_code if diagnosis else "UNKNOWN",
            patient_age=patient.yas if patient.yas else "Belirtilmemiş",
            patient_gender=patient.cinsiyet if patient.cinsiyet else "Belirtilmemiş",
            doctor_name=doctor_name,
            doctor_specialty=doctor_specialty,
            sut_chunks=sut_text,
            explanations=explanations_text
        )

        return prompt

    @staticmethod
    def _format_sut_chunks(chunks: List[Dict[str, Any]]) -> str:
        """SUT chunk'larını okunabilir formata çevirir."""
        if not chunks:
            return "❌ İlgili kural bulunamadı"

        formatted_chunks = []

        for i, chunk in enumerate(chunks[:3], 1):  # Top 3 only for speed
            metadata = chunk.get('metadata', {})
            content = metadata.get('content', '')
            section = metadata.get('section', 'Bölüm ?')

            # Shorten aggressively for speed - max 350 chars per chunk
            if len(content) > 350:
                content = content[:350] + "..."

            chunk_text = f"[{i}] {section}\n{content}"
            formatted_chunks.append(chunk_text.strip())

        return "\n\n".join(formatted_chunks)

    @staticmethod
    def build_summary_prompt(eligibility_results: List[Dict[str, Any]]) -> str:
        """
        Tüm ilaçlar için özet prompt oluşturur.

        Args:
            eligibility_results: İlaç uygunluk sonuçları

        Returns:
            Summary prompt
        """
        # Bu fonksiyon gelecekte CLI output için kullanılabilir
        summary = "## İLAÇ UYGUNLUK ÖZETİ\n\n"

        for i, result in enumerate(eligibility_results, 1):
            drug_name = result.get('drug_name', 'Bilinmeyen ilaç')
            status = result.get('status', 'UNKNOWN')

            emoji = {
                'ELIGIBLE': '✅',
                'NOT_ELIGIBLE': '❌',
                'CONDITIONAL': '⚠️'
            }.get(status, '❓')

            summary += f"{i}. {emoji} **{drug_name}** - {status}\n"

        return summary
