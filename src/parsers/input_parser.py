"""Main input parser for patient reports."""

import logging
import re
from datetime import datetime
from typing import Optional

from models.report import ParsedReport, DoctorInfo, PatientInfo
from llm.openai_client import OpenAIClientWrapper
from .drug_extractor import DrugExtractor
from .diagnosis_extractor import DiagnosisExtractor
from .patient_extractor import PatientInfoExtractor

logger = logging.getLogger(__name__)


class InputParser:
    """Ham rapor metnini parse eden ana sınıf."""

    def __init__(self, openai_client: OpenAIClientWrapper = None):
        self.openai_client = openai_client or OpenAIClientWrapper()
        self.drug_extractor = DrugExtractor(self.openai_client)
        self.diagnosis_extractor = DiagnosisExtractor(self.openai_client)
        self.patient_extractor = PatientInfoExtractor(self.openai_client)
        self.logger = logging.getLogger(self.__class__.__name__)

    def parse_report(self, raw_text: str) -> ParsedReport:
        """
        Ham rapor metnini parse eder.

        Args:
            raw_text: Eczacının yapıştırdığı ham rapor metni

        Returns:
            ParsedReport objesi

        Raises:
            ValueError: Rapor geçersiz veya parse edilemezse
        """
        if not self.validate_input(raw_text):
            raise ValueError("Geçersiz rapor formatı")

        import time
        self.logger.info("Parsing report...")

        total_start = time.time()

        # Metni temizle
        cleaned_text = self.clean_text(raw_text)

        # Rapor ID ve tarih çıkar (regex - hızlı)
        report_id = self._extract_report_id(cleaned_text)
        report_date = self._extract_report_date(cleaned_text)
        hospital_code = self._extract_hospital_code(cleaned_text)

        # Doktor bilgilerini çıkar (regex - hızlı)
        doctor = self._extract_doctor_info(cleaned_text)

        # **OPTIMIZED: Single LLM call for all structured data**
        llm_start = time.time()
        all_data = self._extract_all_with_single_llm_call(cleaned_text)
        llm_time = (time.time() - llm_start) * 1000

        drugs = all_data.get('drugs', [])
        diagnoses = all_data.get('diagnoses', [])
        patient = all_data.get('patient', PatientInfo(cinsiyet=None, dogum_tarihi=None, yas=None))

        # Rapor açıklamalarını çıkar (LDL, statin kullanımı vb.)
        explanations = self._extract_explanations(cleaned_text)

        total_time = (time.time() - total_start) * 1000
        self.logger.info(f"Parsing complete: total={total_time:.1f}ms, llm_extract={llm_time:.1f}ms")
        if total_time > 5000:
            self.logger.warning(f"⚠️ Parsing took {total_time/1000:.1f}s - investigate slow extractors or large LLM latency")

        parsed_report = ParsedReport(
            report_id=report_id or "UNKNOWN",
            date=report_date or datetime.now().date(),
            hospital_code=hospital_code or "UNKNOWN",
            doctor=doctor,
            diagnoses=diagnoses,
            drugs=drugs,
            patient=patient,
            raw_text=cleaned_text,
            explanations=explanations
        )

        self.logger.info(f"Parsed report: {len(drugs)} drugs, {len(diagnoses)} diagnoses")
        return parsed_report

    def validate_input(self, raw_text: str) -> bool:
        """
        Rapor metninin geçerli olup olmadığını kontrol eder.

        Args:
            raw_text: Ham metin

        Returns:
            True if valid
        """
        if not raw_text or len(raw_text.strip()) < 50:
            return False

        # En az bir ilaç veya tanı bilgisi olmalı
        has_drug_info = any(keyword in raw_text.lower() 
                           for keyword in ["etkin madde", "sgk", "ilaç", "rapor"])
        
        return has_drug_info

    def clean_text(self, text: str) -> str:
        """
        Metni temizler ve normalize eder.

        Args:
            text: Ham metin

        Returns:
            Temizlenmiş metin
        """
        # Fazla boşlukları temizle
        text = re.sub(r'\s+', ' ', text)
        
        # Satır başı/sonu boşlukları kaldır
        text = '\n'.join(line.strip() for line in text.split('\n'))
        
        # Fazla satır atlamalarını temizle
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        
        return text.strip()

    def _extract_report_id(self, text: str) -> Optional[str]:
        """Rapor numarasını çıkarır."""
        patterns = [
            r'Rapor\s*(?:No|Numarası|ID)\s*:?\s*(\d+)',
            r'(?:Rapor|Report)\s*(?:#|No\.?)\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    def _extract_report_date(self, text: str) -> Optional[datetime.date]:
        """Rapor tarihini çıkarır."""
        # DD/MM/YYYY formatı
        pattern = r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})'
        match = re.search(pattern, text)
        
        if match:
            day, month, year = match.groups()
            try:
                return datetime(int(year), int(month), int(day)).date()
            except ValueError:
                pass
        
        return None

    def _extract_hospital_code(self, text: str) -> Optional[str]:
        """Hastane/tesis kodunu çıkarır."""
        patterns = [
            r'Tesis\s*Kodu?\s*:?\s*(\d+)',
            r'Hastane\s*Kodu?\s*:?\s*(\d+)',
            r'Kurum\s*Kodu?\s*:?\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    def _extract_doctor_info(self, text: str) -> DoctorInfo:
        """Doktor bilgilerini çıkarır."""
        # Doktor adı
        name_patterns = [
            r'(?:Dr\.?|Doktor)\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)+)',
            r'Hekim\s*:?\s*([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)+)',
        ]
        
        name = None
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                break

        # Branş
        specialty_patterns = [
            r'Branş\s*:?\s*([A-ZÇĞİÖŞÜa-zçğıöşü\s]+)',
            r'Uzmanlık\s*:?\s*([A-ZÇĞİÖŞÜa-zçğıöşü\s]+)',
        ]
        
        specialty = None
        for pattern in specialty_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                specialty = match.group(1).strip()
                # İlk satırı al (eğer çok uzunsa)
                specialty = specialty.split('\n')[0][:50]
                break

        # Diploma no
        diploma_pattern = r'Diploma\s*(?:No|Numarası)\s*:?\s*(\d+)'
        diploma_match = re.search(diploma_pattern, text, re.IGNORECASE)
        diploma = diploma_match.group(1) if diploma_match else "UNKNOWN"

        return DoctorInfo(
            name=name or "UNKNOWN",
            specialty=specialty or "UNKNOWN",
            diploma=diploma
        )

    def _extract_explanations(self, text: str) -> Optional[str]:
        """
        Rapordaki açıklamalar bölümünü çıkarır.
        Bu bölümde genellikle LDL değerleri, statin kullanımı, anjiyo tarihleri vb. önemli bilgiler yer alır.
        """
        # "Açıklamalar" veya "Explanations" bölümünü bul
        patterns = [
            r'Açıklamalar?\s*(?:\(Explanations\))?\s*:?\s*\n(.+?)(?=\n\n[A-Z]|\nTanı Bilgileri|\nDoktor Bilgileri|\nRapor Etkin Madde|\Z)',
            r'(?:Rapor\s+)?Açıklama\s*:?\s*(.+?)(?=\n\n[A-Z]|\nTanı Bilgileri|\Z)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                explanations = match.group(1).strip()
                # Çok uzunsa kısalt (ilk 2000 karakter)
                if len(explanations) > 2000:
                    explanations = explanations[:2000] + "..."
                return explanations
        
        return None

    def _extract_all_with_single_llm_call(self, text: str) -> dict:
        """
        OPTIMIZED: Single LLM call to extract drugs, diagnoses, and patient info.
        This reduces 3 sequential LLM calls to 1, cutting parse time by ~66%.
        
        Returns:
            {
                'drugs': List[Drug],
                'diagnoses': List[Diagnosis], 
                'patient': PatientInfo
            }
        """
        try:
            system_prompt = """Sen bir tıbbi rapor analiz asistanısın. Rapor metninden tüm bilgileri TEK SEFERDE çıkar.

JSON formatında döndür:
{
  "drugs": [
    {
      "kod": "SGKF09",
      "etkin_madde": "KLOPİDOGREL HİDROJEN SÜLFAT",
      "form": "Ağızdan katı",
      "tedavi_sema": "Günde 1 x 1.0 Adet",
      "miktar": 1,
      "eklenme_zamani": "26/12/2024"
    }
  ],
  "diagnoses": [
    {
      "icd10_code": "I25.1",
      "tanim": "ATEROSKLEROTİK KALP HASTALIĞI",
      "baslangic": "26/12/2024",
      "bitis": "25/12/2025"
    }
  ],
  "patient": {
    "cinsiyet": "Erkek",
    "dogum_tarihi": "12/04/1954",
    "yas": 71
  }
}

ÖNEMLİ: TC Kimlik numarası gibi kişisel bilgileri ÇIKARMA!
Eksik bilgiler için "UNKNOWN" veya null kullan."""

            user_prompt = f"""Aşağıdaki rapor metninden TÜM bilgileri çıkar:

{text}

Sadece JSON formatında yanıt ver."""

            response_text = self.openai_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"}
            )

            import json
            data = json.loads(response_text)
            
            # Parse drugs
            drugs = []
            for drug_data in data.get("drugs", []):
                eklenme_zamani = datetime.now().date()
                if drug_data.get("eklenme_zamani") and drug_data["eklenme_zamani"] != "UNKNOWN":
                    try:
                        day, month, year = drug_data["eklenme_zamani"].split('/')
                        eklenme_zamani = datetime(int(year), int(month), int(day)).date()
                    except:
                        pass

                from models.report import Drug
                drug = Drug(
                    kod=drug_data.get("kod", "UNKNOWN"),
                    etkin_madde=drug_data.get("etkin_madde", "UNKNOWN"),
                    form=drug_data.get("form", "Ağızdan katı"),
                    tedavi_sema=drug_data.get("tedavi_sema", "Günde 1 x 1"),
                    miktar=drug_data.get("miktar", 1),
                    eklenme_zamani=eklenme_zamani
                )
                drugs.append(drug)

            # Parse diagnoses
            diagnoses = []
            for diag_data in data.get("diagnoses", []):
                baslangic = None
                bitis = None
                
                if diag_data.get("baslangic") and diag_data["baslangic"] != "UNKNOWN":
                    try:
                        day, month, year = diag_data["baslangic"].split('/')
                        baslangic = datetime(int(year), int(month), int(day)).date()
                    except:
                        pass
                
                if diag_data.get("bitis") and diag_data["bitis"] != "UNKNOWN":
                    try:
                        day, month, year = diag_data["bitis"].split('/')
                        bitis = datetime(int(year), int(month), int(day)).date()
                    except:
                        pass

                from models.report import Diagnosis
                diagnosis = Diagnosis(
                    icd10_code=diag_data.get("icd10_code", "UNKNOWN"),
                    tanim=diag_data.get("tanim", "UNKNOWN"),
                    baslangic=baslangic,
                    bitis=bitis
                )
                diagnoses.append(diagnosis)

            # Parse patient info
            patient_data = data.get("patient", {})
            dogum_tarihi = None
            if patient_data.get("dogum_tarihi"):
                try:
                    day, month, year = patient_data["dogum_tarihi"].split('/')
                    dogum_tarihi = datetime(int(year), int(month), int(day)).date()
                except:
                    pass

            patient = PatientInfo(
                cinsiyet=patient_data.get("cinsiyet"),
                dogum_tarihi=dogum_tarihi,
                yas=patient_data.get("yas")
            )

            self.logger.info(f"Single LLM call extracted: {len(drugs)} drugs, {len(diagnoses)} diagnoses")
            return {
                'drugs': drugs,
                'diagnoses': diagnoses,
                'patient': patient
            }

        except Exception as e:
            self.logger.error(f"Error in combined extraction: {e}")
            # Fallback to old method
            self.logger.warning("Falling back to sequential extraction")
            return {
                'drugs': self.drug_extractor.extract_drugs(text),
                'diagnoses': self.diagnosis_extractor.extract_diagnoses(text),
                'patient': self.patient_extractor.extract_patient_info(text)
            }

