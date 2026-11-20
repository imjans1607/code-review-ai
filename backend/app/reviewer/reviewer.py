"""Load the fine-tuned review model and generate review comments.

This wraps the Hugging Face model in one small class, `AICodeReviewer`, with a
single job: given a code change, return a reviewer comment. It is the same
model and the same input encoding used during training (notebook 04/05), so the
comments here match what we measured with BLEU.

The heavy libraries (torch, transformers) are imported lazily inside the class
so that simply importing this module — e.g. for the teaching walkthrough — does
not require the ML stack to be installed.
"""

from __future__ import annotations

from typing import List, Optional

from .diff_encoder import format_diff

# The model we fine-tuned. Point `model_path` at a local weights folder or a
# Hugging Face Hub id. The base id is only used as a fallback for the tokenizer.
DEFAULT_MODEL = "microsoft/codereviewer"
MAX_SOURCE_TOKENS = 512   # longest diff (in tokens) the model reads
MAX_COMMENT_TOKENS = 128  # longest comment the model writes
NUM_BEAMS = 4             # beam search = steadier, less random comments


class AICodeReviewer:
    """Turns a code change into a natural-language review comment."""

    def __init__(self, model_path: str = DEFAULT_MODEL, device: Optional[str] = None):
        # Imported here (not at top of file) so the module can be read/taught
        # without torch + transformers installed.
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._torch = torch

        # The fine-tuned checkpoint ships its own (marker-aware) tokenizer.
        # Fall back to the base tokenizer and re-add the markers if missing.
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained(DEFAULT_MODEL)
            self._ensure_markers()

        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
        self.model.to(self.device).eval()

    def _ensure_markers(self) -> None:
        """Guarantee the <add>/<del>/<keep> tokens exist in the tokenizer."""
        markers = ["<add>", "<del>", "<keep>"]
        missing = [
            m for m in markers
            if self.tokenizer.convert_tokens_to_ids(m) == self.tokenizer.unk_token_id
        ]
        if missing:
            self.tokenizer.add_special_tokens({"additional_special_tokens": missing})

    def review(self, patch: str) -> str:
        """Generate a single review comment for one diff/patch."""
        return self.review_batch([patch])[0]

    def review_batch(self, patches: List[str], batch_size: int = 8) -> List[str]:
        """Review many patches at once (more efficient than one-by-one)."""
        encoded_inputs = [format_diff(p) for p in patches]
        comments: List[str] = []

        with self._torch.no_grad():  # inference only — no gradients needed
            for i in range(0, len(encoded_inputs), batch_size):
                chunk = encoded_inputs[i:i + batch_size]
                enc = self.tokenizer(
                    chunk,
                    max_length=MAX_SOURCE_TOKENS,
                    truncation=True,
                    padding=True,
                    return_tensors="pt",
                ).to(self.device)
                generated = self.model.generate(
                    **enc,
                    max_new_tokens=MAX_COMMENT_TOKENS,
                    num_beams=NUM_BEAMS,
                )
                comments.extend(
                    self.tokenizer.batch_decode(generated, skip_special_tokens=True)
                )
        return comments
