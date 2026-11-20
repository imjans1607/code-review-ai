# ML / Model Track (CodeT5+ on the CodeReviewer dataset)

All GPU work runs on **Google Colab**, not the local machine. The executed
notebooks (with cell outputs intact) are committed here as the proof-of-work
record required by TASKS.

## Layout

- `notebooks/` — self-contained Colab notebooks (mount Drive / download data →
  prep → baseline / fine-tune → evaluate → export weights).
- `scripts/` — reusable helpers mirrored into notebook cells where useful.

## Model & data (locked defaults)

- **Base model:** `Salesforce/codet5p-220m` (encoder-decoder; smallest CodeT5+
  variant — fast to iterate. Scale to `codet5p-770m` for final metrics if the
  ≥18 BLEU-4 / ≥22 CodeBLEU targets aren't met).
- **Reference baseline (report only):** `microsoft/codereviewer` — the base
  paper's own model, for an apples-to-apples comparison point.
- **Dataset:** CodeReviewer, **`msg` (comment-generation)** sub-task, subset to
  **Python + JavaScript**. Official data on Zenodo; HF mirrors exist.

## Targets (⚠️ recalibrated) & result

| Metric | Idea-doc target | Reality (comment-generation) | **Our result** |
|---|---|---|---|
| BLEU-4 (official CodeReviewer `smooth_bleu`, rmstop=True) | ≥ 18 (baseline "14.8") | **≥18 not achievable.** Paper `microsoft/codereviewer` = **~5.73**; SOTA gains ~0.4–0.5. | **7.26** (above paper) ✅ |
| CodeBLEU | ≥ 22 | Applies to code *refinement*, not comment generation. | n/a |

Model: `microsoft/codereviewer` fine-tuned on the `msg` task with `<add>/<del>/<keep>`
markers, full 117k train / 3 epochs, evaluated on the Python/JS test split (2,370).
Vanilla CodeT5+ on raw diffs scored ~1 BLEU (kept as an ablation).

**Finding (2026-07-28):** the idea doc's BLEU-4 ≥18 / baseline 14.8 is miscalibrated —
no known model reaches 18 on review-comment generation; the realistic ceiling is
~5–6. The "14.8" was likely conflated with the code-*refinement* task. Refs:
CodeReviewer paper; "Too Noisy To Learn" (arXiv:2502.02757, Table III). We report
smoothed BLEU-4 against the ~5.7 reference and lean the project's value on the 4
differentiators (security, CI/CD, rationale, JS).

## Phase status

- **Phase 1:** data prep + baseline inference — `notebooks/01_data_prep_and_baseline.ipynb` (authored; run on Colab)
- **Phase 2:** fine-tuning + evaluation + optional HF Hub upload — `notebooks/02_finetune_and_evaluate.ipynb` (authored; run after Phase 1)
- **Demo:** live presentation notebook — `notebooks/03_demo_inference.ipynb` (paste code → get a review comment; loads the fine-tuned model, no dataset/training)

## Run order on Colab

1. `01_data_prep_and_baseline.ipynb` → writes prepared Python/JS splits + baseline examples to Drive (`code-review-ai/`).
2. `02_finetune_and_evaluate.ipynb` → fine-tunes CodeT5+, evaluates BLEU-4 (+CodeBLEU caveat), exports weights + "after" examples. Set `PUSH_TO_HF=True` (with an HF write token) to publish the model for the demo.
3. `03_demo_inference.ipynb` → set `HF_MODEL_ID` (or `LOCAL_WEIGHTS`) to the fine-tuned model, *Run all*, paste code in the box → live review comment.

Report back the printed split sizes, BLEU-4, training config, and before/after examples so the BUILD_LOG entries can be filled with real numbers.

## Presentation demo

The student runs `03_demo_inference.ipynb`: *Run all*, then paste a Python/JS snippet
and click **Review this code** — the model responds in seconds (works on CPU, no
dataset download). Pre-filled examples also run automatically as a safety net.
Requires the fine-tuned model to be reachable: either published to the **HF Hub**
(recommended — the student needs no auth for a public model) or loaded from a shared
Drive path. Creating the HF account + token is a one-time human step (not automated).
