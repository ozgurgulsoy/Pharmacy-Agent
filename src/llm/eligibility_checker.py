"""Main eligibility checker using LLM."""

import logging
from typing import List, Dict, Any

from models.report import Drug, Diagnosis, PatientInfo, DoctorInfo
from models.eligibility import EligibilityResult, Condition
from .openai_client import OpenAIClientWrapper
from .prompts import PromptBuilder, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class EligibilityChecker:
    """LLM kullanarak ilaç uygunluğunu kontrol eden sınıf."""

    def __init__(self, openai_client: OpenAIClientWrapper):
        self.client = openai_client
        self.prompt_builder = PromptBuilder()
        self.logger = logging.getLogger(self.__class__.__name__)

    def check_eligibility(
        self,
        drug: Drug,
        diagnosis: Diagnosis,
        patient: PatientInfo,
        doctor: DoctorInfo,
        sut_chunks: List[Dict[str, Any]],
        explanations: str = None
    ) -> EligibilityResult:
        """
        Bir ilaç için SGK uygunluğunu kontrol eder.

        Args:
            drug: İlaç bilgisi
            diagnosis: Tanı bilgisi
            patient: Hasta bilgisi
            doctor: Doktor bilgisi
            sut_chunks: İlgili SUT chunk'ları
            explanations: Rapor açıklamaları

        Returns:
            EligibilityResult
        """
        self.logger.info(f"Checking eligibility for: {drug.etkin_madde}")

        # Prompt oluştur
        user_prompt = self.prompt_builder.build_eligibility_prompt(
            drug=drug,
            diagnosis=diagnosis,
            patient=patient,
            doctor_name=doctor.name,
            doctor_specialty=doctor.specialty,
            sut_chunks=sut_chunks,
            explanations=explanations
        )

        # LLM'den yanıt al
        try:
            response_json = self.client.chat_completion_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt
            )

            # JSON'dan EligibilityResult oluştur
            result = self._parse_response(response_json, drug.etkin_madde)
            
            self.logger.info(f"Eligibility check complete: {result.status}")
            return result

        except Exception as e:
            self.logger.error(f"Eligibility check failed: {e}")
            # Hata durumunda varsayılan sonuç
            return self._create_fallback_result(drug.etkin_madde, str(e))

    def check_multiple_drugs(
        self,
        drugs: List[Drug],
        diagnoses: List[Diagnosis],
        patient: PatientInfo,
        doctor: DoctorInfo,
        sut_chunks_per_drug: Dict[str, List[Dict[str, Any]]],
        explanations: str = None
    ) -> List[EligibilityResult]:
        """
        Birden fazla ilaç için uygunluk kontrolü.

        Args:
            drugs: İlaç listesi
            diagnoses: Tanı listesi
            patient: Hasta bilgisi
            doctor: Doktor bilgisi
            sut_chunks_per_drug: Her ilaç için SUT chunks
            explanations: Rapor açıklamaları

        Returns:
            EligibilityResult listesi
        """
        results = []
        
        # Ana tanıyı al (genellikle ilk tanı)
        primary_diagnosis = diagnoses[0] if diagnoses else Diagnosis(
            icd10_code="UNKNOWN",
            tanim="Tanı belirtilmemiş"
        )

        for drug in drugs:
            sut_chunks = sut_chunks_per_drug.get(drug.etkin_madde, [])
            
            result = self.check_eligibility(
                drug=drug,
                diagnosis=primary_diagnosis,
                patient=patient,
                doctor=doctor,
                sut_chunks=sut_chunks,
                explanations=explanations
            )
            
            results.append(result)

        return results

    def _parse_response(self, response_json: Dict[str, Any], drug_name: str) -> EligibilityResult:
        """LLM JSON yanıtını EligibilityResult'a çevirir."""
        try:
            # Conditions listesini parse et
            conditions = []
            for cond_data in response_json.get('conditions', []):
                condition = Condition(
                    description=cond_data.get('description', ''),
                    is_met=cond_data.get('is_met'),
                    required_info=cond_data.get('required_info', '')
                )
                conditions.append(condition)

            # EligibilityResult oluştur
            result = EligibilityResult(
                drug_name=response_json.get('drug_name', drug_name),
                status=response_json.get('status', 'CONDITIONAL'),
                confidence=float(response_json.get('confidence', 0.5)),
                sut_reference=response_json.get('sut_reference', 'Referans bulunamadı'),
                conditions=conditions,
                explanation=response_json.get('explanation', ''),
                warnings=response_json.get('warnings', [])
            )

            return result

        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            return self._create_fallback_result(drug_name, f"Parse error: {e}")

    def _create_fallback_result(self, drug_name: str, error_msg: str) -> EligibilityResult:
        """Hata durumunda fallback sonuç oluşturur."""
        return EligibilityResult(
            drug_name=drug_name,
            status="CONDITIONAL",
            confidence=0.0,
            sut_reference="Hata nedeniyle belirlenemedi",
            conditions=[
                Condition(
                    description="Sistem hatası oluştu",
                    is_met=None,
                    required_info="Manuel kontrol gerekli"
                )
            ],
            explanation=f"⚠️ İlaç uygunluğu kontrol edilemedi. Hata: {error_msg}\n\n"
                       f"Lütfen SUT dokümanını manuel olarak kontrol edin veya "
                       f"doktorla görüşün.",
            warnings=[
                "Sistem hatası nedeniyle otomatik kontrol yapılamadı",
                "Manuel SUT kontrolü şarttır"
            ]
        )
