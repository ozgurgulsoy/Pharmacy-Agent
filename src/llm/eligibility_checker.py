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
        
        OPTIMIZED: Uses a single batched LLM call instead of sequential calls.
        This reduces N sequential LLM calls to 1, dramatically improving performance.

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
        if not drugs:
            return []

        # Ana tanıyı al (genellikle ilk tanı)
        primary_diagnosis = diagnoses[0] if diagnoses else Diagnosis(
            icd10_code="UNKNOWN",
            tanim="Tanı belirtilmemiş"
        )

        # Try batched processing first; on failure, fall back to sequential with detailed logging
        import time
        batch_start = time.time()
        self.logger.info(f"🔍 Starting eligibility check for {len(drugs)} drugs (batched attempt)")

        try:
            self.logger.info(f"🚀 Attempting batched LLM call for all {len(drugs)} drugs")
            results = self._check_all_drugs_batched(
                drugs=drugs,
                diagnosis=primary_diagnosis,
                patient=patient,
                doctor=doctor,
                sut_chunks_per_drug=sut_chunks_per_drug,
                explanations=explanations
            )

            batch_elapsed = time.time() - batch_start
            try:
                avg_ms = (batch_elapsed * 1000) / len(drugs)
            except Exception:
                avg_ms = batch_elapsed * 1000

            self.logger.info(f"✅ Batched check succeeded in {batch_elapsed:.2f}s (avg {avg_ms:.1f}ms/drug)")
            return results

        except Exception as e:
            self.logger.error(f"❌ Batched LLM call failed: {type(e).__name__}: {e}")
            self.logger.exception("Batched eligibility failure stacktrace")
            self.logger.warning("⚠️ Falling back to sequential processing for each drug")

            # Sequential fallback (kept for robustness) with per-drug timing/logging
            results: List[EligibilityResult] = []
            for i, drug in enumerate(drugs, 1):
                self.logger.info(f"   ▶ Processing drug {i}/{len(drugs)}: {drug.etkin_madde}")
                drug_start = time.time()

                sut_chunks = sut_chunks_per_drug.get(drug.etkin_madde, [])
                try:
                    result = self.check_eligibility(
                        drug=drug,
                        diagnosis=primary_diagnosis,
                        patient=patient,
                        doctor=doctor,
                        sut_chunks=sut_chunks,
                        explanations=explanations
                    )
                except Exception as inner_e:
                    self.logger.error(f"Error checking eligibility for {drug.etkin_madde}: {inner_e}")
                    result = self._create_fallback_result(drug.etkin_madde, str(inner_e))

                drug_elapsed = time.time() - drug_start
                self.logger.info(f"   ✓ {drug.etkin_madde} done in {drug_elapsed:.2f}s")
                results.append(result)

            total_elapsed = time.time() - batch_start
            self.logger.warning(f"⚠️ Sequential fallback completed in {total_elapsed:.2f}s for {len(drugs)} drugs")
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

    def _check_all_drugs_batched(
        self,
        drugs: List[Drug],
        diagnosis: Diagnosis,
        patient: PatientInfo,
        doctor: DoctorInfo,
        sut_chunks_per_drug: Dict[str, List[Dict[str, Any]]],
        explanations: str = None
    ) -> List[EligibilityResult]:
        """
        PERFORMANCE OPTIMIZATION: Check all drugs in a single LLM call.
        
        Instead of N sequential API calls (60s each), this makes 1 batched call.
        Expected speedup: ~N times faster for N drugs.
        
        Args:
            drugs: List of drugs to check
            diagnosis: Primary diagnosis
            patient: Patient info
            doctor: Doctor info
            sut_chunks_per_drug: SUT chunks for each drug
            explanations: Report explanations
            
        Returns:
            List of EligibilityResult, one per drug
        """
        self.logger.info(f"Batch checking {len(drugs)} drugs in single LLM call")
        
        # Build combined prompt for all drugs
        from .prompts import SYSTEM_PROMPT
        
        explanations_section = f'📝 RAPOR AÇIKLAMALARI:\n{explanations}\n' if explanations else ''
        
        user_prompt = f"""Aşağıdaki {len(drugs)} ilacın SGK/SUT uygunluğunu AYNI ANDA değerlendir.

📋 HASTA BİLGİLERİ:
- Tanı: {diagnosis.icd10_code} - {diagnosis.tanim}
- Yaş: {patient.yas or 'Bilinmiyor'}
- Cinsiyet: {patient.cinsiyet or 'Bilinmiyor'}
- Doktor: {doctor.name} ({doctor.specialty})

{explanations_section}

"""

        # Add each drug with its SUT chunks
        separator = "=" * 60
        for i, drug in enumerate(drugs, 1):
            sut_chunks = sut_chunks_per_drug.get(drug.etkin_madde, [])
            
            user_prompt += f"""
{separator}
💊 İLAÇ {i}/{len(drugs)}: {drug.etkin_madde}
{separator}

İlaç Bilgileri:
- Etkin Madde: {drug.etkin_madde}
- Form: {drug.form}
- Tedavi Şeması: {drug.tedavi_sema}
- Miktar: {drug.miktar}

📖 İLGİLİ SUT KURALLARI:
"""
            
            if sut_chunks:
                for j, chunk in enumerate(sut_chunks[:5], 1):  # Top 5 chunks
                    metadata = chunk.get('metadata', {})
                    content = metadata.get('content', 'İçerik bulunamadı')
                    user_prompt += f"\n[Chunk {j}]\n{content}\n"
            else:
                user_prompt += "\n⚠️ Bu ilaç için SUT kuralı bulunamadı!\n"

        # Request batch response
        user_prompt += f"""

{separator}
TOPLU DEĞERLENDİRME İSTEĞİ
{separator}


Yukarıdaki {len(drugs)} ilacın HER BİRİ için ayrı ayrı değerlendirme yap.

JSON formatında döndür:
{{
  "results": [
    {{
      "drug_name": "İLAÇ ADI",
      "status": "ELIGIBLE|NOT_ELIGIBLE|CONDITIONAL",
      "confidence": 0.0-1.0,
      "sut_reference": "SUT kuralı referansı",
      "conditions": [
        {{
          "description": "Koşul açıklaması",
          "is_met": true|false|null,
          "required_info": "Eksik bilgi"
        }}
      ],
      "explanation": "Detaylı açıklama",
      "warnings": ["Uyarı 1", "Uyarı 2"]
    }}
  ]
}}

Her ilaç için AYRI bir result objesi oluştur. Toplam {len(drugs)} result olmalı.
"""

        # Make single LLM call
        try:
            response_json = self.client.chat_completion_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
            
            # Parse results
            results = []
            for i, (drug, result_data) in enumerate(zip(drugs, response_json.get('results', []))):
                try:
                    result = self._parse_response(result_data, drug.etkin_madde)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Error parsing result for {drug.etkin_madde}: {e}")
                    results.append(self._create_fallback_result(drug.etkin_madde, str(e)))
            
            # If we got fewer results than drugs, fill with fallbacks
            while len(results) < len(drugs):
                drug = drugs[len(results)]
                results.append(self._create_fallback_result(
                    drug.etkin_madde, 
                    "Yanıt eksik - LLM tüm ilaçları değerlendiremedi"
                ))
            
            self.logger.info(f"Batch check complete: {len(results)} results")
            return results
            
        except Exception as e:
            self.logger.error(f"Batch eligibility check failed: {e}")
            raise
