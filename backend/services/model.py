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

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001/v1/completions")
VLLM_MODEL = os.getenv("VLLM_MODEL", "legal-risk-classifier")
HEADERS  = {"Content-Type": "application/json"}

NEGOTIATION_WORDING = {
    "Indemnification": (
        "We accept this clause subject to the addition of: "
        "'The Contractor's total liability under this indemnity "
        "shall not exceed the Contract Sum.'"
    ),
    "Termination for Convenience": (
        "We accept subject to the addition of: "
        "'Upon termination for convenience the Employer shall pay "
        "the Contractor reasonable demobilisation costs and loss of "
        "profit on the uncompleted portion of the Works.'"
    ),
    "Liquidated Damages": (
        "We accept LADs subject to insertion of an aggregate cap "
        "not exceeding 10% of the Contract Sum."
    ),
    "Payment Terms": (
        "We accept payment terms subject to reducing the assessment "
        "period to 28 days in compliance with the Housing Grants, "
        "Construction and Regeneration Act 1996."
    ),
    "Limitation of Liability": (
        "We note the limitation of liability clause. We require "
        "confirmation that the cap applies mutually to both parties."
    ),
}


def load_model():
    """Check vLLM server is reachable on startup."""
    try:
        r = requests.get(VLLM_URL.replace("/v1/completions", "/health"), timeout=5)
        if r.status_code == 200:
            logger.info("vLLM server ready at %s", VLLM_URL)
        else:
            logger.warning("vLLM server returned %s — falling back to keyword classifier", r.status_code)
    except Exception as e:
        logger.warning("vLLM server not reachable (%s) — falling back to keyword classifier", e)


def _build_prompt(clause_text: str) -> str:
    preview = clause_text.strip()[:700]
    return (
        f"<s>[INST] You are a legal risk analyst for UK construction contracts.\n\n"
        f"Analyse this NEC4 or JCT subcontract clause. Be specific about the clause type.\n\n"
        f"Clause types to identify:\n"
        f"Indemnification, Payment Terms, Limitation of Liability, Liquidated Damages, "
        f"Termination for Convenience, Termination for Default, Governing Law, "
        f"Confidentiality, Design Liability, Retention, Set-Off, Notice Requirements, "
        f"Insurance, Warranty, IP Ownership, Non-Compete, Assignment, Dispute Resolution, "
        f"Cooperation Obligation, Programme Obligation\n\n"
        f"Contract clause:\n{preview}\n\n"
        f"Respond ONLY with valid JSON:\n"
        f'{{\n'
        f'  "clause_type": "specific type from the list above",\n'
        f'  "risk_level": "High or Medium or Low",\n'
        f'  "summary": "one sentence plain English — what this means for the subcontractor",\n'
        f'  "reason": "why this risk level — be specific about the financial or legal consequence"\n'
        f'}} [/INST]'
    )


def _parse(raw) -> dict | None:
    try:
        # HF returns list of generated_text dicts
        if isinstance(raw, list):
            text = raw[0].get("generated_text", "")
        elif isinstance(raw, dict):
            text = raw.get("generated_text", str(raw))
        else:
            text = str(raw)

        start = text.find("{")
        end   = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(text[start:end])
    except Exception:
        return None


def classify_clause(clause_text: str) -> dict:
    """Classify a single clause via local vLLM server."""
    prompt = _build_prompt(clause_text)

    try:
        response = requests.post(
            VLLM_URL,
            headers=HEADERS,
            json={
                "model": VLLM_MODEL,
                "prompt": prompt,
                "max_tokens": 350,
                "temperature": 0.1,
            },
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["text"]
        result = _parse({"generated_text": raw_text})
        if result is None:
            result = _fallback(clause_text)
            result["confidence"] = 0.70
        else:
            result["confidence"] = 0.95
    except Exception as e:
        logger.error("vLLM inference failed: %s", e)
        result = _fallback(clause_text)
        result["confidence"] = 0.70

    result["wording"] = NEGOTIATION_WORDING.get(result.get("clause_type", ""))
    return result


def _fallback(text: str) -> dict:
    t = text.lower()
    risk  = "Medium"
    ctype = "Commercial Clause"
    if any(k in t for k in ["indemni", "hold harmless", "unlimited", "all claims", "terminate for convenience", "liquidated"]):
        risk = "High"
        if "indemni" in t or "hold harmless" in t:
            ctype = "Indemnification"
        elif "terminat" in t:
            ctype = "Termination for Convenience"
        elif "liquidat" in t:
            ctype = "Liquidated Damages"
    elif any(k in t for k in ["confidential", "notice period", "audit right"]):
        risk = "Low"
        ctype = "Standard Clause"
    return {
        "clause_type": ctype,
        "risk_level":  risk,
        "summary":     "This clause requires review before signing.",
        "reason":      "Identified based on key contract language patterns."
    }
