"""
Claura — routes/analyse.py
Runs fine-tuned model on each clause and returns structured risk output.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone

from models.schemas import AnalyseResponse, ClauseResult, RiskLevel, CorrectionRequest
from services.database import get_db, Contract, Clause, Correction
from services.model import classify_clause
from middleware.auth import get_current_user

router = APIRouter()


def _verdict(high: int, medium: int) -> str:
    if high > 0:
        return "REVIEW BEFORE SIGNING"
    if medium > 2:
        return "CAUTION — SEEK ADVICE"
    return "SAFE TO SIGN"


@router.post("/{contract_id}", response_model=AnalyseResponse)
async def analyse_contract(
    contract_id:  int,
    db:           AsyncSession = Depends(get_db),
    current_user: dict         = Depends(get_current_user)
):
    """
    Run risk classification on all clauses of an uploaded contract.
    Uses the fine-tuned Mistral 7B LoRA model.
    """
    user_id = int(current_user["sub"])

    # Verify contract belongs to user
    result   = await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.user_id == user_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get clauses
    result  = await db.execute(
        select(Clause).where(Clause.contract_id == contract_id)
    )
    clauses = result.scalars().all()

    if not clauses:
        raise HTTPException(status_code=404, detail="No clauses found — upload the contract first")

    # Run model on each clause
    results      = []
    high_count   = 0
    medium_count = 0
    low_count    = 0

    for clause in clauses:
        prediction = classify_clause(clause.clause_text)

        risk = prediction.get("risk_level", "Medium")
        if risk == "High":   high_count   += 1
        elif risk == "Medium": medium_count += 1
        else:                low_count    += 1

        # Update clause in DB
        clause.clause_type = prediction.get("clause_type", "Unknown")
        clause.risk_level  = risk
        clause.summary     = prediction.get("summary", "")
        clause.reason      = prediction.get("reason", "")
        clause.wording     = prediction.get("wording")
        clause.confidence  = prediction.get("confidence", 0.9)

        results.append(ClauseResult(
            clause_id=clause.id,
            clause_text=clause.clause_text[:300] + "..." if len(clause.clause_text) > 300 else clause.clause_text,
            clause_type=clause.clause_type,
            risk_level=RiskLevel(risk),
            summary=clause.summary,
            reason=clause.reason,
            confidence=clause.confidence,
            wording=clause.wording
        ))

    # Update contract summary
    verdict = _verdict(high_count, medium_count)
    contract.high_risk   = high_count
    contract.medium_risk = medium_count
    contract.low_risk    = low_count
    contract.verdict     = verdict
    contract.status      = "complete"

    return AnalyseResponse(
        contract_id=contract.id,
        filename=contract.filename,
        contract_type=contract.contract_type,
        total_clauses=len(clauses),
        high_risk=high_count,
        medium_risk=medium_count,
        low_risk=low_count,
        verdict=verdict,
        clauses=results,
        analysed_at=datetime.utcnow()
    )


@router.post("/correct/{clause_id}")
async def correct_clause(
    clause_id:    int,
    body:         CorrectionRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: dict         = Depends(get_current_user)
):
    """
    HITL — submit a correction on a clause.
    Corrections are stored and feed future model retraining.
    """
    user_id = int(current_user["sub"])

    result = await db.execute(select(Clause).where(Clause.id == clause_id))
    clause = result.scalar_one_or_none()
    if not clause:
        raise HTTPException(status_code=404, detail="Clause not found")

    correction = Correction(
        clause_id=clause_id,
        user_id=user_id,
        corrected_type=body.corrected_type,
        corrected_risk=body.corrected_risk,
        corrected_reason=body.corrected_reason
    )
    db.add(correction)
    return {"message": "Correction saved. Thank you — this improves Claura for everyone."}
