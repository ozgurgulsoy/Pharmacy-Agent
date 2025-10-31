"""Diagnosis extraction from patient reports using LLM."""

import logging
import json
from datetime import datetime
from typing import List

from models.report import Diagnosis
from llm.openai_client import OpenAIClientWrapper

logger = logging.getLogger(__name__)


class DiagnosisExtractor:
    """Rapor metninden tanı bilgilerini LLM kullanarak çıkarır."""

    def __init__(self, openai_client: OpenAIClientWrapper = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.openai_client = openai_client or OpenAIClientWrapper()

    def extract_diagnoses(self, text: str) -> List[Diagnosis]:
        """
        Rapor metninden tanı listesini LLM kullanarak çıkarır.

        Args:
            text: Rapor metni

        Returns:
            Diagnosis listesi
        """
        try:
            system_prompt = """Sen bir tıbbi rapor analiz asistanısın. Sana verilen rapor metninden tanı bilgilerini çıkarman gerekiyor.

Raporda "Tanı Bilgileri" veya "Diagnosis Information" bölümünde tanılar listelenmiştir.
Her tanı için şu bilgileri çıkar:
- ICD-10 Kodu (örn: I25.1, E78.4, I10)
- Tanı Açıklaması/Adı (örn: ATEROSKLEROTİK KALP HASTALIĞI)
- Başlangıç Tarihi (GG/AA/YYYY formatında, varsa)
- Bitiş Tarihi (GG/AA/YYYY formatında, varsa)

JSON formatında döndür:
{
  "diagnoses": [
    {
      "icd10_code": "I25.1",
      "tanim": "ATEROSKLEROTİK KALP HASTALIĞI",
      "baslangic": "26/12/2024",
      "bitis": "25/12/2025"
    }
  ]
}

Eğer bir bilgi bulunamazsa null veya "UNKNOWN" kullan."""

            user_prompt = f"""Aşağıdaki rapor metninden tüm tanıları çıkar:

{text}

Lütfen sadece JSON formatında yanıt ver, başka açıklama ekleme."""

            response_text = self.openai_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"}
            )

            # JSON yanıtı parse et
            data = json.loads(response_text)
            
            diagnoses = []
            for diag_data in data.get("diagnoses", []):
                # Tarihleri parse et
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

                diagnosis = Diagnosis(
                    icd10_code=diag_data.get("icd10_code", "UNKNOWN"),
                    tanim=diag_data.get("tanim", "UNKNOWN"),
                    baslangic=baslangic,
                    bitis=bitis
                )
                diagnoses.append(diagnosis)

            self.logger.info(f"Extracted {len(diagnoses)} diagnoses using LLM")
            return diagnoses

        except Exception as e:
            self.logger.error(f"Error extracting diagnoses with LLM: {e}")
            return []
