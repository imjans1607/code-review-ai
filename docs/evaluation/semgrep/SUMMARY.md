# Extending the Semgrep rule set — what it bought, and what it didn't

Measured 2026-11-18 with Semgrep 1.186.0. Targets: **precision > 90%**, **recall > 85%**.

## The short version

Extending the rule set **more than doubled recall on cases it was never tuned against
(26% → 58%) and lost nothing the baseline found**, but **both targets are still
missed** on the fair estimate (recall 58%, precision 85%). The 97% recall seen on
the suite used for tuning was mostly the config fitting that suite, not a property of
the rules.

## Three numbers, three meanings

| What | Suite | Config | Precision | Recall | How to read it |
|---|---|---|---|---|---|
| Baseline | dev | original 4 packs | 84.2% (16/19) [62–94%] | 43.2% (16/37) [29–59%] | the committed first measurement |
| Extended, **tuned on this suite** | dev | extended | 87.8% (36/41) [74–95%] | 97.3% (36/37) [86–100%] | **optimistic**: the config was built against these cases |
| Baseline | **holdout** | original 4 packs | 83.3% (10/12) [55–95%] | 26.3% (10/38) [15–42%] | the same cases scored once |
| Extended | **holdout** | extended | 84.6% (22/26) [66–94%] | **57.9% (22/38) [42–72%]** | **the fair estimate** |

Brackets are 95% Wilson intervals. The holdout (67 cases: 38 vulnerable, 29 safe) was
written and hashed before the extended config existed, uses different frameworks and
APIs from the dev suite, and was scored once per config. Protocol and hashes:
`backend/eval/semgrep_holdout/DESIGN.md`. Raw Semgrep output and per-case results for
every run are in the folders next to this file.

Paired on identical cases, the extended config **gained 12 detections and lost 0** on the
holdout (20 and 0 on dev).

## Where the held-out recall comes from, and where it doesn't

| Holdout recall | Baseline | Extended |
|---|---|---|
| framework-sourced (`request.*`, route params) | 50.0% (9/18) | 72.2% (13/18) |
| plain function parameter | 0.0% (0/10) | 30.0% (3/10) |
| browser source (`location.hash`, `localStorage`) | 0.0% (0/2) | 50.0% (1/2) |
| literal (secrets) | 12.5% (1/8) | 62.5% (5/8) |
| Python | 36.8% (7/19) | 73.7% (14/19) |
| JavaScript | 15.8% (3/19) | 42.1% (8/19) |

By class (holdout, baseline → extended): SQL injection 2/8 → 7/8, eval 3/6 → 5/6,
secrets 1/8 → 5/8, XSS 3/9 → 4/9, path traversal 1/7 → 1/7.

The 16 holdout misses fall into three groups:

1. **APIs the rules do not list (by design).** To keep the holdout honest, custom-rule
   sinks were limited to APIs the dev suite uses. The holdout uses their neighbours, so
   `outerHTML`, `insertAdjacentHTML`, jQuery `.html()`, `fs.createReadStream`,
   `res.download`, `fs.writeFile`, `tarfile.extractall`, `setTimeout(string)` and
   `knex.raw` are missed, as are FastAPI's `HTMLResponse`/`FileResponse` and React state in
   `dangerouslySetInnerHTML`. A real rule author would list these API families, so this
   group is the easiest recall to add, but it needs a new validation set (below).
2. **Secrets the packs do not recognise:** a Google API key in JavaScript and passwords
   inside connection URLs (Python and JavaScript). The Python Google key *was* found.
3. **Path building the rule does not model:** `open("/srv/reports/" + name)` concatenates
   instead of calling `os.path.join`, which is all the Python rule recognises.

## What it costs

* **Precision did not improve** (83% → 85%, within noise) and stays below 90%.
  False-positive findings went from 2 to 4 on the holdout, and the safe cases that still
  got a finding from 2/29 to 4/29. The two new ones are both cherry-picked registry audit
  rules firing on constants: `exec-detected` on `exec(compile("x = 1"))` and
  `sqlalchemy-execute-raw-query` on a query assembled only from constants. (The other two
  holdout false positives, path rules on `secure_filename`/`basename`-guarded code, were
  already there in the baseline.)
* On the dev suite the custom path rules added two false positives: the "resolve, then
  check the prefix" safe cases get flagged because that guard cannot be expressed as a
  sanitizer. They were left flagged rather than hidden with a sanitizer that would also
  suppress genuinely unguarded code.
* **Scan time** roughly doubles on small inputs: 6.6 s → 12.2 s on the holdout, 7.5 s →
  13.7 s on this repo's own code, but only 17.5 s → 18.9 s on 378 third-party files. Much of
  the difference is downloading more rule packs. Well inside the 60 s end-to-end target, but
  it is additive with the model's time.

## Does it make real code noisy?

On code with no known vulnerabilities the extended config produced **no extra findings**:

* this repository's own code (`backend/app`, `scripts`, `backend/tests`, `frontend/src`;
  56 files): 0 findings, baseline 0;
* 378 files of Starlette, FastAPI, httpx, uvicorn and Recharts: 5 findings, the identical 5
  as baseline (weak hashes, a disabled-autoescape setting and file permissions: CWE 327,
  116 and 276, none in the five target classes).

This is weak evidence: those codebases rarely use the sinks in question, and it does not
show how noisy the parameter-based rules are on application code that opens files or
builds queries from function arguments, which is where they are most likely to fire. A
spot check confirmed the extended rules were active: more than 900 rules loaded against
602 for the baseline.

## What changed in the product

* `DEFAULT_CONFIGS` (scanner), `.github/workflows/code-review.yml` and `action.yml` now run
  14 config entries instead of 4: the original packs, `p/security-audit`, `p/expressjs`,
  `p/gitleaks`, six individual rules from Semgrep's `p/default`, and four custom rules in
  `backend/app/security/rules/`. A test keeps the three lists identical.
* The custom rules are taint rules that treat function parameters and browser-controlled
  values as untrusted. They are marked low confidence and **Medium** severity, so they can
  never be promoted to Critical in PR summaries (also tested).
* `BASELINE_CONFIGS` keeps the original four so the first measurement stays reproducible.
* Two password-literal rules were written and **dropped**: they caught nothing on the dev
  suite, and a rule with no measured benefit and unknown noise should not ship.

## Limits of this result

* The suites are small (37 and 38 vulnerable cases), and the intervals show it.
* Semgrep's registry packs change over time and CI installs Semgrep unpinned, so a future
  run can differ. The raw outputs here are the evidence for these numbers. Pinning the
  Semgrep version in CI would be a sensible follow-up but is a product change.
* The suites are synthetic. Real pull requests mix far more code shapes.
* Changing the config now would invalidate the holdout for it; a test fails if the config
  changes without the recorded fingerprint being revisited.

## Where to go from here

1. **Broaden the sink families** (the first miss group) and re-measure on a *third*, fresh
   suite. This is the cheapest way to raise recall, and the held-out result says how much
   to expect from it.
2. **Raise precision** by modelling common guards or by keeping parameter-based findings
   out of the headline count. Precision, not recall, is now the nearer target (85% vs 90%).
3. **Revisit what the README claims** about the security layer. Neither target is met on
   the fair estimate.
