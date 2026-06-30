"""
Claura — routes/upload.py
PDF upload endpoint — extracts and stores clauses.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.schemas import UploadResponse, ContractType
from services.database import get_db, Contract, Clause
from services.pdf_parser import parse_contract
from middleware.auth import get_current_user

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/", response_model=UploadResponse)
async def upload_contract(
    file:          UploadFile = File(...),
    contract_type: str        = Form(default="NEC4 Engineering and Construction Subcontract"),
    db:            AsyncSession = Depends(get_db),
    current_user:  dict       = Depends(get_current_user)
):
    """
    Upload a contract PDF.
    Extracts clauses and stores them ready for analysis.
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Read file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large — maximum 50MB")

    # Extract clauses
    try:
        clause_texts = parse_contract(contents)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {str(e)}")

    if not clause_texts:
        raise HTTPException(status_code=422, detail="No clauses found in this document")

    # Store contract record
    user_id  = int(current_user["sub"])
    contract = Contract(
        user_id=user_id,
        filename=file.filename,
        contract_type=contract_type,
        status="ready"
    )
    db.add(contract)
    await db.flush()

    # Store raw clause texts (risk analysis runs in /analyse)
    for text in clause_texts:
        clause = Clause(
            contract_id=contract.id,
            clause_text=text,
            clause_type="Pending",
            risk_level="Medium",
            summary="Pending analysis",
            reason="Not yet analysed"
        )
        db.add(clause)

    return UploadResponse(
        contract_id=contract.id,
        filename=file.filename,
        status="ready",
        clause_count=len(clause_texts),
        message=f"Uploaded successfully. {len(clause_texts)} clauses extracted. Call /analyse/{contract.id} to run risk analysis."
    )
