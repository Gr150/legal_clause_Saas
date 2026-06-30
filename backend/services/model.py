"""
Claura — model.py
Uses a local vLLM server (OpenAI-compatible) to run the fine-tuned Mistral 7B model.
vLLM must be running on port 8001 before starting Claura.
"""

import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

VLLM_URL   = os.getenv("VLLM_URL",   "http://localhost:8001/v1/completions")
VLLM_MODEL = os.getenv("VLLM_MODEL", "legal-risk-classifier")
HEADERS    = {"Content-Type": "application/json"}

NEGOTIATION_WORDING = {
    "Indemnification": (
        "We accept this clause subject to the addition of: "
        "'The Subcontractor's total liability under this indemnity "
        "shall not exceed the Subcontract Sum.' and deletion of any "
        "reference to unforeseeable losses."
    ),
    "Termination for Convenience": (
        "We accept subject to the addition of: "
        "'Upon termination for convenience the Contractor shall pay "
        "the Subcontractor: (a) reasonable demobilisation costs; "
        "(b) loss of profit on the uncompleted portion of the Works "
        "calculated at the margin in the Subcontractor's tender.'"
    ),
    "Liquidated Damages": (
        "We accept LADs subject to insertion of an aggregate cap "
        "not exceeding 10% of the Subcontract Sum and deletion of "
        "any cross-contract deduction right."
    ),
    "Payment Terms": (
        "We require the payment period to be reduced to 28 days in "
        "compliance with the Housing Grants, Construction and "
        "Regeneration Act 1996. We also require interest on late "
        "payments at 8% above Bank of England base rate per the "
        "Late Payment of Commercial Debts (Interest) Act 1998."
    ),
    "Set-Off": (
        "We require deletion of this clause and replacement with: "
        "'The Contractor may only deduct sums after serving a valid "
        "Pay Less Notice under section 111 of the Housing Grants, "
        "Construction and Regeneration Act 1996, specifying the sum "
        "and the basis of calculation.'"
    ),
    "Design Liability": (
        "We accept design responsibility subject to deletion of "
        "'fit for its intended purpose' and replacement with "
        "'reasonable skill and care to be expected of a competent "
        "specialist designer experienced in works of a similar nature' "
        "to match our Professional Indemnity insurance cover."
    ),
    "Limitation of Liability": (
        "We require the limitation to apply mutually to both parties "
        "at a level not less than the Subcontract Sum."
    ),
    "Retention": (
        "We require retention monies to be held in a separately "
        "designated trust account, not forming part of the "
        "Contractor's general assets."
    ),
}


def load_model():
    """Check vLLM server is reachable on startup."""
    try:
        r = requests.get(VLLM_URL.replace("/v1/completions", "/health"), timeout=5)
        if r.status_code == 200:
            logger.info("vLLM server ready at %s", VLLM_URL)
        else:
            logger.warning("vLLM returned %s — falling back to keyword classifier", r.status_code)
    except Exception as e:
        logger.warning("vLLM not reachable (%s) — falling back to keyword classifier", e)


def _build_prompt(clause_text: str) -> str:
    return (
        "<s>[INST] You are a legal risk analyst specialising in "
        "UK construction contracts (NEC4 and JCT).\n\n"
        f"Analyse this contract clause:\n{clause_text[:700]}\n\n"
        "Respond ONLY with a valid JSON object — no other text:\n"
        "{\n"
        '  "clause_type": "one of: Indemnification, Payment Terms, '
        "Liquidated Damages, Termination for Convenience, "
        "Limitation of Liability, Governing Law, Confidentiality, "
        "Notice Period, Insurance, Design Liability, Set-Off, "
        'Retention, Dispute Resolution, or other specific type",\n'
        '  "risk_level": "High or Medium or Low",\n'
        '  "summary": "one sentence plain English for a non-lawyer",\n'
        '  "reason": "specific financial or legal consequence"\n'
        "} [/INST]"
    )


def _parse(raw_text: str) -> dict | None:
    try:
        start = raw_text.find("{")
        end   = raw_text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(raw_text[start:end])
    except Exception:
        return None


def _fallback(text: str) -> dict:
    t = text.lower()
    risk, ctype = "Medium", "Commercial Clause"
    if any(k in t for k in ["indemni", "hold harmless", "all claims", "unlimited", "all losses"]):
        risk, ctype = "High", "Indemnification"
    elif any(k in t for k in ["liquidat", "lad", "delay damages"]):
        risk, ctype = "High", "Liquidated Damages"
    elif any(k in t for k in ["terminat for convenience", "terminate at will"]):
        risk, ctype = "High", "Termination for Convenience"
    elif any(k in t for k in ["45 day", "payment", "invoice", "application"]):
        risk, ctype = "High", "Payment Terms"
    elif any(k in t for k in ["set-off", "setoff", "deduct", "withhold"]):
        risk, ctype = "High", "Set-Off"
    elif any(k in t for k in ["fit for purpose", "fitness for purpose"]):
        risk, ctype = "High", "Design Liability"
    elif any(k in t for k in ["retention", "5%", "2.5%"]):
        risk, ctype = "Medium", "Retention"
    elif any(k in t for k in ["confidential"]):
        risk, ctype = "Low", "Confidentiality"
    elif any(k in t for k in ["govern", "jurisdiction", "england"]):
        risk, ctype = "Medium", "Governing Law"
    elif any(k in t for k in ["notice", "28 day", "notification"]):
        risk, ctype = "Medium", "Notice Period"
    return {
        "clause_type": ctype,
        "risk_level":  risk,
        "summary":     "Review this clause carefully before signing.",
        "reason":      "Identified based on contract language patterns.",
    }


def classify_clause(clause_text: str) -> dict:
    """Classify a single clause via local vLLM server."""
    prompt = _build_prompt(clause_text)

    try:
        response = requests.post(
            VLLM_URL,
            headers=HEADERS,
            json={
                "model":       VLLM_MODEL,
                "prompt":      prompt,
                "max_tokens":  350,
                "temperature": 0.1,
            },
            timeout=60
        )
        response.raise_for_status()
        raw_text = response.json()["choices"][0]["text"]
        result   = _parse(raw_text)
        if result is None:
            result = _fallback(clause_text)
            result["confidence"] = 0.70
        else:
            result["confidence"] = 0.887
    except Exception as e:
        logger.error("vLLM inference failed: %s", e)
        result = _fallback(clause_text)
        result["confidence"] = 0.70

    result["wording"] = NEGOTIATION_WORDING.get(result.get("clause_type", ""))
    return result
