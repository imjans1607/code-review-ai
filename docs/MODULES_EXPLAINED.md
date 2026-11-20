# Understanding the Project — Module by Module

A plain-English guide to how the **Automated Code Review AI** works. Read it top to
bottom — no prior knowledge needed. By the end you'll be able to explain every part of
the project in your own words.

---

## 1. The big picture (start here)

When a developer changes some code and wants to add it to a shared project, they open a
**pull request (PR)** — basically a "please review and accept my change" request on
GitHub. Normally another developer reads it and leaves comments. That's **code review**,
and it's slow and depends on someone being available.

**This project automates code review.** The moment a pull request appears, the system:

1. reads the code change,
2. writes **review comments** about style and logic (using an AI model),
3. scans for **security vulnerabilities** (using a security tool),
4. **merges** both into one ranked list with explanations,
5. **posts** it back on the pull request automatically, and
6. **records** it in a **dashboard** so you can see trends over time.

The whole thing is split into **6 modules** — each one does a single job and hands its
result to the next:

```
  Pull Request
      │
      ▼
 [1] Collect the change ──►  [2] AI writes review comments ─┐
                            [3] Security scanner finds bugs ─┤
                                                             ▼
                                          [4] Merge + rank + explain
                                                             │
                             ┌───────────────────────────────┤
                             ▼                               ▼
                   [5] Post on the PR              [6] Save to dashboard
```

### The one idea to understand first: "the diff"

A **diff** is the standard way to describe a code change. It shows only the lines that
changed: a `+` means a line was **added**, a `-` means a line was **removed**, and a
plain line is **unchanged context**. Example:

```
  def get_user(conn, username):
-     cur.execute("SELECT * FROM users WHERE name = '" + username + "'")
+     cur.execute("SELECT * FROM users WHERE name = ?", (username,))
      return cur.fetchone()
```

Almost everything in this project revolves around reading a diff. Keep this picture in
mind and the rest is easy.

---

## 2. A few terms you'll see (2-minute primer)

- **Pull request (PR):** a proposed code change on GitHub, waiting to be reviewed and merged.
- **Diff / hunk:** a diff is the change; a **hunk** is one continuous block of changed lines within a file (a file can have several hunks).
- **AI model / fine-tuning:** an AI model is trained on lots of examples. **Fine-tuning** means taking a model that already understands code and training it a bit more on our specific task (writing review comments), so it gets good at exactly that.
- **Static analysis / Semgrep:** "static" means analysing code *without running it*. **Semgrep** is a free tool that scans code for known dangerous patterns.
- **CWE:** a **Common Weakness Enumeration** id — a standard catalogue number for a type of security flaw (e.g. **CWE-89** = SQL injection). It makes findings precise and looked-up-able.

---

## 3. The six modules

Each section: **In one line → What it does → How it works → Where it lives → Why it matters.**

### Module 1 — Intelligent Code Collection

**In one line:** turns a messy code change into clean, structured data.

**What it does:** reads the pull request's diff and figures out, for each file: what
**language** it is (Python or JavaScript), and exactly which lines were **added, removed,
or kept**.

**How it works:** it walks through the diff text line by line. A line starting with `+`
is tagged "added", `-` is "removed", a space is "kept". It also reads the filename's
extension (`.py`, `.js`) to decide the language, and keeps a running line-number counter
so it knows *where* each change is (e.g. "line 11 of login.py"). The result is a tidy
list of objects the other modules can use without ever parsing text again.

**Where it lives:** `backend/app/collector/`

**Why it matters:** it's the front door. Every later module works on *its* clean output,
so getting the change parsed correctly once means nothing else has to deal with raw text.

### Module 2 — AI Code Review

**In one line:** an AI writes human-like review comments about the change.

**What it does:** looks at a code change and produces a natural-language comment, like
*"nit: this import should be grouped with the others"* — the kind of thing a human
reviewer would say about style and logic.

**How it works:** it uses a model called `microsoft/codereviewer` (from the CodeT5
family, already trained on millions of real code changes and reviews) that we
**fine-tuned** on a large dataset of code-review comments. Before the model reads a
change, each line is re-labelled with a marker — `<add>`, `<del>`, or `<keep>` — so the
model clearly sees *what kind* of change each line is (the model was trained on this exact
format). It then generates a short comment.

**Where it lives:** `backend/app/reviewer/` (using the model published on Hugging Face;
the training itself is in `ml/notebooks/`).

**Why it matters:** this is the "AI" in the project — it gives the flexible,
human-sounding feedback that fixed rules can't.

### Module 3 — Security Vulnerability Detection

**In one line:** finds security bugs and labels each with how serious it is.

**What it does:** scans the changed code for dangerous patterns — **SQL injection,
cross-site scripting (XSS), hard-coded passwords/API keys, path traversal, and insecure
`eval()`** — and reports each one with a severity and a CWE number.

**How it works:** it runs **Semgrep**, an industry security scanner with hundreds of
rules (covering the OWASP Top 10, the well-known list of web risks). Semgrep outputs its
findings as data; this module reads that output and turns it into clean findings
(rule, message, severity, file, line, CWE). Semgrep does the detecting; our module drives
it and tidies the results.

**Where it lives:** `backend/app/security/`

**Why it matters:** the AI model handles style; **security needs precision**. A dedicated
scanner with known rules is exact and explainable — you always know *which* rule fired and
*why*.

### Module 4 — Review Fusion & Prioritization

**In one line:** merges the AI comments and the security findings into one ranked list.

**What it does:** takes the two separate streams (Module 2's comments + Module 3's
findings), removes duplicates, **ranks everything by severity** (Critical → High → Medium
→ Low → Informational), and attaches a short **rationale** ("why this matters") to each
one.

