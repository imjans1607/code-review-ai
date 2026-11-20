# Automated Code Review AI with Vulnerability & Style Feedback
## First Review — Report Content

> Use this as the source text for the review document (.docx). Section numbers match the
> required template. Headings, tables, and the architecture figure are ready to paste;
> replace the bracketed `[...]` placeholders (names, register numbers, guide) with the
> actual details.

---

## ABSTRACT

Modern software development is fast, large-scale, and security-critical, yet code review —
one of the most effective quality-assurance practices — remains slow, manual, and dependent
on senior-developer availability. Recent research has begun to automate parts of this work
using large **Code Language Models (CLMs)**. The base paper for this project,
*"Generating Vulnerability Security Fixes with Code Language Models"* (Elsevier, *Information
and Software Technology*, 2025), uses such models to automatically **generate security
patches** for vulnerable source code. It is an important step, but it addresses only one
slice of review: it repairs known vulnerabilities and stops there — it gives no coding-style
or maintainability feedback, is an offline research model with no GitHub or CI/CD
integration, offers limited developer interaction, has no analytics, and does not combine
code-quality review with security in a single workflow.

This project, **Automated Code Review AI with Vulnerability & Style Feedback**, extends that
base work into a complete, deployable review platform. It combines an AI review model (a
CodeT5-family model fine-tuned on the CodeReviewer dataset) that generates human-like style
and logic comments, with a static-analysis security engine (Semgrep) that detects
vulnerabilities such as SQL injection, cross-site scripting, hard-coded secrets, path
traversal, and insecure `eval`, each mapped to its CWE. A fusion engine merges the two,
removes duplicates, ranks everything by severity, and attaches a short rationale to each
comment. The whole pipeline is triggered automatically on a GitHub pull request through
GitHub Actions, posts its review back as inline comments, and records every review in an
analytics dashboard.

The AI review layer has been implemented and evaluated as the first milestone, measured with
the same official BLEU metric used by the reference CodeReviewer work so the comparison is
honest and directly comparable. This report covers the literature that motivates the design,
the requirements and feasibility of the system, and its architecture, methodology, modules,
and estimated cost.

**Keywords:** automated code review, Code Language Models, CodeT5, static analysis, Semgrep,
vulnerability detection, CI/CD, GitHub Actions, developer tooling.

---

## 1. INTRODUCTION

Code review is a cornerstone of software quality. When a developer proposes a change, a
reviewer reads it and comments on correctness, readability, maintainability, and security.
Review reliably catches defects before they reach production and spreads knowledge across a
team — but it costs scarce human time, creates bottlenecks, varies with reviewer experience,
and is often skipped by small or fast-moving teams.

This has driven strong interest in **automating code review** using machine learning. Modern
approaches build on **large pre-trained models of source code** — CodeBERT, CodeT5, and their
successors — which learn general representations of code and can be fine-tuned for specific
tasks. One line of this research targets **security**: the project's base paper,
*"Generating Vulnerability Security Fixes with Code Language Models"* (Elsevier, 2025), trains
Code Language Models on pairs of vulnerable and patched code so the model can understand a
vulnerability and generate a secure fix, reducing the manual effort of remediation.

Valuable as that is, it solves only part of the problem a real reviewer handles. The base
paper's system:

1. **focuses on vulnerability repair, not complete review** — it fixes security bugs but says
   nothing about style, readability, or maintainability;
2. **gives no coding-style feedback**;
3. **has no GitHub pull-request integration** — it runs offline on benchmark data, not on real
   changes;
4. **has no CI/CD automation**;
5. **offers limited developer interaction** — a fix, without an explained review dialogue;
6. **has no analytics dashboard** to track quality over time; and
7. **does not unify code-quality review with security** in one place.

The goal of this project is to close those gaps by building a practical, end-to-end automated
code-review system. Concretely, it:

- **generates natural review comments** on a code change using a CodeT5-family model
  (`microsoft/codereviewer`) fine-tuned on the CodeReviewer dataset (Python and JavaScript);
- **detects security vulnerabilities** in the same change with the Semgrep static-analysis
  engine, reporting each with a severity and CWE;
- **fuses and explains** the two streams — de-duplicating, severity-ranking, and attaching a
  short rationale to every comment;
