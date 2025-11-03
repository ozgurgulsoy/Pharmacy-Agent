"""Main eligibility checker using LLM."""

import logging
from typing import List, Dict, Any, Optional

from app.models.report import Drug, Diagnosis, PatientInfo, DoctorInfo
from app.models.eligibility import EligibilityResult, Condition
from .openai_client import OpenAIClientWrapper
from .prompts import PromptBuilder, SYSTEM_PROMPT
from app.config.settings import MAX_BATCH_SIZE

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
        For large numbers of drugs (>3), falls back to sequential to ensure accuracy.

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

        num_drugs = len(drugs)
        
        if num_drugs > MAX_BATCH_SIZE:
            self.logger.warning(f"⚠️ {num_drugs} drugs detected - using sequential processing for reliability")
            self.logger.info(f"(Batch processing works best for 1-{MAX_BATCH_SIZE} drugs; {num_drugs} drugs may cause incomplete responses)")
            self.logger.info(f"💡 TIP: Adjust MAX_BATCH_SIZE in .env if using a more reliable model like gpt-5-mini")
            
            # Sequential processing with timing
            import time
            total_start = time.time()
            results: List[EligibilityResult] = []
            
            for i, drug in enumerate(drugs, 1):
                self.logger.info(f"   ▶ Processing drug {i}/{num_drugs}: {drug.etkin_madde}")
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
                except Exception as e:
                    self.logger.error(f"Error checking eligibility for {drug.etkin_madde}: {e}")
                    result = self._create_fallback_result(drug.etkin_madde, str(e))
                
                drug_elapsed = time.time() - drug_start
                self.logger.info(f"   ✓ {drug.etkin_madde} done in {drug_elapsed:.2f}s")
                results.append(result)
            
            total_elapsed = time.time() - total_start
            avg_time = total_elapsed / num_drugs if num_drugs > 0 else 0
            self.logger.info(f"✅ Sequential processing completed: {total_elapsed:.2f}s total, {avg_time:.2f}s avg/drug")
            return results
        
        # BATCHED PROCESSING: For 1-3 drugs, batch processing is reliable and fast
        import time
        batch_start = time.time()
        self.logger.info(f"🔍 Starting eligibility check for {num_drugs} drugs (batched processing)")

        try:
            self.logger.info(f"🚀 Batched LLM call for {num_drugs} drug(s)")
            results = self._check_all_drugs_batched(
                drugs=drugs,
                diagnosis=primary_diagnosis,
                patient=patient,
                doctor=doctor,
                sut_chunks_per_drug=sut_chunks_per_drug,
                explanations=explanations
            )

            batch_elapsed = time.time() - batch_start
            avg_ms = (batch_elapsed * 1000) / num_drugs if num_drugs > 0 else 0

            self.logger.info(f"✅ Batched check succeeded in {batch_elapsed:.2f}s (avg {avg_ms:.1f}ms/drug)")
            return results

        except Exception as e:
            self.logger.error(f"❌ Batched LLM call failed: {type(e).__name__}: {e}")
            self.logger.exception("Batched eligibility failure stacktrace")
            self.logger.warning("⚠️ Falling back to sequential processing")

            # Sequential fallback
            results: List[EligibilityResult] = []
            for i, drug in enumerate(drugs, 1):
                self.logger.info(f"   ▶ Processing drug {i}/{num_drugs}: {drug.etkin_madde}")
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
            self.logger.warning(f"⚠️ Sequential fallback completed in {total_elapsed:.2f}s for {num_drugs} drugs")
            return results

    def _parse_response(self, response_json: Dict[str, Any], drug_name: str) -> EligibilityResult:
        """LLM JSON yanıtını EligibilityResult'a çevirir."""
        try:
            # Handle error responses from JSON parsing failures
            if 'parse_error' in response_json:
                self.logger.warning(f"Handling partial/malformed response for {drug_name}")
                raw_response = response_json.get('raw_response', '')
                
                # Try to extract partial information from raw text
                if raw_response:
                    status_candidate = self._extract_string_field(raw_response, "status")
                    status_upper = (status_candidate or '').upper()
                    status = status_upper if status_upper in {"ELIGIBLE", "NOT_ELIGIBLE", "CONDITIONAL"} else 'CONDITIONAL'

                    explanation_candidate = self._extract_string_field(raw_response, "explanation")
                    explanation = (explanation_candidate or 'Yanıt kısmi/hatalı olabilir.')[:500]
                    
                    return EligibilityResult(
                        drug_name=drug_name,
                        status=status,
                        confidence=0.3,  # Low confidence due to parse error
                        sut_reference='Parse hatası nedeniyle sınırlı bilgi',
                        conditions=[],
                        explanation=f"⚠️ Yanıt tam parse edilemedi. Kısmi bilgi:\n{explanation}",
                        warnings=["JSON parse hatası oluştu", "Manuel kontrol önerilir"]
                    )
                else:
                    return self._create_fallback_result(drug_name, response_json.get('parse_error', 'Unknown error'))
            
            # Normal parsing
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

    def _extract_string_field(self, payload: str, key: str) -> Optional[str]:
        """Extract simple string values from a JSON-like snippet without regex."""
        if not payload:
            return None

        marker = f'"{key}"'
        idx = payload.find(marker)
        if idx == -1:
            return None

        colon_idx = payload.find(':', idx + len(marker))
        if colon_idx == -1:
            return None

        first_quote = payload.find('"', colon_idx + 1)
        if first_quote == -1:
            return None

        second_quote = first_quote + 1
        while second_quote < len(payload):
            candidate_char = payload[second_quote]
            if candidate_char == '"' and payload[second_quote - 1] != '\\':
                break
            second_quote += 1

        if second_quote >= len(payload) or payload[second_quote] != '"':
            return None

        return payload[first_quote + 1:second_quote]
