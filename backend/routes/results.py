"""
Claura — routes/results.py
Retrieve past contract analyses.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from models.schemas import ResultsResponse, ContractSummary, AnalyseResponse, ClauseResult, RiskLevel
from services.database import get_db, Contract, Clause
from middleware.auth import get_current_user

router = APIRouter()


@router.get("/", response_model=ResultsResponse)
async def get_all_results(
    db:           AsyncSession = Depends(get_db),
    current_user: dict         = Depends(get_current_user)
):
    """Return all contracts for the current user."""
    user_id = int(current_user["sub"])

    result    = await db.execute(
        select(Contract)
        .where(Contract.user_id == user_id, Contract.status == "complete")
        .order_by(desc(Contract.uploaded_at))
    )
    contracts = result.scalars().all()

    summaries = [
        ContractSummary(
            contract_id=c.id,
            filename=c.filename,
            contract_type=c.contract_type,
            high_risk=c.high_risk,
            medium_risk=c.medium_risk,
            low_risk=c.low_risk,
            verdict=c.verdict or "PENDING",
            uploaded_at=c.uploaded_at
        )
        for c in contracts
    ]

    return ResultsResponse(contracts=summaries, total=len(summaries))


@router.get("/{contract_id}", response_model=AnalyseResponse)
async def get_result(
    contract_id:  int,
    db:           AsyncSession = Depends(get_db),
    current_user: dict         = Depends(get_current_user)
):
    """Return full analysis for a single contract."""
    user_id = int(current_user["sub"])

    result   = await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.user_id == user_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    result  = await db.execute(
        select(Clause).where(Clause.contract_id == contract_id)
    )
    clauses = result.scalars().all()

    return AnalyseResponse(
        contract_id=contract.id,
        filename=contract.filename,
        contract_type=contract.contract_type,
        total_clauses=len(clauses),
        high_risk=contract.high_risk,
        medium_risk=contract.medium_risk,
        low_risk=contract.low_risk,
        verdict=contract.verdict or "PENDING",
        clauses=[
            ClauseResult(
                clause_id=c.id,
                clause_text=c.clause_text[:300] + "..." if len(c.clause_text) > 300 else c.clause_text,
                clause_type=c.clause_type,
                risk_level=RiskLevel(c.risk_level),
                summary=c.summary,
                reason=c.reason,
                confidence=c.confidence,
                wording=c.wording
            )
            for c in clauses
        ],
        analysed_at=contract.uploaded_at
    )
