"""Token counting against the *embedding model's own* tokenizer.

Two traps this exists to avoid:

1. `all-MiniLM-L6-v2` advertises `model_max_length: 512` in its tokenizer
   config but sentence-transformers truncates at the `max_seq_length: 256`
   from `sentence_bert_config.json`. Anything longer is silently discarded --
   no error, no warning, just a vector for the first 256 tokens. So the budget
   must come from the sentence-transformers config, not the tokenizer's.

2. `tiktoken` (already a project dependency) is OpenAI BPE and does not match
   any HuggingFace model's tokenization. These docs run 2.12 tokens/word in
   prose and 2.80 inside code fences, well above the ~1.3 rule of thumb, so a
   heuristic under-counts by roughly 2x and quietly overruns the budget.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Protocol

from loguru import logger

from tauri_assistant.settings import settings
from huggingface_hub import hf_hub_download
from transformers import AutoTokenizer


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...

    @property
    def budget(self) -> int: ...


def _model_max_seq_length(model_name: str) -> int | None:
    """Read `max_seq_length` from the model's sentence-transformers config."""
    try:
        path = hf_hub_download(model_name, "sentence_bert_config.json")
        with open(path) as fh:
            return int(json.load(fh)["max_seq_length"])
    except Exception as exc:  # not a sentence-transformers model, or offline
        logger.debug(f"No sentence_bert_config.json for {model_name}: {exc}")
        return None


class HFTokenCounter:
    def __init__(self, model_name: str, max_tokens: int) -> None:

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        model_limit = _model_max_seq_length(model_name)
        if model_limit is None:
            model_limit = getattr(self._tokenizer, "model_max_length", max_tokens)
            # Some tokenizers use a sentinel like 1e30 to mean "unbounded".
            if model_limit > 1_000_000:
                model_limit = max_tokens

        self._model_limit = int(model_limit)
        self._budget = min(max_tokens, self._model_limit)
        if self._budget < max_tokens:
            logger.warning(
                f"{model_name} truncates at {self._model_limit} tokens; "
                f"clamping chunk budget from {max_tokens} to {self._budget}"
            )

    def count(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False))

    @property
    def budget(self) -> int:
        return self._budget

    @property
    def model_limit(self) -> int:
        """The hard truncation point. Exceeding it loses text silently."""
        return self._model_limit


@lru_cache(maxsize=4)
def get_token_counter(model_name: str | None = None, max_tokens: int | None = None) -> TokenCounter:
    return HFTokenCounter(
        model_name or settings.embedding.model,
        max_tokens or settings.chunking.max_tokens,
    )