- **integrates into CI/CD** so review runs automatically on a pull request via GitHub Actions,
  returning inline comments; and
- **records and visualizes** every review in a dashboard (history, severity distribution,
  trends).

The first review milestone reported here delivers the **AI review layer** end-to-end — a
reproducible data-preparation and training pipeline, a baseline-versus-fine-tuned comparison,
and an evaluation against the reference model's own metric — and lays out the security,
fusion, CI/CD, and dashboard modules that complete the system.

---

## 2. LITERATURE SURVEY

The survey covers four strands relevant to the system: (a) pre-trained models of code, (b)
automated review-comment generation, (c) AI for vulnerability repair (the base paper's area),
and (d) static analysis for security.

**(a) Pre-trained models of source code.** *CodeBERT* (Feng et al., 2020) adapted masked-
language-model pre-training to programming languages, giving strong code-understanding
representations but no text-generation head. *CodeT5* (Wang et al., 2021) introduced an
identifier-aware encoder–decoder (text-to-text) model supporting both understanding and
generation, which makes it suitable for tasks that must *produce* text such as review
comments. *CodeT5+* (Wang et al., 2023) extended this family with flexible sizes and improved
pre-training. These models are the technical foundation for this project's AI review module.

**(b) Automated review-comment generation.** *CodeReviewer* (Li et al., 2022) pre-trains a
CodeT5-based model on a large multilingual corpus of real code changes and their review
comments mined from GitHub, and defines a review-comment-generation task. It is the current
reference point for generating review comments, and this project uses `microsoft/codereviewer`
as the base model for its AI review layer. Tufano et al. (2021, 2022) framed related code-
review recommendation tasks as sequence-to-sequence problems.

**(c) AI for vulnerability repair (base paper).** The project's base paper,
*"Generating Vulnerability Security Fixes with Code Language Models"* (Elsevier, *Information
and Software Technology*, 2025; DOI 10.1016/j.infsof.2025.107786), proposes a framework that
uses Code Language Models to automatically generate secure fixes for vulnerable code. Rather
than only detecting a vulnerability, the model reads the code context, identifies the security
issue, and produces a patched version, trained on large datasets of vulnerable/patched code
pairs and evaluated by comparing generated fixes against human-written patches. Its objectives
are to detect vulnerable code, generate AI-based fixes, reduce manual remediation effort, and
assist secure development. It is a strong contribution to automated *repair* — and the
starting point this project extends toward full review (see §2.2).

**(d) Static analysis and security detection.** Tools such as **Semgrep**, CodeQL, and Bandit
detect security-relevant patterns (injection, unsafe deserialization, hard-coded secrets) with
rule sets mapped to CWE identifiers. They are precise and explainable for known vulnerability
classes but produce no natural-language review discussion, and are usually run separately from
any AI review.

**Metrics note.** Review-comment quality is reported with **BLEU-4** against the human
reference comment, using the CodeReviewer project's smoothed-BLEU script. Published BLEU on
this task is inherently low (single digits) because a semantically correct comment often shares
almost no words with the reference ("Why was this removed?" vs. "Why this deletion?"); recent
work (*"Too Noisy To Learn"*, arXiv:2502.02757) confirms these datasets are noisy and scores
are low by nature. This project therefore benchmarks against the CodeReviewer reference (~5.73)
and reports the honest, comparable number alongside qualitative examples.

### 2.1 Inferences from Literature Survey

- **Transformers are the right foundation.** Encoder–decoder code models (CodeT5 /
  CodeReviewer) are the established approach for generating review comments and provide
  pre-trained weights that make fine-tuning feasible on modest hardware.
- **The base paper proves CLMs work for security — but only for repair.** Its success at
  generating fixes is exactly why extending the same family of models toward *full review*
  (style + security + workflow) is a natural, well-founded next step.
- **The diff must be encoded, not treated as plain text.** CodeReviewer feeds the model the
  *change* with explicit added/deleted/kept line markers; models given raw diff text perform
  far worse.
- **Security is best handled by a dedicated engine.** Static analysers (Semgrep) give precise,
  CWE-mapped, explainable findings, which complement the AI model rather than competing with
  it — motivating a hybrid design.
- **Evaluation must use the reference metric.** Review-comment BLEU is low by nature; only the
  CodeReviewer smoothed-BLEU script gives a comparable number, and qualitative before/after
  examples are essential alongside it.

### 2.2 Limitations & Research Gaps in Existing System

The base paper (Elsevier 2025) automates vulnerability *repair* but leaves several concrete
gaps for a complete review system. This project is designed around closing them:

| # | Limitation of the base paper | This project's improvement |
|---|---|---|
| 1 | Focuses on vulnerability **repair**, not complete review | Full review: AI style/logic comments **and** security detection |
| 2 | No **coding-style** feedback | CodeReviewer-based comments on style, readability, maintainability |
| 3 | No **GitHub pull-request** integration | Runs on real PRs; posts inline comments |
| 4 | No **CI/CD** automation | GitHub Actions workflow triggers review on every PR |
| 5 | **Limited developer interaction** / no explanation | Explainable comments — each carries a short rationale |
| 6 | No **analytics dashboard** | React dashboard: history, severity distribution, trends |
| 7 | No **unified** code-quality + security review, no severity ranking | Fusion engine merges both and ranks Critical → Informational |

**A note on evaluation targets.** Review-comment generation has a low natural ceiling on BLEU:
the reference model (`microsoft/codereviewer`) scores about **5.73**, and state-of-the-art
gains on this task are fractions of a point (refs: CodeReviewer paper; *"Too Noisy To Learn"*,
arXiv:2502.02757). This project reports BLEU honestly against that ~5.73 reference and locates
its value in the seven differentiators above rather than in a single headline number. BLEU also
undercounts semantically-correct comments that reword the reference.

---

## 3. REQUIREMENTS ANALYSIS

### 3.1 Feasibility Study and Risk Assessment

**Technical feasibility.** The building blocks are mature and open: pre-trained CodeReviewer /
CodeT5 weights (Hugging Face), the public CodeReviewer dataset (Zenodo), the Semgrep
open-source engine, the FastAPI web framework, and GitHub Actions. Fine-tuning a
~220M-parameter model is achievable on a single cloud GPU. The AI review layer has already
been trained and evaluated end-to-end, which de-risks the most uncertain part of the project.

**Economic feasibility.** All frameworks, models, and datasets are free and open-source. The
only recurring cost is GPU time for fine-tuning, obtained through a low-cost cloud notebook
subscription (Google Colab Pro). No paid APIs, licences, or servers are required for a
demonstrable prototype (detailed in §4.4).

**Operational feasibility.** The system fits the existing developer workflow — it activates on
a pull request and returns comments where developers already read them — so adoption requires
no behavioural change. For the review demonstration, the pipeline runs on demand and returns a
review in seconds.

**Schedule feasibility.** The work is phased so the highest-risk component (the AI model) is
delivered first, with the security, fusion, CI/CD, and dashboard modules layered on afterwards.
This guarantees a working, demonstrable milestone independent of the later modules.

**Risk assessment.**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GPU session times out / crashes mid-training | Medium | High | Checkpoint after every epoch to cloud storage; resume from the last checkpoint (already exercised successfully after a real power outage — no retraining needed). |
| BLEU expectations unrealistic for the task | High | Medium | Benchmark against the literature's ~5.73 reference; report the honest, comparable number plus qualitative examples. |
| Dataset schema surprises (missing language labels) | Medium | Medium | Inspect the real data at runtime before filtering; train on the full multilingual pool, evaluate on the Python/JS split. |
| Environment/version incompatibility (tokenizer, library) | Medium | Medium | Pin exact library versions known to work; document them. |
| Static-analysis false positives | Medium | Low | Severity-rank and de-duplicate in the fusion engine; tune the Semgrep rule set. |
| Semgrep tooling on Windows | Low | Low | Run Semgrep on the Linux CI runner (GitHub Actions) where it is fully supported. |

### 3.2 Software Requirements Specification

**Functional requirements.**

- **FR1 — Comment generation:** given a code change in Python or JavaScript, generate one or
  more natural-language review comments.
- **FR2 — Security detection:** scan the change with a static-analysis engine and report
  vulnerabilities with a rule name, severity, and CWE reference.
- **FR3 — Fusion & rationale:** merge the AI and security outputs, remove duplicates, rank by
  severity, and attach a short rationale to each item.
- **FR4 — CI/CD trigger:** run automatically when a pull request is created or updated, via
  GitHub Actions.
- **FR5 — Output surfaces:** return results as inline pull-request comments and expose them
  through a dashboard.
- **FR6 — Persistence & analytics:** store review results and present history, severity
  distribution, and trends.

**Non-functional requirements.**

- **NFR1 — Performance:** review a change end-to-end in under ~60 seconds; the demo responds in
  a few seconds.
- **NFR2 — Reproducibility:** training and evaluation reproducible from a committed notebook
  with pinned dependencies and fixed splits.
- **NFR3 — Comparability:** model quality measured with the reference paper's own BLEU script.
- **NFR4 — Portability:** GPU work runs on a cloud notebook, keeping the local machine free;
  the backend runs on a standard developer machine.
- **NFR5 — Maintainability:** modular design, each stage independently testable behind a clear
  interface.

**Hardware & software requirements.**

- *Model training:* Cloud GPU notebook (Google Colab Pro, L4-class GPU); Python 3; PyTorch;
  Hugging Face Transformers (pinned), Datasets, Accelerate; the CodeReviewer dataset.
- *Backend & tooling:* FastAPI + Uvicorn; SQLite (development) → PostgreSQL (optional);
  Semgrep (open-source); GitHub Actions for CI/CD.
- *Frontend:* React + Vite + Tailwind CSS dashboard.
- *Local development machine:* Windows 11, Python 3.11 (the heavy ML stack stays on the cloud,
  not the local GPU).

---

## 4. DESCRIPTION OF PROPOSED SYSTEM

The proposed system is an automated code-review assistant that reviews a code change the moment
a developer proposes it, combining a learned review-comment generator with a security scanner
and returning ranked, explained feedback inside the developer's normal workflow — extending the
base paper's vulnerability-repair model into a complete, deployable review platform.

### 4.1 Selected Methodologies

- **Transfer learning with a diff-pre-trained transformer.** The review-comment generator is
  built by fine-tuning `microsoft/codereviewer` — a CodeT5-family encoder–decoder already
  pre-trained on code changes and reviews — on the CodeReviewer dataset's comment-generation
  task. This gives a fair, published baseline for the AI review module.
- **Structured diff encoding.** Each changed line is prefixed with an explicit edit marker —
  `<add>`, `<del>`, or `<keep>` — so the model sees the *structure* of the change rather than
  raw diff text. This encoding materially improves comment quality.
- **Multilingual training, focused evaluation.** The model is trained on the full multilingual
  comment corpus (≈117k changes) for maximum review signal, but **evaluated on the Python +
  JavaScript test split** to match the project's language scope.
- **Honest, comparable evaluation.** Quality is measured with the official CodeReviewer
  smoothed-BLEU script, reported with and without stop-word removal, and supported with
  qualitative before/after examples.
- **Hybrid AI + static analysis.** Security detection uses the Semgrep rule engine rather than
  asking the model to "guess" vulnerabilities, giving precise, CWE-mapped, explainable findings
  that are then fused with the AI comments.
- **Incremental, testable delivery.** Each stage (data → model → security → fusion → API →
  CI/CD → dashboard) is an independently testable unit, so the AI review layer can be
  demonstrated before the later modules exist.

### 4.2 Architecture Diagram

```
        ┌───────────────────────────────────────────────┐
        │                 GitHub Pull Request            │
        └───────────────────────┬───────────────────────┘
                                │  (Actions: on PR create / update)
                                ▼
                   Extract diff + changed files + language   (Module 1)
                                │
                                ▼  POST /review
    ┌──────────────────────── FastAPI Backend ───────────────────────┐
    │                                                                 │
    │   ┌───────────────────────┐        ┌──────────────────────┐     │
    │   │  AI review model       │        │   Semgrep security    │    │
    │   │ (CodeReviewer, fine-   │        │   scan → findings     │    │
    │   │  tuned; style + logic) │        │  (rule, severity, CWE)│    │
    │   │      (Module 2)        │        │      (Module 3)       │    │
    │   └───────────┬───────────┘        └───────────┬──────────┘     │
    │               │                                │                 │
    │               └──────────────┬─────────────────┘                │
    │                              ▼                                   │
    │        Fusion engine: de-duplicate + severity-rank               │
    │              + attach rationale to each comment   (Module 4)     │
    │                              │                                   │
    │                     Persist (SQLite / PostgreSQL)                │
    └──────────────────────────────┬──────────────────────────────────┘
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
      Inline PR comments (Module 5)      React analytics dashboard (Module 6)
```

*Figure 4.1 — End-to-end architecture. The AI review layer (Module 2) and the Semgrep security
layer (Module 3) run on the same change and are merged, ranked, and explained by the fusion
engine (Module 4) before being posted to the PR (Module 5) and recorded in the dashboard
(Module 6).*

### 4.3 Module Description and Workflow

The idea doc defines six modules; the system implements each as an independent, testable unit.

| Module | Description |
|---|---|
| **M1 — Intelligent Code Collection** | Extract the changed files, diff, and language from a pull request. |
| **M2 — AI Code Review** | Fine-tuned CodeReviewer model generates natural style/logic comments from the change. |
| **M3 — Security Vulnerability Detection** | Semgrep scans the code and emits findings (rule, severity, CWE, OWASP). |
| **M4 — Review Fusion & Prioritization** | Merge M2 + M3, de-duplicate, rank by severity, attach a rationale. |
| **M5 — Automated CI/CD Review** | GitHub Actions runs the pipeline on a PR and posts inline + summary comments. |
| **M6 — Analytics Dashboard** | React dashboard for review history, severity distribution, and trends. |

**Workflow.** (1) A developer opens or updates a pull request. (2) GitHub Actions extracts the
changed files, the diff, and the language (M1). (3) The change runs through the fine-tuned
review model (M2) **and** the Semgrep scanner (M3). (4) The fusion engine de-duplicates and
severity-ranks the combined findings and attaches a rationale to each (M4). (5) Results are
posted back as inline pull-request comments (M5), persisted, and surfaced in the dashboard (M6)
— all within the target latency.

**First-milestone result (AI review layer).** The comment-generation model has been fine-tuned
(full training set, three epochs) and evaluated on the Python/JavaScript test split using the
reference paper's own BLEU script. It scores **above the published CodeReviewer reference**, and
qualitatively produces genuine, on-topic reviewer comments (for example, "nit: this import
should be grouped with the other imports" and "Why was this removed?"). The baseline model,
before fine-tuning, produced irrelevant output (e.g. echoing licence headers), giving a clear
before/after contrast. Per-epoch checkpointing allowed the run to be recovered after a real
power outage with no retraining — evidence of a robust, reproducible pipeline.

### 4.4 Estimated Cost for Implementation and Overheads

The system is built entirely from open-source components; the only real expenditure is cloud
GPU time for model fine-tuning. All figures are indicative for a student project.

| Item | Basis | Estimated cost |
|---|---|---|
| Cloud GPU notebook (Google Colab Pro) | ~1–2 months at ≈ ₹1,000 / month for fine-tuning + iteration | ₹1,000 – ₹2,000 |
| Pre-trained model weights (CodeReviewer / CodeT5) | Open-source, Hugging Face | ₹0 |
| CodeReviewer dataset | Open (Zenodo) | ₹0 |
| Semgrep (security engine) | Open-source (OSS edition) | ₹0 |
| FastAPI, React, Tailwind, GitHub Actions | Open-source / free tier | ₹0 |
| Model & artifact hosting (Hugging Face Hub / demo) | Free tier | ₹0 |
| Source hosting & CI minutes (GitHub) | Free tier for public/student use | ₹0 |
| Local development machine | Already owned; ML stack runs on the cloud | ₹0 |
| **Total direct cost** | | **≈ ₹1,000 – ₹2,000** |

**Overheads (non-monetary).** Development effort across the phased modules; GPU compute-time
for training and re-training experiments; and the human time to prepare the data, evaluate
results, and integrate the modules. Because training runs on a cloud GPU, there is **no local
hardware cost or wear**, and the local machine stays free for development. A future production
deployment (persistent hosting, PostgreSQL, always-on webhook) would add recurring server cost
but is out of scope for the demonstrable prototype delivered here.

---

*End of first-review content.*
