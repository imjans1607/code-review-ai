# Semgrep precision / recall — measured results

Run on 2026-11-18T04:03:35+00:00 with Semgrep 1.186.0 on Windows-10-10.0.26300-SP0.
Suite: `holdout`. Config set: `baseline` (the product's shipped config as of 2026-11-18).
Rule sources: `p/python`, `p/javascript`, `p/owasp-top-ten`, `p/secrets`.
Current `labels.json` sha256 `3ddaed4a7e0544fc…`.

## Headline

| Metric | Target | Measured | Result |
|---|---|---|---|
| Precision | > 90% | 83.3% (10/12; 95% CI 55–95%) | **not met** |
| Recall | > 85% | 26.3% (10/38; 95% CI 15–42%) | **not met** |

* Precision counting only findings in the five target classes: 83.3% (10/12; 95% CI 55–95%).
* Recall requiring the *right* class (CWE) as well: 23.7% (9/38; 95% CI 13–39%).
* Safe (fixed) cases that still got a finding: 6.9% (2/29; 95% CI 2–22%).

Raw counts: 38 vulnerable cases (10 detected, 28 missed), 29 safe cases, 2 false-positive findings (2 in the target classes), 5 duplicate findings on already-detected sinks.

## Recall by vulnerability class

| Class | Recall | False-positive findings |
|---|---|---|
| sqli | 25.0% (2/8; 95% CI 7–59%) | 0 |
| xss | 33.3% (3/9; 95% CI 12–65%) | 0 |
| secret | 12.5% (1/8; 95% CI 2–47%) | 0 |
| path_traversal | 14.3% (1/7; 95% CI 3–51%) | 2 |
| eval | 50.0% (3/6; 95% CI 19–81%) | 0 |

## Recall by how the untrusted value arrives

Most Semgrep security rules are taint rules that need a recognisable source (e.g. `request.args`). `bare_param` cases pass the value as a plain function argument, which is common in real code but gives such rules nothing to start from.

| Source | Recall |
|---|---|
| bare_param | 0.0% (0/10; 95% CI 0–28%) |
| browser_source | 0.0% (0/2; 95% CI 0–66%) |
| framework | 50.0% (9/18; 95% CI 29–71%) |
| literal | 12.5% (1/8; 95% CI 2–47%) |

## Recall by language

| Language | Recall |
|---|---|
| javascript | 15.8% (3/19; 95% CI 6–38%) |
| python | 36.8% (7/19; 95% CI 19–59%) |

## Missed vulnerabilities (false negatives)

| Case | Class | Source | What it is |
|---|---|---|---|
| `hj-eval-settimeout-string` | eval | bare_param | function argument passed to setTimeout as a string |
| `hj-eval-localstorage` | eval | browser_source | stored script text passed to eval |
| `hj-path-createreadstream` | path_traversal | framework | query value streamed straight from disk |
| `hj-path-res-download` | path_traversal | framework | query value passed to res.download |
| `hj-path-writefile` | path_traversal | framework | request body decides where a file is written |
| `hj-secret-google-key` | secret | literal | Google API key in source |
| `hj-secret-sendgrid` | secret | literal | SendGrid API key in source |
| `hj-secret-npm-token` | secret | literal | npm access token in source |
| `hj-secret-db-url-password` | secret | literal | database password embedded in a connection URL |
| `hj-sqli-pg-template` | sqli | framework | route parameter in a template-literal query |
| `hj-sqli-mysql2-concat` | sqli | bare_param | function argument concatenated into a query |
| `hj-sqli-knex-raw` | sqli | bare_param | function argument concatenated into knex.raw |
| `hj-xss-jquery-html-hash` | xss | browser_source | location.hash passed to jQuery .html() |
| `hj-xss-insert-adjacent-html` | xss | bare_param | function argument passed to insertAdjacentHTML |
| `hj-xss-outerhtml` | xss | bare_param | function argument assigned to outerHTML |
| `hj-xss-react-state` | xss | bare_param | component state rendered with dangerouslySetInnerHTML |
| `hp-eval-compile-exec` | eval | bare_param | function argument compiled and executed |
| `hp-path-fastapi-fileresponse` | path_traversal | framework | FastAPI path parameter built into a path and served |
| `hp-path-tar-extractall` | path_traversal | bare_param | archive extracted without checking member paths |
| `hp-path-open-concat` | path_traversal | bare_param | function argument concatenated into a path and opened |
| `hp-secret-google-api-key` | secret | literal | Google API key in source |
| `hp-secret-sendgrid-key` | secret | literal | SendGrid API key in source |
| `hp-secret-db-url-password` | secret | literal | database password embedded in a connection URL |
| `hp-sqli-fastapi-fstring` | sqli | framework | FastAPI query parameter formatted into SQL |
| `hp-sqli-psycopg2-percent` | sqli | bare_param | function argument %-formatted into a query |
| `hp-sqli-django-cursor-concat` | sqli | framework | request value concatenated into a raw cursor query |
| `hp-xss-django-mark-safe` | xss | framework | request value marked safe and returned |
| `hp-xss-fastapi-htmlresponse` | xss | framework | FastAPI parameter in an HTML f-string response |

## Detected

| Case | Rule(s) | Right class? |
|---|---|---|
| `hj-eval-vm-run` | `express-vm-injection` | yes |
| `hj-sqli-sequelize-query` | `express-sequelize-injection` | yes |
| `hj-xss-express-write` | `direct-response-write`, `raw-html-format` | yes |
| `hp-eval-flask-exec` | `exec-injection` | yes |
| `hp-eval-django-eval-post` | `user-eval` | yes |
| `hp-path-flask-open-form` | `path-traversal-open`, `path-traversal-open` | yes |
| `hp-secret-jwt-encode` | `jwt-python-hardcoded-secret` | no |
| `hp-sqli-sqlalchemy-text-fstring` | `tainted-sql-string`, `avoid-sqlalchemy-text` | yes |
| `hp-xss-django-httpresponse-fstring` | `raw-html-format`, `reflected-data-httpresponse` | yes |
| `hp-xss-flask-make-response` | `raw-html-format`, `raw-html-format` | yes |

## False-positive findings

| Where | Case | Line | Rule | Class |
|---|---|---|---|---|
| safe_case | `hp-path-secure-filename` | python/path_traversal.py:48 | `path-traversal-open` | path_traversal |
| safe_case | `hj-path-basename-stream` | javascript/path_traversal.js:29 | `express-path-join-resolve-traversal` | path_traversal |

## How to read this

* The suite is small, so each number comes with a 95% Wilson interval; one case moves a percentage by several points.
* Cases were written and labeled **before** the first scored run and were not adjusted to the output. See `backend/app/security/evaluation.py` for the exact scoring rules.
* This measures the rule set named at the top. A config that was tuned while looking at this same suite gives an optimistic result; only a suite the config was never tuned against is a fair estimate.
* Semgrep registry packs change over time; `semgrep_raw.json` is the exact output these numbers come from.
