"""Patient information extraction from reports using LLM."""

import logging
import json
from datetime import datetime
from typing import Optional

from models.report import PatientInfo
from llm.openai_client import OpenAIClientWrapper

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class PatientInfoExtractor:
    """Rapor metninden hasta bilgilerini LLM kullanarak çıkarır."""

    def __init__(self, openai_client: OpenAIClientWrapper = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.openai_client = openai_client or OpenAIClientWrapper()

    def extract_patient_info(self, text: str) -> PatientInfo:
        """
        Rapor metninden hasta bilgilerini LLM kullanarak çıkarır.

        NOT: TC Kimlik numarası GÜVENLİK nedeniyle çıkarılmaz/saklanmaz!

        Args:
            text: Rapor metni

        Returns:
            PatientInfo objesi
        """
        try:
            system_prompt = """Sen bir tıbbi rapor analiz asistanısın. Sana verilen rapor metninden hasta bilgilerini çıkarman gerekiyor.

Rapordaki "Personal Information" veya "Hasta Bilgileri" bölümünden şu bilgileri çıkar:
- Cinsiyet (Erkek/Kadın)
- Doğum Tarihi (GG/AA/YYYY formatında, varsa)
- Yaş (sayı olarak, varsa)

ÖNEMLİ: TC Kimlik numarası gibi kişisel bilgileri ÇIKARMA!

JSON formatında döndür:
{
  "cinsiyet": "Erkek",
  "dogum_tarihi": "12/04/1954",
  "yas": 71
}

Eğer bir bilgi bulunamazsa null kullan."""

            user_prompt = f"""Aşağıdaki rapor metninden hasta bilgilerini çıkar:

{text}

Lütfen sadece JSON formatında yanıt ver, başka açıklama ekleme."""

            response_text = self.openai_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"}
            )

            # JSON yanıtı parse et
            data = json.loads(response_text)
            
            # Doğum tarihini parse et
            dogum_tarihi = None
            if data.get("dogum_tarihi"):
                try:
                    day, month, year = data["dogum_tarihi"].split('/')
                    dogum_tarihi = datetime(int(year), int(month), int(day)).date()
                except:
                    pass

            patient_info = PatientInfo(
                cinsiyet=data.get("cinsiyet"),
                dogum_tarihi=dogum_tarihi,
                yas=data.get("yas")
            )

            self.logger.info(f"Extracted patient info using LLM: {patient_info.cinsiyet}, {patient_info.yas} yaş")
            return patient_info

        except Exception as e:
            self.logger.error(f"Error extracting patient info with LLM: {e}")
            return PatientInfo(cinsiyet=None, dogum_tarihi=None, yas=None)
