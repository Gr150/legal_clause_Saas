"""
merge_lora.py — run once on DGX before starting Claura.
Merges the LoRA adapter into the base Mistral 7B model so vLLM can serve it.

Usage:
    python merge_lora.py
"""

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

BASE_MODEL  = "/home/guru/legal-risk-finetune/legal-risk-finetune/models/mistral-7b"
LORA_ADAPTER = "/home/guru/legal-risk-finetune/legal-risk-finetune/legal-risk-lora-adapters"
OUTPUT_PATH  = "/home/guru/legal-risk-finetune/legal-risk-finetune/legal-risk-merged"

print("Loading base model...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto",
)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(model, LORA_ADAPTER)

print("Merging weights...")
model = model.merge_and_unload()

print(f"Saving merged model to {OUTPUT_PATH} ...")
model.save_pretrained(OUTPUT_PATH)

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
tokenizer.save_pretrained(OUTPUT_PATH)

print("Done. Merged model saved.")