**How it works:** both a style comment and a security finding are converted into one
common shape. If a style comment and a security finding land on the *same line*, the
security one wins (it's the more important thing to say about that line). Then the whole
list is sorted so the scariest issues appear first, and each gets its explanation.

**Where it lives:** `backend/app/fusion/`

**Why it matters:** a developer shouldn't get two separate, unordered reports. This module
produces the single, prioritized, explained review that a person actually reads.

### Module 5 — Automated CI/CD Review

**In one line:** runs the whole pipeline automatically on every pull request and posts the result.

**What it does:** the moment a pull request is opened, it triggers the review (no human
presses anything) and posts the comments back **onto the pull request**, both as a summary
and as inline notes on the exact lines.

**How it works:** it uses **GitHub Actions** — GitHub's built-in automation. A small
configuration file (`.github/workflows/code-review.yml`) says "when a PR opens, do these
steps": grab the change, run Semgrep, run the review pipeline, and post the results using
GitHub's API. ("CI/CD" just means automation that runs on every code change.)

**Where it lives:** `.github/workflows/`, `scripts/run_review.py`, `backend/app/publisher/`

**Why it matters:** this is what makes it *real*. Without it, the reviewer is just a script
someone has to run. With it, reviews happen automatically, where developers already work.

### Module 6 — Analytics Dashboard

**In one line:** a web page that shows the review history and trends.

**What it does:** every review is saved, and a dashboard displays the totals, a chart of
findings by severity, a trend line over time, and a searchable table of past reviews —
with filters by **author, severity, and file**.

**How it works:** the backend saves each review into a small **SQLite** database (a
single-file database, no setup). It exposes that data through simple web addresses
(`/reviews`, `/stats`). The dashboard — built with **React** (a popular tool for building
web pages) — reads those and draws the cards, charts, and table.

**Where it lives:** `backend/app/storage.py` (saving) and `frontend/` (the web page).

**Why it matters:** one review is useful; seeing patterns over time ("are we getting more
secure?", "who needs help?") is where a team gets real value.

---

## 4. How it all fits together (follow one change through the system)

Say a developer opens a pull request that changes `login.py` and accidentally builds a
database query by gluing strings together (a classic SQL-injection bug), and also leaves a
hard-coded API key.

1. **Module 1** reads the diff → "1 Python file changed, here are the added lines."
2. **Module 2** (AI) looks at the change → writes a style/logic comment.
3. **Module 3** (Semgrep) scans it → finds **SQL injection (CWE-89, Critical)** and a
   **hard-coded secret (CWE-798, Critical)**.
4. **Module 4** merges them, ranks the two Criticals to the top, and adds a rationale to
   each.
5. **Module 5** posts the ranked review right onto the pull request, inline on the risky
   lines.
6. **Module 6** saves the review so it shows up on the dashboard's charts and trend line.

All of it happens automatically, in seconds, the moment the pull request appears.

---

## 5. How good is it? (the results, explained simply)

- **AI review quality:** measured with **BLEU** (a standard score for how close generated
  text is to a human's). Our fine-tuned model scores **7.26**, *above* the best published
  model for this task (~5.73). **Important:** BLEU scores on review comments are *always*
  low (single digits) — because two comments can mean the same thing in totally different
  words (*"Why was this removed?"* vs *"Why this deletion?"* share almost no words). So a
  small number here is normal, and beating the published model is a genuine result.
- **Security:** correctly detects all five promised vulnerability types (SQL injection,
  XSS, hard-coded secrets, path traversal, insecure `eval`), each ranked and CWE-tagged.
- **End to end:** the AI model is published and public, the dashboard runs live, and
  reviews post automatically on real pull requests.

---

## 6. Quick glossary

| Term | Plain meaning |
|---|---|
| **Pull request (PR)** | A proposed code change on GitHub, waiting to be reviewed. |
| **Diff** | A description of a change: `+` added, `-` removed, space = unchanged. |
| **Hunk** | One continuous block of changed lines inside a file. |
| **CodeT5 / CodeReviewer** | AI models built to understand and write about code. |
| **Fine-tuning** | Extra training of a model on our specific task. |
| **BLEU** | A score for how close generated text is to a human reference. |
| **Semgrep** | A free tool that scans code for dangerous patterns. |
| **Static analysis** | Analysing code without running it. |
| **CWE** | A standard catalogue number for a type of security flaw. |
| **OWASP Top 10** | The well-known list of the biggest web security risks. |
| **Fusion** | Merging the AI comments and security findings into one list. |
| **Severity** | How serious an issue is: Critical → High → Medium → Low → Informational. |
| **CI/CD** | Automation that runs on every code change (here, on every PR). |
| **GitHub Actions** | GitHub's built-in automation that powers the CI/CD. |
| **FastAPI** | The Python framework running the backend/API. |
| **React** | The tool used to build the dashboard web page. |
| **SQLite** | A simple, single-file database. |

---

## 7. One-line cheat sheet (memorize these)

| Module | Say this |
|---|---|
| **1. Code Collection** | "Reads the pull request and extracts the changed files, language, and lines." |
| **2. AI Code Review** | "A fine-tuned AI model writes human-like style and logic comments." |
| **3. Security Detection** | "Semgrep scans for vulnerabilities and tags each with a CWE and severity." |
| **4. Fusion & Prioritization** | "Merges the AI and security results, removes duplicates, and ranks them by severity." |
| **5. CI/CD Review** | "GitHub Actions runs it automatically on every PR and posts the review inline." |
| **6. Dashboard** | "Saves every review and shows history, severity charts, and trends." |

If you can say those six sentences and explain "the diff," you understand the whole project.
