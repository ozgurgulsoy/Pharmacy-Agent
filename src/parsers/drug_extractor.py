"""Drug extraction from patient reports using LLM."""

import logging
import json
from datetime import datetime
from typing import List

from models.report import Drug
from llm.openai_client import OpenAIClientWrapper

logger = logging.getLogger(__name__)


class DrugExtractor:
    """Rapor metninden ilaç bilgilerini LLM kullanarak çıkarır."""

    def __init__(self, openai_client: OpenAIClientWrapper = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.openai_client = openai_client or OpenAIClientWrapper()

    def extract_drugs(self, text: str) -> List[Drug]:
        """
        Rapor metninden ilaç listesini LLM kullanarak çıkarır.

        Args:
            text: Rapor metni

        Returns:
            Drug listesi
        """
        try:
            # LLM'e ilaç çıkarma prompt'u gönder
            system_prompt = """Sen bir tıbbi rapor analiz asistanısın. Sana verilen rapor metninden ilaç bilgilerini çıkarman gerekiyor.

Raporda "Rapor Etkin Madde Bilgileri" veya "İlaç Listesi" bölümünde ilaçlar listelenmiştir.
Her ilaç için şu bilgileri çıkar:
- SGK Kodu (örn: SGKF09, SGKFDX, SGKF60)
- Etkin Madde (ilaç adı, örn: KLOPİDOGREL HİDROJEN SÜLFAT, METOPROLOL, İRBESARTAN)
- Form (örn: Ağızdan katı, Enjektabl)
- Tedavi Şeması (örn: Günde 1 x 1.0 Adet)
- Miktar (sayı olarak)
- Eklenme Tarihi (GG/AA/YYYY formatında)

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
  ]
}

Eğer bir bilgi bulunamazsa "UNKNOWN" veya varsayılan değer kullan."""

            user_prompt = f"""Aşağıdaki rapor metninden tüm ilaçları çıkar:

{text}

Lütfen sadece JSON formatında yanıt ver, başka açıklama ekleme."""

            response_text = self.openai_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"}
            )

            # JSON yanıtı parse et
            data = json.loads(response_text)
            
            drugs = []
            for drug_data in data.get("drugs", []):
                # Tarihi parse et
                eklenme_zamani = datetime.now().date()
                if "eklenme_zamani" in drug_data and drug_data["eklenme_zamani"] != "UNKNOWN":
                    try:
                        date_str = drug_data["eklenme_zamani"]
                        day, month, year = date_str.split('/')
                        eklenme_zamani = datetime(int(year), int(month), int(day)).date()
                    except:
                        pass

                drug = Drug(
                    kod=drug_data.get("kod", "UNKNOWN"),
                    etkin_madde=drug_data.get("etkin_madde", "UNKNOWN"),
                    form=drug_data.get("form", "Ağızdan katı"),
                    tedavi_sema=drug_data.get("tedavi_sema", "Günde 1 x 1"),
                    miktar=drug_data.get("miktar", 1),
                    eklenme_zamani=eklenme_zamani
                )
                drugs.append(drug)

            self.logger.info(f"Extracted {len(drugs)} drugs using LLM")
            return drugs

        except Exception as e:
            self.logger.error(f"Error extracting drugs with LLM: {e}")
            return []
