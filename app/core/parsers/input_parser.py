"""Main input parser for patient reports."""

import logging
from datetime import datetime
from typing import Optional

from app.models.report import ParsedReport, DoctorInfo, PatientInfo, Drug, Diagnosis
from app.core.llm.openai_client import OpenAIClientWrapper
from app.core.llm.prompts import FULL_REPORT_EXTRACTION_SYSTEM_PROMPT
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

        # **OPTIMIZED: Single LLM call for all structured data**
        llm_start = time.time()
        all_data = self._extract_all_with_single_llm_call(cleaned_text)
        llm_time = (time.time() - llm_start) * 1000

        report_info = all_data.get('report', {}) if isinstance(all_data, dict) else {}
        doctor_info = all_data.get('doctor', {}) if isinstance(all_data, dict) else {}
        drugs = all_data.get('drugs', []) if isinstance(all_data, dict) else []
        diagnoses = all_data.get('diagnoses', []) if isinstance(all_data, dict) else []
        patient = all_data.get('patient', PatientInfo(cinsiyet=None, dogum_tarihi=None, yas=None)) if isinstance(all_data, dict) else PatientInfo(cinsiyet=None, dogum_tarihi=None, yas=None)
        explanations = all_data.get('explanations') if isinstance(all_data, dict) else None

        report_id = report_info.get('id') if isinstance(report_info, dict) else None
        hospital_code = report_info.get('hospital_code') if isinstance(report_info, dict) else None
        report_date = self._safe_parse_date(report_info.get('date') if isinstance(report_info, dict) else None)

        doctor = self._build_doctor_info(doctor_info)

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
        if not text:
            return ""

        normalized = text.replace('\r\n', '\n').replace('\r', '\n')
        lines = [line.strip() for line in normalized.split('\n')]

        cleaned_lines = []
        previous_blank = False
        for line in lines:
            if not line:
                if not previous_blank:
                    cleaned_lines.append("")
                previous_blank = True
                continue

            parts = [segment for segment in line.split(' ') if segment]
            collapsed = ' '.join(parts)
            cleaned_lines.append(collapsed)
            previous_blank = False

        cleaned_text = '\n'.join(cleaned_lines).strip()
        return cleaned_text

    def _safe_parse_date(self, value: Optional[str]) -> Optional[datetime.date]:
        """Parse dates produced by the LLM without using regex."""
        if not value:
            return None

        value_str = str(value).strip()
        if value_str.upper() == "UNKNOWN":
            return None

        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value_str, fmt).date()
            except ValueError:
                continue
        return None

    def _build_doctor_info(self, doctor_payload: Optional[dict]) -> DoctorInfo:
        """Create DoctorInfo entity from LLM payload."""
        if not isinstance(doctor_payload, dict):
            return DoctorInfo(name="UNKNOWN", specialty="UNKNOWN", diploma="UNKNOWN")

        name = doctor_payload.get("name") or "UNKNOWN"
        specialty = doctor_payload.get("specialty") or "UNKNOWN"
        diploma = doctor_payload.get("diploma") or "UNKNOWN"

        return DoctorInfo(name=name, specialty=specialty, diploma=diploma)


    def _extract_all_with_single_llm_call(self, text: str) -> dict:
        """Single LLM call to extract full structured report data."""
        try:
            system_prompt = FULL_REPORT_EXTRACTION_SYSTEM_PROMPT
            user_prompt = (
                "Hasta raporunu analiz et ve şemaya uygun JSON döndür.\n\n" 
                "Rapor Metni:\n"
                f"{text}\n\nJSON yanıt:"
            )

            response_text = self.openai_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"}
            )

            import json
            data = json.loads(response_text)

            report_info = data.get("report", {}) or {}
            doctor_info = data.get("doctor", {}) or {}

            # Parse drugs
            drugs = []
            for drug_data in data.get("drugs", []) or []:
                eklenme_zamani = datetime.now().date()
                eklenme_value = drug_data.get("eklenme_zamani")
                if eklenme_value and eklenme_value != "UNKNOWN":
                    try:
                        day, month, year = eklenme_value.split('/')
                        eklenme_zamani = datetime(int(year), int(month), int(day)).date()
                    except Exception:
                        pass

                drug = Drug(
                    kod=drug_data.get("kod", "UNKNOWN"),
                    etkin_madde=drug_data.get("etkin_madde", "UNKNOWN"),
                    form=drug_data.get("form", "UNKNOWN"),
                    tedavi_sema=drug_data.get("tedavi_sema", "UNKNOWN"),
                    miktar=drug_data.get("miktar", 1),
                    eklenme_zamani=eklenme_zamani
                )
                drugs.append(drug)

            # Parse diagnoses
            diagnoses = []
            for diag_data in data.get("diagnoses", []) or []:
                baslangic = None
                if diag_data.get("baslangic") and diag_data["baslangic"] != "UNKNOWN":
                    try:
                        day, month, year = diag_data["baslangic"].split('/')
                        baslangic = datetime(int(year), int(month), int(day)).date()
                    except Exception:
                        pass

                bitis = None
                if diag_data.get("bitis") and diag_data["bitis"] != "UNKNOWN":
                    try:
                        day, month, year = diag_data["bitis"].split('/')
                        bitis = datetime(int(year), int(month), int(day)).date()
                    except Exception:
                        pass

                diagnosis = Diagnosis(
                    icd10_code=diag_data.get("icd10_code", "UNKNOWN"),
                    tanim=diag_data.get("tanim", "UNKNOWN"),
                    baslangic=baslangic,
                    bitis=bitis
                )
                diagnoses.append(diagnosis)

            # Parse patient info
            patient_data = data.get("patient", {}) or {}
            dogum_tarihi = None
            dogum_value = patient_data.get("dogum_tarihi")
            if dogum_value and dogum_value != "UNKNOWN":
                try:
                    day, month, year = dogum_value.split('/')
                    dogum_tarihi = datetime(int(year), int(month), int(day)).date()
                except Exception:
                    pass

            patient = PatientInfo(
                cinsiyet=patient_data.get("cinsiyet"),
                dogum_tarihi=dogum_tarihi,
                yas=patient_data.get("yas")
            )

            self.logger.info(
                "Single LLM call extracted: %s drugs, %s diagnoses",
                len(drugs),
                len(diagnoses)
            )
            return {
                'report': report_info,
                'doctor': doctor_info,
                'drugs': drugs,
                'diagnoses': diagnoses,
                'patient': patient,
                'explanations': data.get('explanations')
            }

        except Exception as e:
            self.logger.error(f"Error in combined extraction: {e}")
            self.logger.warning("Falling back to sequential extraction")
            return {
                'report': {},
                'doctor': {},
                'drugs': self.drug_extractor.extract_drugs(text),
                'diagnoses': self.diagnosis_extractor.extract_diagnoses(text),
                'patient': self.patient_extractor.extract_patient_info(text),
                'explanations': None
            }
