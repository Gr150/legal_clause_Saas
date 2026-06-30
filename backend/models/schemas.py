"""
Claura — schemas.py
Pydantic request and response models
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    high   = "High"
    medium = "Medium"
    low    = "Low"


class ContractType(str, Enum):
    nec4_ecc  = "NEC4 Engineering and Construction Contract"
    nec4_sub  = "NEC4 Engineering and Construction Subcontract"
    jct_db    = "JCT Design and Build Subcontract"
    jct_minor = "JCT Minor Works Contract"
    jct_std   = "JCT Standard Building Contract"
    bespoke   = "Bespoke / Other"


# ── AUTH ──────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email:        EmailStr
    password:     str = Field(min_length=8)
    company_name: str = Field(min_length=2)

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token:  str
    token_type:    str = "bearer"
    user_id:       int
    company_name:  str


# ── UPLOAD ────────────────────────────────────────────────────────
class UploadResponse(BaseModel):
    contract_id:   int
    filename:      str
    status:        str
    clause_count:  int
    message:       str


# ── CLAUSE ────────────────────────────────────────────────────────
class ClauseResult(BaseModel):
    clause_id:   int
    clause_text: str
    clause_type: str
    risk_level:  RiskLevel
    summary:     str
    reason:      str
    confidence:  float
    wording:     Optional[str] = None   # suggested negotiation wording


# ── ANALYSE ───────────────────────────────────────────────────────
class AnalyseResponse(BaseModel):
    contract_id:     int
    filename:        str
    contract_type:   str
    total_clauses:   int
    high_risk:       int
    medium_risk:     int
    low_risk:        int
    verdict:         str   # "REVIEW BEFORE SIGNING" / "SAFE TO SIGN" / "CAUTION"
    clauses:         List[ClauseResult]
    analysed_at:     datetime


# ── RESULTS ───────────────────────────────────────────────────────
class ContractSummary(BaseModel):
    contract_id:   int
    filename:      str
    contract_type: str
    high_risk:     int
    medium_risk:   int
    low_risk:      int
    verdict:       str
    uploaded_at:   datetime

class ResultsResponse(BaseModel):
    contracts:     List[ContractSummary]
    total:         int


# ── CORRECTION (HITL) ─────────────────────────────────────────────
class CorrectionRequest(BaseModel):
    clause_id:          int
    corrected_type:     Optional[str]      = None
    corrected_risk:     Optional[RiskLevel] = None
    corrected_reason:   Optional[str]      = None
