"""Lokales Chat-Modell über Hugging Face transformers."""
import os
import threading

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
DEVICE = os.environ.get("LLM_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.7"))

_tokenizer = None
_model = None
_load_lock = threading.Lock()
# Ein Modell, eine Generierung zur Zeit – parallele Anfragen warten.
_gen_lock = threading.Lock()


def load() -> None:
    global _tokenizer, _model
    with _load_lock:
        if _model is not None:
            return
        dtype = torch.float16 if DEVICE.startswith("cuda") else torch.float32
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        _model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=dtype).to(DEVICE)
        _model.eval()


def generate(messages: list[dict], max_new_tokens: int) -> str:
    load()
    prompt = _tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = _tokenizer(prompt, return_tensors="pt").to(DEVICE)
    with _gen_lock, torch.inference_mode():
        out = _model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=TEMPERATURE > 0,
            temperature=TEMPERATURE if TEMPERATURE > 0 else None,
            top_p=0.9 if TEMPERATURE > 0 else None,
            pad_token_id=_tokenizer.pad_token_id or _tokenizer.eos_token_id,
        )
    new_tokens = out[0, inputs["input_ids"].shape[1]:]
    return _tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
