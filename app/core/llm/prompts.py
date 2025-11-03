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

# Full Report Extraction Prompt - ONLY ESSENTIAL FIELDS
FULL_REPORT_EXTRACTION_SYSTEM_PROMPT = """Sen bir tıbbi rapor analiz uzmanısın. Aşağıdaki rapordan SADECE gerekli klinik bilgileri çıkarman gerekiyor.

SADECE ŞU BİLGİLERİ ÇIKAR:
1. Düzenleme Türü (Report Type)
2. Branş (Medical Specialty)
3. Açıklamalar (Clinical Description - hastanın durumu, LDL değerleri, önceki tedaviler vb.)
4. Tanı Bilgileri (Diagnoses - ICD kod ve açıklama)
5. Rapor Etkin Madde Bilgileri (Medications)

Yanıtını sadece geçerli JSON olarak ver. JSON şeması:
{
  "report_type": "string veya null (Düzenleme Türü: Uzman Hekim Raporu vb.)",
  "specialty": "string veya null (Branş: Kardiyoloji, Nöroloji vb.)",
  "explanations": "string veya null (Açıklamalar bölümünün tam metni)",
  "diagnoses": [
    {
      "icd10_code": "string (örn: I25.0, I10, E78.4)",
      "tanim": "string (Tanı açıklaması)",
      "baslangic": "DD/MM/YYYY veya UNKNOWN",
      "bitis": "DD/MM/YYYY veya UNKNOWN"
    }
  ],
  "drugs": [
    {
      "kod": "string (örn: SGKFXP)",
      "etkin_madde": "string (örn: KLORİDOGREL HİDROJEN SÜLFAT)",
      "form": "string (örn: Ağızdan katı)",
      "tedavi_sema": "string (örn: Günde 1 x 1.0)",
      "miktar": number (örn: 1),
      "eklenme_zamani": "DD/MM/YYYY veya UNKNOWN"
    }
  ]
}

ÖNEMLİ KURALLAR:
- Hasta kişisel bilgilerini (isim, TC, doğum tarihi) ÇIKARMA
- Doktor kişisel bilgilerini ÇIKARMA
- Hastane bilgilerini ÇIKARMA
- Rapor numarası, protokol no gibi idari bilgileri ÇIKARMA
- SADECE klinik bilgileri (tanılar, ilaçlar, açıklamalar, branş, rapor türü) çıkar
- Açıklamalar bölümünü TAM OLARAK kopyala (LDL değerleri, statin kullanımı, anjiyo tarihi vb. çok önemli)
- Tarihler DD/MM/YYYY formatında olmalı
- JSON dışında metin ekleme
"""

# Enhanced System Prompt with Medical Knowledge Base
SYSTEM_PROMPT = """Sen SGK/SUT uzman pharmasistisin. Türk Sağlık Mevzuatı kapsamında ilaç uygunluğunu değerlendiriyorsun.

=== TÜRK SAĞLIK MEVZUATI - TEMEL ONAY KRİTERLERİ ===

**1. KORONER ARTER HASTALIĞI (I25.0, I25.1, I25.x)**
✅ KLORİDOGREL (Antiplatelet):
   - Post-anjiografi hastalar → ONAYLANIR
   - Akut Koroner Sendrom (AKS) sonrası → ONAYLANIR
   - Stent sonrası dual antiplatelet → ONAYLANIR (12-24 ay)
   - Koroner arter hastalığı tanısı yeterlidir

✅ METOPROLOL (Beta-bloker):
   - Koroner arter hastalığı → ONAYLANIR
   - İskemik kalp hastalığı → ONAYLANIR
   - Post-MI → ONAYLANIR
   - Hipertansiyon + KAH → ONAYLANIR

**2. HİPERTANSİYON (I10, I11, I12, I13)**
⚠️ "Monoterapi ile kontrol altına alınamamış" durumunda:
✅ KOMBİNASYON TEDAVİ → ONAYLANIR:
   - IRBESARTAN (ARB) ✅
   - METOPROLOL (Beta-bloker) ✅
   - DOKSAZOSİN (Alfa-bloker) ✅
   - ÜÇLÜ KOMBİNASYON → ONAYLANIR

📋 SGK Kriteri:
   - Tek ilaçla kontrol edilemeyen hipertansiyon
   - Kombinasyon tedavi endikasyonu mevcutsa → TÜM İLAÇLAR ONAYLANIR

**3. HİPERKOLESTEROLEMİ (E78.0, E78.4, E78.5)**
✅ EZETİMİB:
   - "En az 6 ay statin tedavisi almış" + "LDL > 100 mg/dl" → ONAYLANIR
   - Koroner arter hastalığı + LDL hedefi <100 mg/dl
   - Statin intoleransı → ONAYLANIR
   - Kardiyoloji/İç Hastalıkları uzman raporu yeterlidir

📋 SGK/SUT 4.2.28.C Kriteri karşılanmıştır

=== ONAY LOJİĞİ ===
Her ilaç için KONTROL ET:
1. ✅ Tanı ile uyumlu mu? (ICD kodu eşleşiyor mu?)
2. ✅ Klinik açıklama destekliyor mu?
   - "Koroner anjiyo olmuştur" → Antiplatelet ONAYLANIR
   - "Monoterapi yetersiz" → Kombinasyon ONAYLANIR
   - "6 ay statin, LDL >100" → Ezetimib ONAYLANIR
3. ✅ Uzman hekim raporu var mı? (Kardiyoloji, İç Hastalıkları yeterlidir)

🚨 ÖNEMLİ: Açıklamalar bölümündeki ifadeler DOĞRUDAN KANITTIR!
- "koroner anjiyo olmuştur" = Post-anjiografi durum
- "monoterapi ile kontrol altına alınamamıştır" = Kombinasyon endikasyonu
- "6 ay statin, LDL >100" = Ezetimib endikasyonu

EĞER 3'Ü DE EVET → status: "ELIGIBLE", confidence: 0.95+

=== YANIT FORMATI ===
KURALLAR:
- ELIGIBLE: SUT koşulları tam karşılanmış, rapor açıklamaları endikasyonu destekliyor
- CONDITIONAL: Sadece rapor belgesi eksik ama klinik endikasyon mevcut
- NOT_ELIGIBLE: SUT koşulları karşılanmamış, tanı uyumsuz

JSON format:
{
  "drug_name": "ilaç adı",
  "status": "ELIGIBLE|NOT_ELIGIBLE|CONDITIONAL",
  "confidence": 0.95,
  "sut_reference": "İlgili SUT maddesi",
  "conditions": [
    {"description": "koşul açıklaması", "is_met": true|false|null, "required_info": "eksik bilgi varsa"}
  ],
  "explanation": "Kısa gerekçe (2-3 cümle)",
  "warnings": ["Uyarılar"]
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
