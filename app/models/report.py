"""Data models for patient reports and related entities."""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class Drug:
    """İlaç bilgilerini temsil eden model."""
    kod: str                    # SGKF07
    etkin_madde: str           # EZETIMIB
    form: str                  # Ağızdan katı
    tedavi_sema: str          # Günde 1 x 1.0 Adet
    miktar: int               # 1
    eklenme_zamani: date      # 26/12/2024


@dataclass
class Diagnosis:
    """Tanı bilgilerini temsil eden model."""
    icd10_code: str           # I25.1
    tanim: str                # Aterosklerotik Kalp Hastalığı
    baslangic: Optional[date] = None
    bitis: Optional[date] = None


@dataclass
class PatientInfo:
    """Hasta bilgilerini temsil eden model."""
    cinsiyet: Optional[str] = None
    dogum_tarihi: Optional[date] = None
    yas: Optional[int] = None
    # Privacy: TC kimlik saklanmayacak


@dataclass
class DoctorInfo:
    """Doktor bilgilerini temsil eden model."""
    name: str
    specialty: str
    diploma: str


@dataclass
class ParsedReport:
    """Parse edilmiş rapor model."""
    report_id: str
    date: date
    hospital_code: str
    doctor: DoctorInfo
    diagnoses: List[Diagnosis]
    drugs: List[Drug]
    patient: PatientInfo
    raw_text: str
    explanations: Optional[str] = None  # Rapor açıklamaları (LDL değerleri, statin kullanımı vb.)
    report_type: Optional[str] = None   # Rapor türü (Uzman Hekim Raporu, Sağlık Kurulu Raporu vb.)