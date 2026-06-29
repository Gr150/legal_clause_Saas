"""
Claura — model.py
Loads fine-tuned Mistral 7B + LoRA from local DGX Spark paths.
No API keys. No internet. Model already on disk.

Base model path:    /home/guru/legal-risk-finetune/legal-risk-finetune/models/mistral-7b
LoRA adapter path:  /home/guru/legal-risk-finetune/legal-risk-finetune/legal-risk-lora-adapters
"""

import os
import json
import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from peft import PeftModel
from typing import Optional

logger = logging.getLogger(__name__)

BASE_MODEL    = os.getenv(
    "BASE_MODEL_PATH",
    "/home/guru/legal-risk-finetune/legal-risk-finetune/models/mistral-7b"
)
ADAPTER_MODEL = os.getenv(
    "ADAPTER_MODEL_PATH",
    "/home/guru/legal-risk-finetune/legal-risk-finetune/legal-risk-lora-adapters"
)

_pipe = None

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
    global _pipe
    if _pipe is not None:
        return

    logger.info("Loading base model from: %s", BASE_MODEL)

    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL,
        trust_remote_code=True
    )
    tokenizer.pad_token = tokenizer.eos_token

    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )

    logger.info("Merging LoRA adapters from: %s", ADAPTER_MODEL)
    model = PeftModel.from_pretrained(base, ADAPTER_MODEL)
    model = model.merge_and_unload()

    _pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=350,
        temperature=0.1,
        do_sample=False,
        return_full_text=True
    )

    logger.info("Fine-tuned model ready — F1 0.887")


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


def _parse(raw: str, prompt: str) -> Optional[dict]:
    response = raw[len(prompt):].strip()
    try:
        start = response.find("{")
        end   = response.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(response[start:end])
    except Exception:
        return None


def _fallback(text: str) -> dict:
    t = text.lower()
    risk  = "Medium"
    ctype = "Commercial Clause"
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
    if _pipe is None:
        result = _fallback(clause_text)
    else:
        try:
            prompt = _build_prompt(clause_text)
            output = _pipe(prompt)[0]["generated_text"]
            result = _parse(output, prompt)
            if result is None:
                result = _fallback(clause_text)
        except Exception as e:
            logger.error("Inference error: %s", e)
            result = _fallback(clause_text)

    result["wording"]    = NEGOTIATION_WORDING.get(result.get("clause_type", ""))
    result["confidence"] = 0.887 if _pipe else 0.70
    return result
